from datetime import datetime

from sqlalchemy import func
from sqlmodel import Field

from share.sqlmodel.models.types.datetime import DATETIME_TZ


class UpdatedDateMixin:
    updated_at: datetime | None = Field(
        default=None,
        sa_type=DATETIME_TZ,  # type: ignore[arg-type]
        sa_column_kwargs={'nullable': False, 'server_default': func.now(), 'onupdate': func.current_timestamp()},
    )


class CreatedDateMixin:
    created_at: datetime | None = Field(
        default=None,
        sa_type=DATETIME_TZ,  # type: ignore[arg-type]
        sa_column_kwargs={'nullable': False, 'server_default': func.now()},
    )


class DatesMixin(UpdatedDateMixin, CreatedDateMixin):
    pass
