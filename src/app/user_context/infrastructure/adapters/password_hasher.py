import base64
import hashlib
import hmac
import os


class PasswordHasher:
    _salt_size: int = 16
    _n: int = 2**14
    _r: int = 8
    _p: int = 1
    _dklen: int = 64

    def hash(self, password: str) -> str:
        salt = os.urandom(self._salt_size)
        password_hash = hashlib.scrypt(
            password.encode('utf-8'),
            salt=salt,
            n=self._n,
            r=self._r,
            p=self._p,
            dklen=self._dklen,
        )
        encoded_salt = base64.b64encode(salt).decode('ascii')
        encoded_hash = base64.b64encode(password_hash).decode('ascii')
        return f'scrypt${self._n}${self._r}${self._p}${encoded_salt}${encoded_hash}'

    def verify(self, password: str, hashed_password: str) -> bool:
        algorithm, n, r, p, encoded_salt, encoded_hash = hashed_password.split('$', maxsplit=5)
        if algorithm != 'scrypt':
            return False

        salt = base64.b64decode(encoded_salt.encode('ascii'))
        expected_hash = base64.b64decode(encoded_hash.encode('ascii'))
        password_hash = hashlib.scrypt(
            password.encode('utf-8'),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected_hash),
        )
        return hmac.compare_digest(password_hash, expected_hash)


password_hasher_impl = PasswordHasher()
