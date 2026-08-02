from sqlalchemy import DateTime

# `timezone=True`: stores values as PostgreSQL `TIMESTAMP WITH TIME ZONE` (tz-aware), not naive `TIMESTAMP`.
DATETIME_TZ = DateTime(timezone=True)
