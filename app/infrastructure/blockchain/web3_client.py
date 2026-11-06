"""Async Web3 connection pool, one instance per chain."""

from __future__ import annotations

from web3 import AsyncWeb3, AsyncHTTPProvider

from app.domain.exceptions import UnsupportedChainError


class Web3Client:
    """Lazily builds and caches ``AsyncWeb3`` instances per chain id."""

    def __init__(self, rpc_urls: dict[int, str]) -> None:
        self._urls = dict(rpc_urls)
        self._instances: dict[int, AsyncWeb3] = {}

    def supported_chain_ids(self) -> list[int]:
        return sorted(self._urls)

    def get(self, chain_id: int) -> AsyncWeb3:
        if chain_id not in self._urls:
            raise UnsupportedChainError(
                f"No RPC configured for chain {chain_id}"
            )
        if chain_id not in self._instances:
            self._instances[chain_id] = AsyncWeb3(
                AsyncHTTPProvider(self._urls[chain_id])
            )
        return self._instances[chain_id]
