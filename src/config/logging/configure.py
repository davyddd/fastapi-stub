from config.logging.handlers.sentry.config import configure_sentry_handler
from config.logging.handlers.stdout.config import configure_stdout_handler
from config.settings import settings

_configured = False


def configure_logging_handlers():
    # Called by every entrypoint; the web and scheduler entrypoints also import the dramatiq one, which calls it
    # on import, so the second call must not configure the handlers (and init Sentry) again
    global _configured
    if _configured or settings.DEBUG:
        return
    configure_stdout_handler()
    configure_sentry_handler()
    _configured = True
