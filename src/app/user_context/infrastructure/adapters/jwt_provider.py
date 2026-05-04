import base64
import hashlib
import hmac
import json
import time
from uuid import UUID

from config.settings import settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


class JWTProvider:
    def __init__(self, secret_key: str, algorithm: str, expires_seconds: int):
        if algorithm != 'HS256':
            raise ValueError('Only HS256 is supported')
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expires_seconds = expires_seconds

    def create_access_token(self, user_id: UUID) -> str:
        now = int(time.time())
        payload = {'sub': str(user_id), 'iat': now, 'exp': now + self.expires_seconds}
        header = {'alg': self.algorithm, 'typ': 'JWT'}

        encoded_header = _b64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
        encoded_payload = _b64url_encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
        signing_input = f'{encoded_header}.{encoded_payload}'.encode('ascii')
        signature = hmac.new(self.secret_key.encode('utf-8'), signing_input, hashlib.sha256).digest()
        encoded_signature = _b64url_encode(signature)
        return f'{encoded_header}.{encoded_payload}.{encoded_signature}'


jwt_provider_impl = JWTProvider(
    secret_key=settings.JWT_SECRET_KEY,
    algorithm=settings.JWT_ALGORITHM,
    expires_seconds=settings.JWT_ACCESS_TOKEN_EXPIRES_SECONDS,
)
