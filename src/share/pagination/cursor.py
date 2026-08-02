from typing import Literal

Direction = Literal['next', 'prev']

# Tokens are URL-safe by construction (digits, hex, unpadded base64url), so the cursor
# needs no envelope encoding; '.' never occurs inside a token.
SEPARATOR = '.'
_DIRECTIONS = {'n': 'next', 'p': 'prev'}


def encode_cursor(fingerprint: str, tokens: list[str], direction: Direction) -> str:
    """Compact positional keyset cursor: `<n|p>.<key fingerprint>.<token>...`.
    Field names are not carried — the token order is the keyset key order, and the
    fingerprint pins which key the cursor was built for."""
    return SEPARATOR.join([direction[0], fingerprint, *tokens])


def decode_cursor(raw: str, fingerprint: str, expected_tokens: int) -> tuple[list[str], Direction]:
    """Decode an opaque cursor. Raises ValueError on malformed input or a cursor built
    for a different keyset key (fingerprint/arity mismatch)."""
    direction_char, _, rest = raw.partition(SEPARATOR)
    cursor_fingerprint, _, payload = rest.partition(SEPARATOR)
    tokens = payload.split(SEPARATOR) if payload else []
    if direction_char not in _DIRECTIONS or cursor_fingerprint != fingerprint or len(tokens) != expected_tokens:
        raise ValueError('Cannot decode cursor')
    return tokens, _DIRECTIONS[direction_char]  # type: ignore[return-value]
