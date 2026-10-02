import logging
from collections.abc import Iterable

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dddesign.structure.domains.constants import BaseEnum

from share.fastapi.utils.body_formatter import format_body
from share.fastapi.utils.url_mask_resolver import UrlMaskResolver

logger = logging.getLogger(__name__)

METHODS_WITH_BODY = {'POST', 'PUT', 'PATCH'}


class LogType(str, BaseEnum):
    REQUEST = 'REQUEST'
    RESPONSE = 'RESPONSE'

    @property
    def data_field(self) -> str:
        return f'{self.value.lower()}_data'


class RequestResponseLoggingMiddleware:
    """
    Pure ASGI middleware that logs incoming HTTP requests and outgoing responses.

    For POST, PUT, PATCH requests, the request body is logged as request_data.
    For all responses, the response body is logged as response_data.

    Important: Implemented as pure ASGI middleware (not BaseHTTPMiddleware)
    to avoid breaking context-dependent connection scoping.
    """

    def __init__(self, app: ASGIApp):
        self.app = app
        self.url_mask_resolver = UrlMaskResolver(app)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        http_method: str = scope.get('method', '')

        if scope['type'] != 'http' or http_method == 'OPTIONS':
            await self.app(scope, receive, send)
            return

        url_path: str = scope.get('path', '')
        url_mask = self.url_mask_resolver.resolve(url_path)

        message_template = f'{{log_type}} {http_method} {url_path}'
        base_log: dict = {
            'http_method': http_method,
            'url_path': url_path,
            'url_mask': url_mask,
            'masked_request': f'{http_method} {url_mask}',
        }

        request_body, receive = await self._observe_request_data(http_method, receive)
        request_content_type = self._get_content_type(scope.get('headers', []))
        logger.info(self._get_log(LogType.REQUEST, base_log, message_template, request_body, request_content_type))

        try:
            response_body, status_code, response_content_type = await self._observe_response_data(scope, receive, send)
        except Exception:
            logger.exception(self._get_log(LogType.RESPONSE, base_log, message_template, status_code=500))
            raise
        logger.info(
            self._get_log(
                LogType.RESPONSE, base_log, message_template, response_body, response_content_type, status_code=status_code
            )
        )

    @staticmethod
    def _get_log(
        log_type: LogType,
        base_log: dict,
        message_template: str,
        body: bytes = b'',
        content_type: str | None = None,
        **kwargs,
    ) -> dict:
        log: dict = {**base_log, 'message': message_template.format(log_type=log_type), 'log_type': log_type, **kwargs}
        if body:
            log[log_type.data_field] = format_body(body, content_type)
        return log

    @staticmethod
    def _get_content_type(headers: Iterable[tuple[bytes, bytes]]) -> str | None:
        for name, value in headers:
            if name.lower() == b'content-type':
                return value.decode('latin-1')
        return None

    @staticmethod
    async def _observe_request_data(http_method: str, receive: Receive) -> tuple[bytes, Receive]:
        if http_method not in METHODS_WITH_BODY:
            return b'', receive

        body_parts: list[bytes] = []
        while True:
            message = await receive()
            body_parts.append(message.get('body', b''))
            if not message.get('more_body', False):
                break

        body = b''.join(body_parts)
        body_sent = False

        async def receive_wrapper() -> Message:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return await receive()

        return body, receive_wrapper

    async def _observe_response_data(self, scope: Scope, receive: Receive, send: Send) -> tuple[bytes, int | None, str | None]:
        status_code: int | None = None
        content_type: str | None = None
        response_body_parts: list[bytes] = []

        async def send_wrapper(message: Message):
            nonlocal status_code, content_type
            if message['type'] == 'http.response.start':
                status_code = message.get('status')
                content_type = self._get_content_type(message.get('headers', []))
            elif message['type'] == 'http.response.body':
                response_body_parts.append(message.get('body', b''))
            await send(message)

        await self.app(scope, receive, send_wrapper)
        return b''.join(response_body_parts), status_code, content_type
