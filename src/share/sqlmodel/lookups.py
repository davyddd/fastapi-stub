from enum import StrEnum

LOOKUP_SEPARATOR = '__'


class Lookup(StrEnum):
    EXACT = 'exact'
    IN = 'in'
    ISNULL = 'isnull'


class SearchType(StrEnum):
    ILIKE = 'ilike'
    EXACT = 'exact'


class FieldLookups:
    """Annotated marker declaring which lookups a filter field allows:

        class CampaignFilters(DataTransferObject):
            campaign_id: Annotated[CampaignId | None, FieldLookups(Lookup.IN)] = None
            email: Annotated[str | None, FieldLookups(Lookup.EXACT, Lookup.ISNULL)] = None

    `FilterParams.build` expands each declared lookup into its own field
    (`campaign_id__in: list[CampaignId] | None`, `email__isnull: bool | None`, ...).
    Fields without the marker allow EXACT only. List values are accepted only
    through an IN lookup — never on the bare field.
    """

    def __init__(self, *lookups: Lookup) -> None:
        if not lookups:
            raise ValueError('At least one lookup must be declared')
        self.lookups = tuple(lookups)
