"""Shared fixtures and in-memory fakes for the API tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.deps import chain_registry_dep, orchestrator_dep
from app.application import SwapOrchestrator, TransactionRequest
from app.domain.models import Chain, DEX, ProtocolVersion, Quote, Token
from app.main import create_app

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

USDC_ADDR = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH_ADDR = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
SENDER = "0x0000000000000000000000000000000000000001"


def _chain(chain_id: int = 1) -> Chain:
    return Chain(
        id=chain_id,
        name="Ethereum" if chain_id == 1 else f"Chain{chain_id}",
        native_symbol="ETH",
        wrapped_native_address=WETH_ADDR,
        block_explorer_url="https://etherscan.io" if chain_id == 1 else None,
    )


def _usdc(chain_id: int = 1) -> Token:
    return Token(chain_id=chain_id, address=USDC_ADDR, symbol="USDC", decimals=6)


def _weth(chain_id: int = 1) -> Token:
    return Token(chain_id=chain_id, address=WETH_ADDR, symbol="WETH", decimals=18)


def _dex(dex_id: str, chain_id: int = 1) -> DEX:
    return DEX(
        id=dex_id,
        name=dex_id.title(),
        chain_id=chain_id,
        router_address=ROUTER,
        protocol=ProtocolVersion.V2,
    )


# --------------------------------------------------------------------------- #
# Fakes                                                                        #
# --------------------------------------------------------------------------- #


class FixedClock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


class FakeDEXProvider:
    def __init__(
        self,
        dex: DEX,
        amount_out: int | None,
        *,
        raises: Exception | None = None,
    ) -> None:
        self._dex = dex
        self._amount_out = amount_out
        self._raises = raises

    @property
    def dex(self) -> DEX:
        return self._dex

    async def get_quote(self, token_in, token_out, amount_in, *, path=None):
        if self._raises is not None:
            raise self._raises
        if self._amount_out is None:
            return None
        return Quote(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            amount_out=self._amount_out,
            dex=self._dex,
            ttl_seconds=600,
        )

    async def build_swap_tx(self, params, *, sender):
        return TransactionRequest(
            chain_id=params.token_in.chain_id,
            to=self._dex.router_address,
            data="0xdeadbeef",
            value=0,
        )


class FakeRegistry:
    def __init__(self, chains: list[Chain], providers: list[FakeDEXProvider]) -> None:
        self._chains = {c.id: c for c in chains}
        self._providers = providers

    def get_chain(self, chain_id: int) -> Chain | None:
        return self._chains.get(chain_id)

    def list_chains(self) -> list[Chain]:
        usable = {p.dex.chain_id for p in self._providers}
        return [c for cid, c in self._chains.items() if cid in usable]

    def list_dex_providers(self, chain_id: int) -> list[FakeDEXProvider]:
        return [p for p in self._providers if p.dex.chain_id == chain_id]

    def get_dex_provider(self, chain_id: int, dex_id: str) -> FakeDEXProvider | None:
        for p in self._providers:
            if p.dex.chain_id == chain_id and p.dex.id == dex_id:
                return p
        return None


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))


@pytest.fixture
def default_registry() -> FakeRegistry:
    return FakeRegistry(
        chains=[_chain(1)],
        providers=[
            FakeDEXProvider(_dex("uniswap_v2"), 400_000_000_000_000_000),
            FakeDEXProvider(_dex("sushiswap"), 420_000_000_000_000_000),
        ],
    )


@pytest.fixture
def client(default_registry: FakeRegistry, fixed_clock: FixedClock):
    app = create_app()
    orchestrator = SwapOrchestrator(default_registry, fixed_clock)
    app.dependency_overrides[orchestrator_dep] = lambda: orchestrator
    app.dependency_overrides[chain_registry_dep] = lambda: default_registry
    with TestClient(app) as test_client:
        yield test_client


# Helpers re-exportados para los tests
def usdc(chain_id: int = 1) -> Token:
    return _usdc(chain_id)


def weth(chain_id: int = 1) -> Token:
    return _weth(chain_id)


__all__ = [
    "FakeDEXProvider",
    "FakeRegistry",
    "FixedClock",
    "USDC_ADDR",
    "WETH_ADDR",
    "ROUTER",
    "SENDER",
    "usdc",
    "weth",
    "_chain",
    "_dex",
]
