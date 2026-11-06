"""Uniswap V2 compatible DEX adapter.

Works for Uniswap V2, SushiSwap, PancakeSwap V2, QuickSwap, and any other
router that implements the canonical V2 interface.
"""

from __future__ import annotations

from decimal import Decimal

from web3 import AsyncWeb3

from app.application.ports import TransactionRequest
from app.domain.exceptions import ValidationError
from app.domain.models import Chain, DEX, Quote, SwapParams, Token
from app.infrastructure.blockchain.abis import (
    UNISWAP_V2_FACTORY_ABI,
    UNISWAP_V2_PAIR_ABI,
    UNISWAP_V2_ROUTER_ABI,
)
from app.infrastructure.blockchain.web3_client import Web3Client

_ZERO_ADDRESS = "0x" + "0" * 40


class UniswapV2Provider:
    def __init__(self, dex: DEX, chain: Chain, w3_client: Web3Client) -> None:
        if dex.factory_address is None:
            raise ValidationError(
                f"DEX {dex.id} requires factory_address for UniswapV2Provider"
            )
        self._dex = dex
        self._chain = chain
        self._w3_client = w3_client

    # -- DEXProvider protocol ------------------------------------------------- #

    @property
    def dex(self) -> DEX:
        return self._dex

    async def get_quote(
        self,
        token_in: Token,
        token_out: Token,
        amount_in: int,
        *,
        path: tuple[Token, ...] | None = None,
    ) -> Quote | None:
        if amount_in <= 0:
            return None

        w3 = self._w3_client.get(self._dex.chain_id)
        path_tokens = path or await self._compute_path(w3, token_in, token_out)
        if path_tokens is None:
            return None

        path_addresses = [self._normalize(t.address) for t in path_tokens]
        router = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(self._dex.router_address),
            abi=UNISWAP_V2_ROUTER_ABI,
        )

        try:
            amounts = await router.functions.getAmountsOut(
                amount_in, path_addresses
            ).call()
        except Exception:
            return None  # revert / no liquidity / RPC hiccup

        if not amounts or amounts[-1] <= 0:
            return None

        impact = await self._estimate_price_impact(w3, path_addresses, amounts)

        return Quote(
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            amount_out=int(amounts[-1]),
            dex=self._dex,
            price_impact=impact,
            path=path_tokens,
        )

    async def build_swap_tx(
        self,
        params: SwapParams,
        *,
        sender: str,
    ) -> TransactionRequest:
        w3 = self._w3_client.get(self._dex.chain_id)
        router = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(self._dex.router_address),
            abi=UNISWAP_V2_ROUTER_ABI,
        )
        path_addresses = [self._normalize(t.address) for t in params.path]

        # web3.py requires EIP-55 checksum for every `address` ABI argument.
        # The user's wallet may return lowercase; normalise before encoding.
        recipient = AsyncWeb3.to_checksum_address(params.recipient)

        if params.token_in.is_native:
            data = router.encode_abi(
                "swapExactETHForTokens",
                args=[
                    params.amount_out_min,
                    path_addresses,
                    recipient,
                    params.deadline,
                ],
            )
            value = params.amount_in
        elif params.token_out.is_native:
            data = router.encode_abi(
                "swapExactTokensForETH",
                args=[
                    params.amount_in,
                    params.amount_out_min,
                    path_addresses,
                    recipient,
                    params.deadline,
                ],
            )
            value = 0
        else:
            data = router.encode_abi(
                "swapExactTokensForTokens",
                args=[
                    params.amount_in,
                    params.amount_out_min,
                    path_addresses,
                    recipient,
                    params.deadline,
                ],
            )
            value = 0

        return TransactionRequest(
            chain_id=self._dex.chain_id,
            to=self._dex.router_address,
            data=data,
            value=value,
        )
    # -- internals ------------------------------------------------------------ #

    def _normalize(self, address: str) -> str:
        """Map the native pseudo-address to the chain's wrapped native token."""
        if address.lower() == "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee":
            return AsyncWeb3.to_checksum_address(
                self._chain.wrapped_native_address
            )
        return AsyncWeb3.to_checksum_address(address)

    def _wrapped_native_token(self) -> Token:
        return Token(
            chain_id=self._chain.id,
            address=self._chain.wrapped_native_address,
            symbol="W" + self._chain.native_symbol,
            decimals=18,
        )

    async def _compute_path(
        self,
        w3: AsyncWeb3,
        token_in: Token,
        token_out: Token,
    ) -> tuple[Token, ...] | None:
        in_addr = self._normalize(token_in.address)
        out_addr = self._normalize(token_out.address)

        factory = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(self._dex.factory_address),
            abi=UNISWAP_V2_FACTORY_ABI,
        )

        # 1) Direct pair
        direct = await factory.functions.getPair(in_addr, out_addr).call()
        if direct != _ZERO_ADDRESS:
            return (token_in, token_out)

        # 2) Route via wrapped native (WETH/WBNB/WMATIC)
        wrapped = self._wrapped_native_token()
        w_addr = self._normalize(wrapped.address)
        if in_addr == w_addr or out_addr == w_addr:
            return None

        pair_a = await factory.functions.getPair(in_addr, w_addr).call()
        pair_b = await factory.functions.getPair(w_addr, out_addr).call()
        if pair_a != _ZERO_ADDRESS and pair_b != _ZERO_ADDRESS:
            return (token_in, wrapped, token_out)

        return None

    async def _estimate_price_impact(
        self,
        w3: AsyncWeb3,
        path_addresses: list[str],
        amounts: list[int],
    ) -> Decimal:
        """Approximate aggregate price impact across hops.

        For each hop: impact = 1 - (amount_out * reserve_in) / (amount_in * reserve_out).
        Multi-hop impacts are summed (small-amount approximation).
        """
        factory = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(self._dex.factory_address),
            abi=UNISWAP_V2_FACTORY_ABI,
        )
        total = Decimal(0)

        for i in range(len(path_addresses) - 1):
            in_addr = path_addresses[i]
            out_addr = path_addresses[i + 1]
            pair_addr = await factory.functions.getPair(in_addr, out_addr).call()
            if pair_addr == _ZERO_ADDRESS:
                return Decimal(0)

            pair = w3.eth.contract(
                address=AsyncWeb3.to_checksum_address(pair_addr),
                abi=UNISWAP_V2_PAIR_ABI,
            )
            token0 = await pair.functions.token0().call()
            reserves = await pair.functions.getReserves().call()
            reserve0, reserve1 = reserves[0], reserves[1]
            if token0.lower() == in_addr.lower():
                reserve_in, reserve_out = reserve0, reserve1
            else:
                reserve_in, reserve_out = reserve1, reserve0

            if reserve_in == 0 or reserve_out == 0:
                return Decimal(0)

            amount_in_hop = amounts[i]
            amount_out_hop = amounts[i + 1]
            if amount_in_hop == 0:
                continue

            spot = Decimal(reserve_out) / Decimal(reserve_in)
            effective = Decimal(amount_out_hop) / Decimal(amount_in_hop)
            hop_impact = (spot - effective) / spot
            if hop_impact > 0:
                total += hop_impact

        return total
