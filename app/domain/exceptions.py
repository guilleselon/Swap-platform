"""Domain-level exceptions.

Zero dependencies: this module must not import web3, fasthtml, requests,
or any infrastructure library. It's the shared vocabulary of errors for
the whole domain.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every business error raised by the platform."""


class ValidationError(DomainError):
    """A domain model was constructed with invalid data."""


class InvalidSwapRequestError(DomainError):
    """The swap request is structurally invalid (bad slippage, zero amount...)."""


class UnsupportedChainError(DomainError):
    """The requested chain is not supported by the platform."""


class UnsupportedDexError(DomainError):
    """The requested DEX is not available/usable for this pair."""


class InsufficientLiquidityError(DomainError):
    """No pool has enough liquidity to satisfy the request."""


class NoRouteFoundError(DomainError):
    """No DEX produced a usable quote for this pair."""


class QuoteExpiredError(DomainError):
    """A quote was used after its TTL elapsed."""
