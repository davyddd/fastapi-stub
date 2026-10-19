from functools import partial

from aerospike_native import Client, ClientPolicy, new_client

from ddaerospike.dsn import AerospikeDsn
from dddesign.structure.domains.constants import BaseEnum
from ddutils.connections import ConnectionManager, ConnectionManagerFactory
from ddutils.scoped_registry import ScopedRegistry, process_loop_scope

from config.settings import settings

# Milliseconds: opening a socket to a node, on the first connect and whenever a per-node pool grows
CONNECT_TIMEOUT = 5_000


class AerospikeConnectionAlias(str, BaseEnum):
    """Cluster to talk to, chosen per manager like Postgres' `postgres_session_factory(alias=...)`."""

    PRIMARY = 'primary'

    @property
    def url(self) -> AerospikeDsn:
        urls = {
            AerospikeConnectionAlias.PRIMARY: settings.AEROSPIKE_URL,
        }
        return urls[self]

    @property
    def namespace(self) -> str:
        return self.url.namespace


async def _create_client(alias: AerospikeConnectionAlias) -> Client:
    policy = ClientPolicy()
    policy.timeout = CONNECT_TIMEOUT
    return await new_client(policy, alias.url.seeds)


def _build_client_registry(alias: AerospikeConnectionAlias) -> ScopedRegistry[Client]:
    # One client per process and loop: the client completes its futures on the loop it was created in, and its
    # Rust threads do not survive a fork. It is itself a pool (connections per node, a cluster-tend task) and lives
    # until `aerospike_client_factory.close()` on shutdown.
    return ScopedRegistry[Client](
        create_func=partial(_create_client, alias), scope_func=process_loop_scope, destructor_method_name='close'
    )


aerospike_client_registries: dict[AerospikeConnectionAlias, ScopedRegistry[Client]] = {
    alias: _build_client_registry(alias) for alias in AerospikeConnectionAlias
}

# `async with aerospike_client_factory() as client`, or `(alias=AerospikeConnectionAlias.PRIMARY)` to pick the cluster;
# the default `ConnectionManager` hands out the process-wide client and closes nothing on exit.
# `aerospike_client_factory.close()` on shutdown closes the clients of the current loop.
aerospike_client_factory: ConnectionManagerFactory[AerospikeConnectionAlias, Client, ConnectionManager[Client]] = (
    ConnectionManagerFactory(
        aerospike_client_registries,
        default=AerospikeConnectionAlias.PRIMARY,
        connection_manager_class=ConnectionManager[Client],
    )
)
