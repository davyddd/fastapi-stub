from typing import Any

from pydantic import BaseModel


class UpdateParams(BaseModel):
    """Base contract of the columns a repository allows to update.

    Subclass per model with optional fields; the application fills the ones it wants
    to change, `None` fields are skipped. The UPDATE counterpart of the `filters`
    contract passed to `QueryParams.build` — see `FilterSet.update_by_filters`.
    """

    @property
    def values(self) -> dict[str, Any]:
        return {field_name: value for field_name, value in self if value is not None}
