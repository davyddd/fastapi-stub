from __future__ import annotations

import asyncio
import contextlib
import glob
import json
import os
import tempfile
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread

from dramatiq.asyncio import get_event_loop_thread
from dramatiq.logging import get_logger
from dramatiq.middleware import Middleware

HEALTH_DIR = os.path.join(tempfile.gettempdir(), 'dramatiq-health')
HEALTH_PORT = int(os.getenv('DRAMATIQ_HEALTH_PORT', '9192'))
HEALTH_PING_INTERVAL = int(os.getenv('DRAMATIQ_HEALTH_PING_INTERVAL', '10'))
HEALTH_STALE_THRESHOLD = int(os.getenv('DRAMATIQ_HEALTH_STALE_THRESHOLD', '60'))

os.makedirs(HEALTH_DIR, exist_ok=True)

_shutting_down = Event()


class HealthCheck(Middleware):
    def after_worker_boot(self, broker, worker):  # noqa: ARG002
        pid = os.getpid()
        thread = Thread(target=_health_pinger, args=(pid, worker), daemon=True)
        thread.start()

    def before_worker_shutdown(self, broker, worker):  # noqa: ARG002
        _shutting_down.set()

    def after_worker_shutdown(self, broker, worker):  # noqa: ARG002
        pid = os.getpid()
        path = os.path.join(HEALTH_DIR, f'worker-{pid}')
        with contextlib.suppress(OSError):
            os.remove(path)

    @property
    def forks(self):
        return [_run_health_server]


async def _ping():
    return True


def _health_pinger(pid: int, worker):
    logger = get_logger(__name__, f'HealthPinger({pid})')
    path = os.path.join(HEALTH_DIR, f'worker-{pid}')

    # `wait` returns True when shutdown is signalled, so we exit before logging dead threads torn down by SIGTERM.
    while not _shutting_down.wait(HEALTH_PING_INTERVAL):
        # Check 1: all WorkerThreads alive
        dead_threads = [t for t in worker.workers if not t.is_alive()]
        if dead_threads:
            logger.warning('Dead worker threads detected: %d/%d for worker %d', len(dead_threads), len(worker.workers), pid)
            continue

        # Check 2: event loop responsive
        event_loop_thread = get_event_loop_thread()
        if event_loop_thread is None:
            continue

        try:
            future = asyncio.run_coroutine_threadsafe(_ping(), event_loop_thread.loop)
            future.result(timeout=HEALTH_PING_INTERVAL)
        except (TimeoutError, RuntimeError):
            logger.warning('Event loop ping failed for worker %d', pid)
            continue

        # Both checks passed
        with open(path, 'w') as f:
            f.write(str(time.time()))


def _cleanup_stale_files():
    """Remove stale worker files left by previously crashed containers."""
    now = time.time()
    removed = []
    for path in glob.glob(os.path.join(HEALTH_DIR, 'worker-*')):
        try:
            with open(path) as f:
                last_ping = float(f.read().strip())
            if now - last_ping > HEALTH_STALE_THRESHOLD:
                os.remove(path)
                removed.append(os.path.basename(path))
        except (ValueError, OSError):
            os.remove(path)
            removed.append(os.path.basename(path))
    return removed


def _check_health():
    worker_files = glob.glob(os.path.join(HEALTH_DIR, 'worker-*'))
    if not worker_files:
        return False, {'status': 'unhealthy', 'errors': ['no worker files found'], 'workers': {}}

    now = time.time()
    errors = []
    workers = {}

    for path in worker_files:
        worker_name = os.path.basename(path)
        try:
            with open(path) as f:
                last_ping = float(f.read().strip())
            age = int(now - last_ping)
            healthy = age <= HEALTH_STALE_THRESHOLD
            workers[worker_name] = {'last_ping_age_s': age, 'healthy': healthy}
            if not healthy:
                errors.append(f'{worker_name}: stale ({age}s)')
        except (ValueError, OSError):
            workers[worker_name] = {'healthy': False, 'error': 'unreadable'}
            errors.append(f'{worker_name}: unreadable')

    status = 'healthy' if not errors else 'unhealthy'
    return not errors, {'status': status, 'errors': errors, 'workers': workers}


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path in ('/livez', '/readyz', '/startupz'):
            ok, result = _check_health()
        else:
            self.send_response(404)
            self.end_headers()
            return

        status = 200 if ok else 503
        body = json.dumps(result).encode()
        self.send_response(status)
        self.send_header('content-type', 'application/json')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # type: ignore[invalid-method-override]
        logger = get_logger(__name__, type(self))
        logger.debug(fmt, *args)


def _run_health_server():
    logger = get_logger(__name__, '_run_health_server')

    removed = _cleanup_stale_files()
    if removed:
        logger.info('Cleaned up stale worker files: %s', removed)

    logger.info('Starting health check server on port %d...', HEALTH_PORT)
    try:
        httpd = HTTPServer(('0.0.0.0', HEALTH_PORT), _HealthHandler)
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
    return 0
