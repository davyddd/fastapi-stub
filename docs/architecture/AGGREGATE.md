## Aggregate

**Aggregate** is a collection of related Entities that are treated as a single unit within a single bounded context.
By exposing controlled methods for interaction, it enforces consistency and ensures atomic execution.

**Constraints:**
1. **Consistency** — exposes public methods that enforce domain rules across all internal Entities.
2. **Atomicity** — treats operations on the Aggregate as a single unit.

In most cases, Aggregate is not required. Data from Ports can be packed into a DTO, passed to Application, 
which builds Entities separately (divide and conquer). Use Aggregate only in the following cases:
- When multiple Entities must be validated or modified together under shared business rules.
- Simple container for related Entities within a single HTTP request, reducing multiple REST calls and network overhead.

**Example:**
```python
from dddesign.structure.domains.aggregates import Aggregate
from pydantic import model_validator

from app.profile_context.domains.dto.media import Media
from app.profile_context.domains.entities.profile import Profile


class ProfileAggregate(Aggregate):
    profile: Profile
    icon: Media | None = None

    @model_validator(mode='after')
    def validate_consistency(self):
        if self.profile.icon_id:
            if self.icon is None:
                raise ValueError('`icon` field is required when `profile` has `icon_id`')
            if self.profile.icon_id != self.icon.media_id:
                raise ValueError('`profile.icon_id` is not equal to `icon.media_id`')
        elif self.icon is not None:
            raise ValueError('`icon` field is not allowed when `profile` has no `icon_id`')

        return self
```

### Aggregate List Factory

`AggregateListFactory` converts a list of Entities into Aggregates by automatically fetching related data.
It solves the N+1 problem: instead of making a separate request for each Entity's dependencies,
it collects all required IDs and fetches them in a single batch request via `get_map`.

The factory uses `AggregateDependencyMapper` to define how dependencies are resolved:
- `method_getter` — method that fetches related data (`get_map` for batch, `get` for single)
- `entity_attribute_name` — field in Entity containing the foreign key (e.g., `icon_id`)
- `aggregate_attribute_name` — field in Aggregate where the resolved object is stored (e.g., `icon`)

```python
from dddesign.structure.infrastructure.adapters.internal import InternalAdapter

from app.profile_context.domains.dto.media import Media, MediaId
from app.media_context.applications.media import MediaApp, media_app_impl


class MediaAdapter(InternalAdapter):
    media_app: MediaApp = media_app_impl
    
    def get(self, media_id: MediaId | None) -> Media | None:
        if media_id is None:
            return None

        medias = self.get_map((media_id,))
        return next(iter(medias.values()), None)

    def get_map(self, media_ids: tuple[str, ...]) -> dict[str, Media]:
        if not media_ids:
            return {}

        medias = self.media_app.get_list(media_ids=media_ids)
        return {MediaId(media.media_id): Media(**media.model_dump()) for media in medias}


media_adapter_impl = MediaAdapter()
```

**Example 1**: Retrieving multiple related objects
```python
from dddesign.structure.domains.aggregates import AggregateDependencyMapper, AggregateListFactory

from app.profile_context.domains.aggregates.profile import ProfileAggregate
from app.profile_context.infrastructure.adapters.internal.media import media_adapter_impl


aggregate_list_factory = AggregateListFactory[ProfileAggregate](
    aggregate_class=ProfileAggregate,
    aggregate_entity_attribute_name='profile',
    dependency_mappers=(
        AggregateDependencyMapper(
            method_getter=media_adapter_impl.get_map,
            entity_attribute_name='icon_id',
            aggregate_attribute_name='icon',
        ),
    ),
)

aggregates: list[ProfileAggregate] = aggregate_list_factory.create_list([...])  # list of Profile Entity
```

**Example 2**: Retrieving a single related object
```python
from dddesign.structure.domains.aggregates import AggregateDependencyMapper, AggregateListFactory

from app.profile_context.domains.aggregates.profile import ProfileAggregate
from app.profile_context.infrastructure.adapters.internal.media import media_adapter_impl


aggregate_list_factory = AggregateListFactory[ProfileAggregate](
    aggregate_class=ProfileAggregate,
    aggregate_entity_attribute_name='profile',
    dependency_mappers=(
        AggregateDependencyMapper(
            method_getter=media_adapter_impl.get,
            entity_attribute_name='icon_id',
            aggregate_attribute_name='icon',
        ),
    ),
)

aggregates: list[ProfileAggregate] = aggregate_list_factory.create_list([...])  # list of Profile Entity
```
