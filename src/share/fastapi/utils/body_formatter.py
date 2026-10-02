import json
import os

MAX_BODY_LOG_SIZE = int(os.getenv('MAX_BODY_LOG_SIZE', 1_048_576))  # default 1 MB

JSON_MEDIA_TYPE = 'application/json'
JSON_MEDIA_TYPE_SUFFIX = '+json'


def _get_media_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    return content_type.split(';', 1)[0].strip().lower()


def _parse_json(body: bytes) -> dict | None:
    try:
        parsed = json.loads(body.decode('utf-8'))
    except UnicodeDecodeError, json.JSONDecodeError, ValueError:
        return None
    match parsed:
        case dict():
            return parsed
        case list():
            return {'items': parsed}
        case _:
            return {'raw': parsed}


def format_body(body: bytes, content_type: str | None) -> dict:
    # The ES field is `flattened` and accepts objects only: everything that is not loggable JSON becomes a stub object.
    media_type = _get_media_type(content_type)
    is_json = media_type is not None and (media_type == JSON_MEDIA_TYPE or media_type.endswith(JSON_MEDIA_TYPE_SUFFIX))
    if is_json and len(body) <= MAX_BODY_LOG_SIZE and (parsed := _parse_json(body)) is not None:
        return parsed
    return {'content_type': media_type, 'size': len(body)}
