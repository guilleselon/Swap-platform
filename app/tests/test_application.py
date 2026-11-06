"""Application-layer tests using in-memory fakes of the ports."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.application import SwapOrchestrator, TransactionRequest
from app.domain import (
    Chain,
    DEX,
    ProtocolVersion,
    Quote,
    SwapRequest,
    SwapStatus,
    UnsupportedDexError,
)
from app.domain.exceptions import NoRouteFoundError, UnsupportedChainError
from app.domain.models import Token

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
        ttl_seconds: int = 600,
    ) -> None:
        self._dex = dex
        self._amount_out = amount_out
        self._raises = raises
        self._ttl = ttl_seconds
        self.quote_calls = 0

    @property
    def dex(self) -> DEX:
        return self._dex

    async def get_quote(self, token_in, token_out, amount_in, *, path=None):
        self.quote_calls += 1
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
            ttl_seconds=self._ttl,
        )

    async def build_swap_tx(self, params, *, sender):
        return TransactionRequest(
            chain_id=params.token_in.chain_id,
            to=self._dex.router_address,
            data="0x",
        )


class FakeRegistry:
    def __init__(self, chain: Chain, providers: list[FakeDEXProvider]) -> None:
        self._chain = chain
        self._providers = providers

    def get_chain(self, chain_id: int) -> Chain | None:
        return self._chain if chain_id == self._chain.id else None

    def list_dex_providers(self, chain_id: int) -> list[FakeDEXProvider]:
        return list(self._providers) if chain_id == self._chain.id else []

    def get_dex_provider(self, chain_id: int, dex_id: str) -> FakeDEXProvider | None:
        if chain_id != self._chain.id:
            return None
        return next((p for p in self._providers if p.dex.id == dex_id), None)


# --------------------------------------------------------------------------- #
# Fixtures — parametrised by chain_id so tokens stay coherent with the chain   #
# --------------------------------------------------------------------------- #


SENDER = "0x0000000000000000000000000000000000000001"
ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def _token(symbol: str, address: str, decimals: int, chain_id: int = 1) -> Token:
    return Token(
        chain_id=chain_id,
        address=address,
        symbol=symbol,
        decimals=decimals,
    )


def _usdc(chain_id: int = 1) -> Token:
    return _token("USDC", USDC_ADDRESS, 6, chain_id)


def _weth(chain_id: int = 1) -> Token:
    return _token("WETH", WETH_ADDRESS, 18, chain_id)


def _chain(chain_id: int = 1) -> Chain:
    return Chain(
        id=chain_id,
        name="Ethereum" if chain_id == 1 else f"Chain{chain_id}",
        native_symbol="ETH",
        wrapped_native_address=WETH_ADDRESS,
    )


def _dex(dex_id: str, chain_id: int = 1) -> DEX:
    return DEX(
        id=dex_id,
        name=dex_id.title(),
        chain_id=chain_id,
        router_address=ROUTER,
        protocol=ProtocolVersion.V2,
    )


def _request(
    *,
    chain: Chain | None = None,
    preferred_dex_id: str | None = None,
) -> SwapRequest:
    resolved_chain = chain or _chain()
    return SwapRequest(
        chain=resolved_chain,
        token_in=_usdc(resolved_chain.id),
        token_out=_weth(resolved_chain.id),
        amount_in=1_000_000_000,
        sender=SENDER,
        slippage_bps=50,
        deadline_seconds=1200,
        preferred_dex_id=preferred_dex_id,
    )


def _fixed_clock() -> FixedClock:
    return FixedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #


def test_single_provider_happy_path():
    provider = FakeDEXProvider(_dex("uniswap_v2"), 400_000_000_000_000_000)
    orch = SwapOrchestrator(FakeRegistry(_chain(), [provider]), _fixed_clock())

    result = asyncio.run(orch.prepare_swap(_request()))

    assert result.status is SwapStatus.PREPARED
    assert result.params is not None
    assert result.params.amount_out_min == 400_000_000_000_000_000 * 9950 // 10_000
    # deadline = clock (2024-01-01T00:00:00Z) + 1200s
    assert result.params.deadline == 1_704_067_200 + 1200
    assert result.params.recipient == SENDER


def test_multiple_providers_picks_best():
    uni = FakeDEXProvider(_dex("uniswap_v2"), 400_000_000_000_000_000)
    sushi = FakeDEXProvider(_dex("sushiswap"), 420_000_000_000_000_000)
    orch = SwapOrchestrator(FakeRegistry(_chain(), [uni, sushi]), _fixed_clock())

    result = asyncio.run(orch.prepare_swap(_request()))

    assert result.quote is not None
    assert result.quote.dex.id == "sushiswap"
    assert uni.quote_calls == 1 and sushi.quote_calls == 1  # both queried


def test_preferred_dex_queried_alone():
    uni = FakeDEXProvider(_dex("uniswap_v2"), 400_000_000_000_000_000)
    sushi = FakeDEXProvider(_dex("sushiswap"), 420_000_000_000_000_000)
    orch = SwapOrchestrator(FakeRegistry(_chain(), [uni, sushi]), _fixed_clock())

    result = asyncio.run(
        orch.prepare_swap(_request(preferred_dex_id="uniswap_v2"))
    )

    assert result.quote is not None
    assert result.quote.dex.id == "uniswap_v2"
    assert uni.quote_calls == 1
    assert sushi.quote_calls == 0  # not called


def test_preferred_dex_not_available_raises():
    uni = FakeDEXProvider(_dex("uniswap_v2"), 400_000_000_000_000_000)
    orch = SwapOrchestrator(FakeRegistry(_chain(), [uni]), _fixed_clock())

    with pytest.raises(UnsupportedDexError):
        asyncio.run(orch.prepare_swap(_request(preferred_dex_id="pancakeswap")))


def test_unsupported_chain_raises():
    uni = FakeDEXProvider(_dex("uniswap_v2"), 400_000_000_000_000_000)
    orch = SwapOrchestrator(FakeRegistry(_chain(1), [uni]), _fixed_clock())

    # Chain 999 is not in the registry; tokens must be on chain 999 too so
    # that SwapRequest itself is valid and the error surfaces in the
    # orchestrator, not in the domain validation.
    with pytest.raises(UnsupportedChainError):
        asyncio.run(orch.prepare_swap(_request(chain=_chain(999))))


def test_partial_failure_tolerated():
    good = FakeDEXProvider(_dex("uniswap_v2"), 400_000_000_000_000_000)
    broken = FakeDEXProvider(
        _dex("sushiswap"), None, raises=ConnectionError("RPC timeout")
    )
    orch = SwapOrchestrator(
        FakeRegistry(_chain(), [good, broken]), _fixed_clock()
    )

    result = asyncio.run(orch.prepare_swap(_request()))

    assert result.quote is not None
    assert result.quote.dex.id == "uniswap_v2"


def test_all_providers_fail_raises_no_route():
    broken1 = FakeDEXProvider(_dex("uniswap_v2"), None, raises=ConnectionError("x"))
    broken2 = FakeDEXProvider(_dex("sushiswap"), None, raises=ConnectionError("y"))
    orch = SwapOrchestrator(
        FakeRegistry(_chain(), [broken1, broken2]), _fixed_clock()
    )

    with pytest.raises(NoRouteFoundError):
        asyncio.run(orch.prepare_swap(_request()))


def test_provider_returning_none_is_skipped():
    empty = FakeDEXProvider(_dex("uniswap_v2"), None)  # no route
    good = FakeDEXProvider(_dex("sushiswap"), 400_000_000_000_000_000)
    orch = SwapOrchestrator(
        FakeRegistry(_chain(), [empty, good]), _fixed_clock()
    )

    result = asyncio.run(orch.prepare_swap(_request()))
    assert result.quote is not None
    assert result.quote.dex.id == "sushiswap"
