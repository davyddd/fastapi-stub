from typing import Self

from pydantic import BaseModel

from share.sqlmodel.filter_params import FilterParams


class Pagination(BaseModel):
    """One pagination shape for both paging styles. The client always sends `page` and
    echoes `next_cursor`/`prev_cursor` when it has one; the server serves cursor requests
    via the fast keyset path and falls back to page/offset otherwise. `count` is
    optional — large tables skip the expensive COUNT, and a non-null `next_cursor` is
    the "there is more" signal.
    """

    page: int
    limit: int
    count: int | None = None
    next_cursor: str | None = None
    prev_cursor: str | None = None

    @classmethod
    def from_params(
        cls,
        params: FilterParams,
        count: int | None = None,
        next_cursor: str | None = None,
        prev_cursor: str | None = None,
        limit: int | None = None,
    ) -> Self:
        """`limit` overrides the display limit for endpoints with a fixed page size.
        A non-null `next_cursor` IS the "there is more" signal; page/limit endpoints
        expose `count` and leave the cursors empty."""
        return cls(
            page=params.page,
            limit=limit or params.page_size,
            count=count,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
        )


class Meta(BaseModel):
    pagination: Pagination


class PaginatedResponse[T](BaseModel):
    data: list[T]
    meta: Meta

    @classmethod
    def factory(cls, items: list[T], pagination: Pagination) -> 'PaginatedResponse[T]':
        return cls(data=items, meta=Meta(pagination=pagination))
