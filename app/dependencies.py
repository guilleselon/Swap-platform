"""Composition root: singleton factories for the whole application.

All service instances are created exactly once per process. Tests can
override them by calling ``.cache_clear()`` on the relevant factory or
by providing fakes via FastAPI dependency_overrides.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from app.application import SwapOrchestrator
from app.application.ports import ChainRegistry, Clock
from app.config.chains import CHAINS, DEXES_BY_CHAIN
from app.config.settings import rpc_urls
from app.infrastructure import Web3ChainRegistry, Web3Client


class SystemClock:
    """Production implementation of the ``Clock`` port."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def get_clock() -> Clock:
    return SystemClock()


@lru_cache(maxsize=1)
def get_web3_client() -> Web3Client:
    return Web3Client(rpc_urls())


@lru_cache(maxsize=1)
def get_chain_registry() -> ChainRegistry:
    return Web3ChainRegistry.build(CHAINS, DEXES_BY_CHAIN, get_web3_client())


@lru_cache(maxsize=1)
def get_orchestrator() -> SwapOrchestrator:
    return SwapOrchestrator(get_chain_registry(), get_clock())


def reset_singletons() -> None:
    """Clear all caches. Used by tests to isolate state across cases."""
    get_clock.cache_clear()
    get_web3_client.cache_clear()
    get_chain_registry.cache_clear()
    get_orchestrator.cache_clear()
