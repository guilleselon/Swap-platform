"""Ports (interfaces) the application layer needs from the outside world.

Defined with ``typing.Protocol`` so any object matching the signature works
— no inheritance needed. The application depends only on these contracts;
concrete adapters live in ``infrastructure/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.models import DEX, Chain, Quote, SwapParams, Token


# --------------------------------------------------------------------------- #
# DTOs crossing the application <-> infrastructure boundary                    #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class TransactionRequest:
    """EVM-agnostic envelope for a transaction to be signed & broadcast.

    This is an *application-layer DTO*, not a domain object: it carries
    encoding concerns (calldata, chain id, gas) the domain must not know.
    """

    chain_id: int
    to: str
    data: str  # 0x-prefixed hex calldata
    value: int = 0
    gas: int | None = None
    gas_price: int | None = None
    nonce: int | None = None


# --------------------------------------------------------------------------- #
# Ports                                                                        #
# --------------------------------------------------------------------------- #


@runtime_checkable
class Clock(Protocol):
    """Deterministic access to 'now'. Injected so tests can freeze time."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC datetime."""
        ...


@runtime_checkable
class DEXProvider(Protocol):
    """A single DEX adapter the orchestrator can query.

    Contract:
    - ``get_quote`` returns ``None`` when the DEX has no route.
    - It may raise domain exceptions (``InsufficientLiquidityError``, etc.)
      or infrastructure exceptions on transport failures.
    """

    @property
    def dex(self) -> DEX: ...

    async def get_quote(
        self,
        token_in: Token,
        token_out: Token,
        amount_in: int,
        *,
        path: tuple[Token, ...] | None = None,
    ) -> Quote | None: ...

    async def build_swap_tx(
        self,
        params: SwapParams,
        *,
        sender: str,
    ) -> TransactionRequest:
        """Encode ``params`` into a signable EVM transaction for this DEX."""
        ...


@runtime_checkable
class ChainRegistry(Protocol):
    """Knows which chains and DEX providers are available."""

    def get_chain(self, chain_id: int) -> Chain | None: ...

    def list_chains(self) -> list[Chain]:
        """Return all chains that have at least one usable DEX provider."""
        ...

    def list_dex_providers(self, chain_id: int) -> list[DEXProvider]: ...

    def get_dex_provider(self, chain_id: int, dex_id: str) -> DEXProvider | None: ...
