"""Tests for the pure domain layer.

Run with:
    pytest app/tests/test_domain.py -q

Requires nothing but pytest + stdlib.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain import (
    Chain,
    DEX,
    ProtocolVersion,
    Quote,
    SwapRequest,
    UnsupportedDexError,
)
from app.domain.exceptions import NoRouteFoundError
from app.domain.models import Token
from app.domain.services import quote_service, routing_service

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _chain() -> Chain:
    return Chain(
        id=1,
        name="Ethereum",
        native_symbol="ETH",
        wrapped_native_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
    )


def _token(symbol: str, address: str, decimals: int) -> Token:
    return Token(chain_id=1, address=address, symbol=symbol, decimals=decimals)


USDC = _token("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6)
WETH = _token("WETH", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", 18)
SENDER = "0x0000000000000000000000000000000000000001"


def _dex(dex_id: str) -> DEX:
    return DEX(
        id=dex_id,
        name=dex_id,
        chain_id=1,
        router_address="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        protocol=ProtocolVersion.V2,
    )


def _quote(dex_id: str, amount_out: int, *, age_seconds: int = 0) -> Quote:
    return Quote(
        token_in=USDC,
        token_out=WETH,
        amount_in=1_000_000_000,  # 1_000 USDC
        amount_out=amount_out,
        dex=_dex(dex_id),
        created_at=datetime.now(timezone.utc) - timedelta(seconds=age_seconds),
        ttl_seconds=30,
    )


def _request(preferred_dex_id: str | None = None) -> SwapRequest:
    return SwapRequest(
        chain=_chain(),
        token_in=USDC,
        token_out=WETH,
        amount_in=1_000_000_000,
        sender=SENDER,
        preferred_dex_id=preferred_dex_id,
    )


# --------------------------------------------------------------------------- #
# quote_service                                                                #
# --------------------------------------------------------------------------- #


def test_rank_picks_highest_output():
    q_uni = _quote("uniswap_v2", 400_000_000_000_000_000)   # 0.40 WETH
    q_sushi = _quote("sushiswap",  410_000_000_000_000_000) # 0.41 WETH
    assert quote_service.best([q_uni, q_sushi]).dex.id == "sushiswap"


def test_expired_quotes_are_ignored_even_if_better():
    fresh = _quote("uniswap_v2", 400_000_000_000_000_000)
    stale = _quote("sushiswap", 999_000_000_000_000_000, age_seconds=120)
    assert quote_service.best([fresh, stale]).dex.id == "uniswap_v2"


def test_no_valid_quotes_raises():
    with pytest.raises(NoRouteFoundError):
        quote_service.best([])


# --------------------------------------------------------------------------- #
# routing_service                                                              #
# --------------------------------------------------------------------------- #


def test_routing_respects_preferred_dex():
    q_uni = _quote("uniswap_v2", 400_000_000_000_000_000)
    q_sushi = _quote("sushiswap", 410_000_000_000_000_000)
    chosen = routing_service.select_quote([q_uni, q_sushi], _request("uniswap_v2"))
    assert chosen.dex.id == "uniswap_v2"


def test_routing_raises_when_preferred_dex_is_missing():
    q_uni = _quote("uniswap_v2", 400_000_000_000_000_000)
    with pytest.raises(UnsupportedDexError):
        routing_service.select_quote([q_uni], _request("pancakeswap"))


# --------------------------------------------------------------------------- #
# Quote -> SwapParams                                                          #
# --------------------------------------------------------------------------- #


def test_to_swap_params_applies_slippage():
    q = _quote("uniswap_v2", 400_000_000_000_000_000)
    params = q.to_swap_params(
        slippage_bps=50,  # 0.5 %
        recipient=SENDER,
        deadline=2_000_000_000,
    )
    assert params.amount_out_min == 400_000_000_000_000_000 * 9950 // 10_000
    assert params.path == (USDC, WETH)
