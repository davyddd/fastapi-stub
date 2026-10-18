from ddaerospike.feature_flags import AerospikeFeatureFlagStorage, FeatureFlagData
from ddaerospike.manager import AerospikeManager

from ddutils.feature_flags import FeatureFlags

from config.databases.aerospike import AerospikeConnectionAlias, aerospike_client_factory


class FeatureFlagManager(AerospikeManager[FeatureFlagData]):
    client_factory = aerospike_client_factory
    namespace = AerospikeConnectionAlias.PRIMARY.namespace
    set_name = 'feature_flag'


# The flags live in the `feature_flag` set of Aerospike, a flag per record; `RedisFeatureFlagStorage` from ddredis is
# the drop-in alternative. Readers share one per-process cache, so one instance for the whole application.
feature_flags = FeatureFlags(AerospikeFeatureFlagStorage(FeatureFlagManager()))
