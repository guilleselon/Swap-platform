"""Concrete ChainRegistry — wires config + Web3Client + providers."""

from __future__ import annotations

from app.application.ports import DEXProvider
from app.domain.models import Chain, DEX, ProtocolVersion
from app.infrastructure.blockchain.web3_client import Web3Client
from app.infrastructure.dex_providers.uniswap_v2 import UniswapV2Provider


class Web3ChainRegistry:
    """Implements the application-layer ``ChainRegistry`` port."""

    def __init__(self, chains: dict[int, Chain]) -> None:
        self._chains = dict(chains)
        self._providers: dict[int, dict[str, DEXProvider]] = {}

    # -- wiring -------------------------------------------------------------- #

    def register(self, provider: DEXProvider) -> None:
        self._providers.setdefault(provider.dex.chain_id, {})[
            provider.dex.id
        ] = provider

    @classmethod
    def build(
        cls,
        chains: dict[int, Chain],
        dexes_by_chain: dict[int, list[DEX]],
        w3_client: Web3Client,
    ) -> "Web3ChainRegistry":
        registry = cls(chains)
        supported = set(w3_client.supported_chain_ids())
        for chain_id, dexes in dexes_by_chain.items():
            if chain_id not in supported or chain_id not in chains:
                continue
            chain = chains[chain_id]
            for dex in dexes:
                if dex.protocol is ProtocolVersion.V2:
                    registry.register(
                        UniswapV2Provider(dex, chain, w3_client)
                    )
                # v3 / v4 adapters will be wired here when implemented.
        return registry

    # -- ChainRegistry protocol ---------------------------------------------- #

    def get_chain(self, chain_id: int) -> Chain | None:
        return self._chains.get(chain_id)

    def list_chains(self) -> list[Chain]:
        """Return chains that have at least one registered DEX provider."""
        return [
            self._chains[cid]
            for cid in sorted(self._providers)
            if cid in self._chains
        ]

    def list_dex_providers(self, chain_id: int) -> list[DEXProvider]:
        return list(self._providers.get(chain_id, {}).values())

    def get_dex_provider(
        self, chain_id: int, dex_id: str
    ) -> DEXProvider | None:
        return self._providers.get(chain_id, {}).get(dex_id)
