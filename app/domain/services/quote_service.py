"""Pure comparison of quotes.

No I/O: takes Quote objects in, returns Quote objects out. Safe to unit
test without any network or chain mock.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..exceptions import NoRouteFoundError
from ..models import Quote


def filter_valid(quotes: Iterable[Quote]) -> list[Quote]:
    """Drop expired quotes and those that produced zero output."""
    return [q for q in quotes if not q.is_expired and q.amount_out > 0]


def rank(quotes: Iterable[Quote]) -> list[Quote]:
    """Sort by descending effective price (best output per unit of input)."""
    return sorted(quotes, key=lambda q: q.effective_price(), reverse=True)


def best(quotes: Iterable[Quote]) -> Quote:
    """Return the single best quote or raise NoRouteFoundError."""
    valid = filter_valid(quotes)
    if not valid:
        raise NoRouteFoundError("No valid quotes were produced")
    return rank(valid)[0]
