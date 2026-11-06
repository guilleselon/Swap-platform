"""The ``prepare_swap`` use case.

Flow:
    1. Validate chain is supported (via ChainRegistry).
    2. Collect available DEX providers for the chain.
    3. Fetch quotes concurrently, tolerating individual DEX failures.
    4. Delegate ranking/selection to the pure domain (routing_service).
    5. Convert the winning Quote into SwapParams (freezing deadline).
    6. Return a SwapResult(PREPARED).

No I/O here: all side effects go through the injected ports.
"""

from __future__ import annotations

import asyncio
import logging

from app.domain.exceptions import (
    NoRouteFoundError,
    UnsupportedChainError,
    UnsupportedDexError,
)
from app.domain.models import Quote, SwapRequest, SwapResult, SwapStatus, Token
from app.domain.services import routing_service

from .ports import ChainRegistry, Clock, DEXProvider

logger = logging.getLogger(__name__)


class SwapOrchestrator:
    def __init__(self, registry: ChainRegistry, clock: Clock) -> None:
        self._registry = registry
        self._clock = clock

    # -- public API -------------------------------------------------------- #

    async def get_quotes(
        self,
        chain_id: int,
        token_in: Token,
        token_out: Token,
        amount_in: int,
        *,
        preferred_dex_id: str | None = None,
    ) -> list[Quote]:
        """Fetch ALL quotes for a pair. Does not select a winner.

        Used by the ``/api/quotes`` endpoint so the UI can display the
        full comparison table. Raises ``UnsupportedChainError`` /
        ``UnsupportedDexError`` for invalid input; returns ``[]`` when no
        DEX produced a route.
        """
        chain = self._registry.get_chain(chain_id)
        if chain is None:
            raise UnsupportedChainError(
                f"Chain id {chain_id} is not supported"
            )
        providers = self._registry.list_dex_providers(chain_id)
        if not providers:
            raise UnsupportedChainError(
                f"No DEX providers configured for chain {chain_id}"
            )
        return await self._collect_quotes(
            token_in, token_out, amount_in, providers, preferred_dex_id
        )

    async def prepare_swap(self, request: SwapRequest) -> SwapResult:
        quotes = await self.get_quotes(
            request.chain.id,
            request.token_in,
            request.token_out,
            request.amount_in,
            preferred_dex_id=request.preferred_dex_id,
        )
        if not quotes:
            raise NoRouteFoundError(
                f"No route for {request.token_in.symbol}->{request.token_out.symbol} "
                f"on chain {request.chain.id}"
            )

        chosen = routing_service.select_quote(quotes, request)

        deadline = int(self._clock.now().timestamp()) + request.deadline_seconds
        params = chosen.to_swap_params(
            slippage_bps=request.slippage_bps,
            recipient=request.effective_recipient,
            deadline=deadline,
        )

        return SwapResult(
            status=SwapStatus.PREPARED,
            quote=chosen,
            params=params,
        )

    # -- internals --------------------------------------------------------- #

    async def _collect_quotes(
        self,
        token_in: Token,
        token_out: Token,
        amount_in: int,
        providers: list[DEXProvider],
        preferred_dex_id: str | None,
    ) -> list[Quote]:
        # Explicit DEX requested: query only that one.
        if preferred_dex_id is not None:
            target = next(
                (p for p in providers if p.dex.id == preferred_dex_id), None
            )
            if target is None:
                raise UnsupportedDexError(
                    f"DEX '{preferred_dex_id}' is not available on this chain"
                )
            quote = await target.get_quote(token_in, token_out, amount_in)
            return [quote] if quote is not None else []

        # Open mode: fan out concurrently, tolerate individual failures.
        results = await asyncio.gather(
            *(
                p.get_quote(token_in, token_out, amount_in)
                for p in providers
            ),
            return_exceptions=True,
        )

        quotes: list[Quote] = []
        for provider, result in zip(providers, results):
            if isinstance(result, BaseException):
                logger.warning(
                    "DEX %s failed while quoting %s->%s: %s",
                    provider.dex.id,
                    token_in.symbol,
                    token_out.symbol,
                    result,
                )
                continue
            if result is not None:
                quotes.append(result)
        return quotes
