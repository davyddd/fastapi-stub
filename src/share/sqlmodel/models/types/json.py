from sqlalchemy.dialects.postgresql import JSONB as _JSONB

# `none_as_null=True`: Python `None` persists as SQL NULL, not the JSON literal `null` (`'null'::jsonb`).
JSONB = _JSONB(none_as_null=True)
