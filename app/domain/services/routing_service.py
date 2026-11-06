"""Routing: pick which quote the platform will execute.

Still pure: consumes quotes + a SwapRequest and returns a Quote. Turning
that quote into a transaction is the application layer's job.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..exceptions import NoRouteFoundError, UnsupportedDexError
from ..models import Quote, SwapRequest
from . import quote_service


def select_quote(quotes: Iterable[Quote], request: SwapRequest) -> Quote:
    """Choose the best quote, honouring an explicit DEX preference if any."""
    candidates = quote_service.filter_valid(quotes)

    if request.preferred_dex_id is not None:
        candidates = [q for q in candidates if q.dex.id == request.preferred_dex_id]
        if not candidates:
            raise UnsupportedDexError(
                f"DEX '{request.preferred_dex_id}' produced no valid quote for "
                f"{request.token_in.symbol}->{request.token_out.symbol} "
                f"on chain {request.chain.id}"
            )

    if not candidates:
        raise NoRouteFoundError(
            f"No route for {request.token_in.symbol}->{request.token_out.symbol} "
            f"on chain {request.chain.id}"
        )

    return quote_service.rank(candidates)[0]
