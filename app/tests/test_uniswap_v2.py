"""Unit tests for UniswapV2Provider using mocked Web3 calls.

Mocks strategy
--------------
- Each contract function (``getPair``, ``getAmountsOut``, ``token0``,
  ``getReserves``) is a ``MagicMock`` with a ``side_effect`` that returns
  a ``_callable(result)`` — i.e. an object whose ``.call()`` is an
  ``AsyncMock`` returning ``result``. This mirrors web3.py's API exactly:
  ``contract.functions.fn(args).call()`` is awaitable.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from web3 import AsyncWeb3

from app.domain.models import (
    Chain,
    DEX,
    ProtocolVersion,
    SwapParams,
    Token,
)
from app.infrastructure.dex_providers.uniswap_v2 import UniswapV2Provider

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
FACTORY = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
PAIR = "0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc"
ZERO = "0x" + "0" * 40
WETH_ADDR = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDC_ADDR = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
DAI_ADDR = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
SENDER = "0x0000000000000000000000000000000000000001"

CHAIN = Chain(
    id=1,
    name="Ethereum",
    native_symbol="ETH",
    wrapped_native_address=WETH_ADDR,
)
DEX_ = DEX(
    id="uniswap_v2",
    name="Uniswap V2",
    chain_id=1,
    router_address=ROUTER,
    factory_address=FACTORY,
    protocol=ProtocolVersion.V2,
)
USDC = Token(chain_id=1, address=USDC_ADDR, symbol="USDC", decimals=6)
WETH = Token(chain_id=1, address=WETH_ADDR, symbol="WETH", decimals=18)
DAI = Token(chain_id=1, address=DAI_ADDR, symbol="DAI", decimals=18)
NATIVE = Token(
    chain_id=1,
    address="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
    symbol="ETH",
    decimals=18,
)

# --------------------------------------------------------------------------- #
# Mock builders                                                                #
# --------------------------------------------------------------------------- #


class FakeWeb3Client:
    def __init__(self, w3) -> None:
        self._w3 = w3

    def get(self, chain_id: int):
        return self._w3

    def supported_chain_ids(self) -> list[int]:
        return [1]


def _callable(result) -> MagicMock:
    """Object whose ``.call()`` is an ``AsyncMock(return_value=result)``."""
    m = MagicMock()
    m.call = AsyncMock(return_value=result)
    return m


def _callable_raises(exc: Exception) -> MagicMock:
    m = MagicMock()
    m.call = AsyncMock(side_effect=exc)
    return m


def _make_w3(
    *,
    pairs: dict[tuple[str, str], str] | None = None,
    amounts_out: list[int] | None = None,
    amounts_out_raises: bool = False,
    token0: str = USDC_ADDR,
    reserves: tuple[int, int] = (10**15, 4 * 10**20),
) -> MagicMock:
    """Build a mocked ``AsyncWeb3`` with functional ``contract().functions``.

    ``pairs`` maps ``(addr_a_lower, addr_b_lower)`` (order-insensitive) to
    the pair contract address. Missing pairs return ``ZERO``.
    """
    pairs = {
        (a.lower(), b.lower()): addr
        for (a, b), addr in (pairs or {}).items()
    }

    def pair_for(addr_a: str, addr_b: str) -> str:
        key = (addr_a.lower(), addr_b.lower())
        return pairs.get(key) or pairs.get((key[1], key[0])) or ZERO

    # -- router -------------------------------------------------------------
    router = MagicMock()
    if amounts_out_raises:
        router.functions.getAmountsOut.side_effect = (
            lambda *_a, **_k: _callable_raises(Exception("execution reverted"))
        )
    else:
        default_out = amounts_out or [1_000 * 10**6, 4 * 10**17]
        router.functions.getAmountsOut.side_effect = (
            lambda amount_in, path: _callable(default_out)
        )

    # -- factory ------------------------------------------------------------
    factory = MagicMock()
    factory.functions.getPair.side_effect = (
        lambda a, b: _callable(pair_for(a, b))
    )

    # -- pair ---------------------------------------------------------------
    pair = MagicMock()
    pair.functions.token0.side_effect = lambda: _callable(token0)
    pair.functions.getReserves.side_effect = (
        lambda: _callable((reserves[0], reserves[1], 0))
    )

    # -- web3 ---------------------------------------------------------------
    w3 = MagicMock()

    def contract(address, abi):
        addr = address.lower() if isinstance(address, str) else address
        if addr == ROUTER.lower():
            return router
        if addr == FACTORY.lower():
            return factory
        return pair

    w3.eth.contract.side_effect = contract
    return w3


# --------------------------------------------------------------------------- #
# get_quote                                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_quote_direct_pair():
    w3 = _make_w3(
        pairs={(USDC_ADDR, WETH_ADDR): PAIR},
        amounts_out=[1_000 * 10**6, 4 * 10**17],
        token0=USDC_ADDR,
        reserves=(1_000_000 * 10**6, 400 * 10**18),
    )
    provider = UniswapV2Provider(DEX_, CHAIN, FakeWeb3Client(w3))

    quote = await provider.get_quote(USDC, WETH, 1_000 * 10**6)

    assert quote is not None
    assert quote.amount_out == 4 * 10**17
    assert quote.dex.id == "uniswap_v2"
    assert quote.path == (USDC, WETH)
    assert quote.price_impact >= 0  # estimation is 0 for the above numbers


@pytest.mark.asyncio
async def test_get_quote_returns_none_when_no_path():
    # No pairs at all -> direct missing AND USDC->WETH is native-wrapped, no bridge.
    w3 = _make_w3(pairs={})
    provider = UniswapV2Provider(DEX_, CHAIN, FakeWeb3Client(w3))

    quote = await provider.get_quote(USDC, WETH, 1_000 * 10**6)
    assert quote is None


@pytest.mark.asyncio
async def test_get_quote_returns_none_when_amounts_out_reverts():
    w3 = _make_w3(
        pairs={(USDC_ADDR, WETH_ADDR): PAIR},
        amounts_out_raises=True,
    )
    provider = UniswapV2Provider(DEX_, CHAIN, FakeWeb3Client(w3))

    quote = await provider.get_quote(USDC, WETH, 1_000 * 10**6)
    assert quote is None


@pytest.mark.asyncio
async def test_get_quote_routes_via_weth():
    # USDC and DAI both have a pair against WETH, but none directly.
    w3 = _make_w3(
        pairs={
            (USDC_ADDR, WETH_ADDR): PAIR,
            (WETH_ADDR, DAI_ADDR): PAIR,
        },
        amounts_out=[1_000 * 10**6, 4 * 10**17, 400 * 10**18],
        token0=USDC_ADDR,
        reserves=(1_000_000 * 10**6, 400 * 10**18),
    )
    provider = UniswapV2Provider(DEX_, CHAIN, FakeWeb3Client(w3))

    quote = await provider.get_quote(USDC, DAI, 1_000 * 10**6)

    assert quote is not None
    assert len(quote.path) == 3
    assert quote.path[0].symbol == "USDC"
    assert quote.path[1].symbol == "WETH"
    assert quote.path[2].symbol == "DAI"


# --------------------------------------------------------------------------- #
# build_swap_tx                                                                #
# --------------------------------------------------------------------------- #


def _real_w3_for_encoding() -> AsyncWeb3:
    """A real AsyncWeb3 whose ``contract().encode_abi`` works offline."""
    return AsyncWeb3(AsyncWeb3.AsyncHTTPProvider("http://127.0.0.1:0"))


def _make_params(token_in: Token, token_out: Token, *, path=None) -> SwapParams:
    return SwapParams(
        token_in=token_in,
        token_out=token_out,
        amount_in=1_000 * 10**6,
        amount_out_min=4 * 10**17 * 9950 // 10_000,
        recipient=SENDER,
        deadline=2_000_000_000,
        path=path or (token_in, token_out),
        dex=DEX_,
    )


@pytest.mark.asyncio
async def test_build_swap_tx_erc20_to_erc20():
    provider = UniswapV2Provider(
        DEX_, CHAIN, FakeWeb3Client(_real_w3_for_encoding())
    )
    tx = await provider.build_swap_tx(
        _make_params(USDC, WETH), sender=SENDER
    )

    assert tx.to == ROUTER
    assert tx.value == 0
    assert tx.data.startswith("0x38ed1739")  # swapExactTokensForTokens


@pytest.mark.asyncio
async def test_build_swap_tx_native_in():
    provider = UniswapV2Provider(
        DEX_, CHAIN, FakeWeb3Client(_real_w3_for_encoding())
    )
    tx = await provider.build_swap_tx(
        _make_params(NATIVE, USDC), sender=SENDER
    )

    assert tx.value == 1_000 * 10**6
    assert tx.data.startswith("0x7ff36ab5")  # swapExactETHForTokens
    # Native pseudo-address must be rewritten to WETH in calldata.
    assert WETH_ADDR[2:].lower() in tx.data.lower()
    assert "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" not in tx.data.lower()


@pytest.mark.asyncio
async def test_build_swap_tx_native_out():
    provider = UniswapV2Provider(
        DEX_, CHAIN, FakeWeb3Client(_real_w3_for_encoding())
    )
    tx = await provider.build_swap_tx(
        _make_params(USDC, NATIVE), sender=SENDER
    )

    assert tx.value == 0
    assert tx.data.startswith("0x18cbafe5")  # swapExactTokensForETH
    assert WETH_ADDR[2:].lower() in tx.data.lower()

@pytest.mark.asyncio
async def test_build_swap_tx_lowercase_recipient_is_normalized():
    """Regression: web3.py rejects non-checksummed addresses in encode_abi."""
    provider = UniswapV2Provider(
        DEX_, CHAIN, FakeWeb3Client(_real_w3_for_encoding())
    )
    lower_sender = SENDER.lower()  # e.g. 0x0000...0001
    params = SwapParams(
        token_in=NATIVE,
        token_out=USDC,
        amount_in=1_000 * 10**6,
        amount_out_min=400_000 * 10**6,
        recipient=lower_sender,     # lowercase on purpose
        deadline=2_000_000_000,
        path=(NATIVE, USDC),
        dex=DEX_,
    )

    # Before the fix this raised web3.exceptions.InvalidAddress.
    tx = await provider.build_swap_tx(params, sender=lower_sender)
    assert tx.data.startswith("0x7ff36ab5")  # swapExactETHForTokens

@pytest.mark.asyncio
async def test_build_swap_tx_erc20_lowercase_recipient():
    provider = UniswapV2Provider(
        DEX_, CHAIN, FakeWeb3Client(_real_w3_for_encoding())
    )
    lower_sender = SENDER.lower()
    params = SwapParams(
        token_in=USDC,
        token_out=WETH,
        amount_in=1_000 * 10**6,
        amount_out_min=4 * 10**17 * 9950 // 10_000,
        recipient=lower_sender,
        deadline=2_000_000_000,
        path=(USDC, WETH),
        dex=DEX_,
    )
    tx = await provider.build_swap_tx(params, sender=lower_sender)
    assert tx.data.startswith("0x38ed1739")  # swapExactTokensForTokens
