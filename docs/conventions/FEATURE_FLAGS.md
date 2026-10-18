## Feature Flags

Feature flags come from [ddutils](https://github.com/davyddd/ddutils) (`ddutils.feature_flags`), the storage from
[ddaerospike](https://github.com/davyddd/ddaerospike): the `feature_flag` set of Aerospike, a flag per record, the
flag name is the primary key and `enabled`, `proportion`, `payload` are its bins (`RedisFeatureFlagStorage` from
ddredis is the drop-in alternative). `config.feature_flags.feature_flags` is the single reader of the application,
with a per-process cache (15–20 seconds), so a flag read costs nothing on the hot path and a change in Aerospike is
visible within that time.

A flag is on or off (`enabled`), seen by a share of the readers (`proportion`, 1.0 for everyone) and may carry a
free-form `payload`.

### Reading

`is_enabled` combines the switch and the proportion. Pass an `idempotent_key` (a user id, an account id) for a
rollout: the key is hashed into a bucket of the flag, so the same user always lands on the same side. Without a key
the decision is random on every call.

```python
from config.feature_flags import feature_flags


class CheckoutApp(Application):
    async def checkout(self, profile: Profile) -> Order:
        if await feature_flags.is_enabled('new_checkout'):                  # a kill-switch: proportion 1.0
            return await self._checkout_v2(profile)
        if await feature_flags.is_enabled('new_ranking', profile.id):      # a rollout: on for `proportion` of the profiles
            ...
```

### Payload

The payload's shape is the application's business: parse it with a model where it is used, after the switch.

```python
class EmailProviderBlockRules(ValueObject):
    globally_blocked: frozenset[MailProvider] = frozenset()


if await feature_flags.is_enabled('email_provider_block'):
    rules = EmailProviderBlockRules.model_validate(await feature_flags.get_payload('email_provider_block'))
```

### Writing

Flags are written through the storage, by an admin panel or a script, never by the readers:

```python
from ddutils.feature_flags import FeatureFlagRecord

storage = feature_flags.storage
await storage.put('new_ranking', FeatureFlagRecord(enabled=True, proportion=0.1, payload={}))
await storage.get_map()                                                   # every flag by name
await storage.rename('new_ranking', 'ranking_v2', await storage.get('new_ranking'))
await storage.delete('ranking_v2')
```

### Failures

An Aerospike failure never reaches the caller: the last known record (or the defaults, for a flag never read) is served
and re-read with an exponential backoff; a record that does not parse is logged and read as the defaults. A missing
flag is off.
