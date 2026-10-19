## Feature Flags

Feature flags come from [ddutils](https://github.com/davyddd/ddutils) (`ddutils.feature_flags`), the storage from
[ddaerospike](https://github.com/davyddd/ddaerospike): the `feature_flag` set of Aerospike, a flag per record, the
flag name is the primary key and `enabled`, `proportion`, `payload` are its bins (`RedisFeatureFlagStorage` from
ddredis is the drop-in alternative). `config.feature_flags.feature_flags` is the single reader of the application:
`FeatureFlags(storage, base_ttl=15)` caches every flag it read for 15 to 20 seconds, so a flag read costs nothing on
the hot path and a change in Aerospike is visible within that time, also to the process that wrote it. The cache
belongs to the instance, so there is one instance.

A flag is `FeatureFlagRecord(enabled=False, proportion=1.0, payload={})`: on or off, seen by a share of the readers
and carrying a free-form payload. A flag that does not exist reads as these defaults, so a missing flag is off.

### Reading

`is_enabled(name, idempotent_key=None)` combines the switch and the proportion: off for everyone when the flag is
off, on for `proportion` of the readers when it is on. The proportion applies whenever the flag is on, so a
kill-switch keeps the default `1.0` and a rollout sets it explicitly. With an `idempotent_key` the split is
repeatable: the key is hashed together with the flag name into a bucket, so the same key always lands on the same
side of one flag, and may land on the other side of another. Without a key the decision is random on every call.

The key is the unit the share is measured on, so pick the one the feature is about: for something a user sees,
the user or profile id; for delivery settings per recipient, the recipient, not the project. A key one level too
coarse (a project id when one big project carries most of the traffic) makes a 10% rollout hit far more or far
less than 10% of what the feature touches.

```python
from config.feature_flags import feature_flags


class CheckoutApp(Application):
    async def checkout(self, profile: Profile) -> Order:
        if await feature_flags.is_enabled('new_checkout'):                  # a kill-switch: the default proportion
            return await self._checkout_v2(profile)
        if await feature_flags.is_enabled('new_ranking', profile.id):      # a rollout: on for `proportion` of the profiles
            ...
```

### Payload

`get_payload(name)` is the payload as stored, `{}` for a missing flag. Its shape is the application's business:
parse it with a model where it is used, after the switch, and do not mutate the mapping, it is the cached object.

```python
class EmailProviderBlockRules(ValueObject):
    globally_blocked: frozenset[MailProvider] = frozenset()


if await feature_flags.is_enabled('email_provider_block'):
    rules = EmailProviderBlockRules.model_validate(await feature_flags.get_payload('email_provider_block'))
```

### Writing

Flags are written through the storage, by an admin panel or a script, never by the readers. `put` creates or
overwrites, there is no create-only: a script that must not overwrite reads with `get` first. `rename` is
put-then-delete on Aerospike (two records, no transaction) and one MULTI/EXEC on Redis. `get_map` on Aerospike
reads at most 1000 flags and logs an ERROR when the set holds that many.

```python
from ddutils.feature_flags import FeatureFlagRecord

storage = feature_flags.storage
await storage.put('new_ranking', FeatureFlagRecord(enabled=True, proportion=0.1, payload={}))
await storage.get_map()                                                   # every flag by name
await storage.rename('new_ranking', 'ranking_v2', await storage.get('new_ranking'))
await storage.delete('ranking_v2')
```

`FeatureFlagRecord` validates on construction: `enabled` takes a bool or what a storage may hold for one (`1`,
`'true'`, `'yes'`), `proportion` a number in 0..1, `payload` a mapping. `from_dict` is strict, an unknown key is an
error, so a record edited by hand with an extra bin is malformed.

### Failures

An Aerospike failure never reaches the caller: the last known record (or the defaults, for a flag never read) is
served and logged, and the re-read is retried with a backoff from 1 second doubling up to the TTL. A record that
does not validate is logged and read by `get` as the defaults, which turns the flag off; in `get_map` one such
record makes the whole list unavailable until it is fixed.
