"""Domain models for the swap platform.

Pure Python: no web3, no fasthtml, no network, no I/O.

Conventions
-----------
- Amounts are integer values in the token's smallest unit (wei-like).
- Human-readable rates/impacts use Decimal.
- Slippage uses basis points (1 bps = 0.01%; 10_000 bps = 100%).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .exceptions import (
    InvalidSwapRequestError,
    QuoteExpiredError,
    ValidationError,
)

BPS_DENOMINATOR = 10_000

#: Canonical pseudo-address recognised by most DEX routers for the native coin.
NATIVE_TOKEN_ADDRESS = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _validate_evm_address(address: str) -> None:
    if not isinstance(address, str) or not _EVM_ADDRESS_RE.match(address):
        raise ValidationError(f"Invalid EVM address: {address!r}")


class ProtocolVersion(str, Enum):
    V2 = "v2"
    V3 = "v3"
    V4 = "v4"


# --------------------------------------------------------------------------- #
# Entities                                                                     #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Chain:
    id: int
    name: str
    native_symbol: str
    wrapped_native_address: str  # WETH / WBNB / WMATIC
    block_explorer_url: str | None = None

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValidationError("Chain id must be positive")
        if not self.name:
            raise ValidationError("Chain name is required")
        if not self.native_symbol:
            raise ValidationError("Chain native_symbol is required")
        _validate_evm_address(self.wrapped_native_address)


@dataclass(frozen=True, slots=True)
class Token:
    chain_id: int
    address: str
    symbol: str
    decimals: int
    name: str | None = None

    def __post_init__(self) -> None:
        if self.decimals < 0 or self.decimals > 36:
            raise ValidationError(f"Invalid decimals: {self.decimals}")
        if not self.symbol:
            raise ValidationError("Token symbol is required")
        _validate_evm_address(self.address)

    @property
    def is_native(self) -> bool:
        return self.address.lower() == NATIVE_TOKEN_ADDRESS.lower()


@dataclass(frozen=True, slots=True)
class DEX:
    id: str
    name: str
    chain_id: int
    router_address: str
    protocol: ProtocolVersion
    factory_address: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValidationError("DEX id is required")
        if not self.name:
            raise ValidationError("DEX name is required")
        _validate_evm_address(self.router_address)
        if self.factory_address is not None:
            _validate_evm_address(self.factory_address)


# --------------------------------------------------------------------------- #
# Quote                                                                        #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Quote:
    token_in: Token
    token_out: Token
    amount_in: int
    amount_out: int
    dex: DEX
    price_impact: Decimal = Decimal("0")
    gas_estimate: int | None = None
    fee_amount: int | None = None
    path: tuple[Token, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 30

    def __post_init__(self) -> None:
        if self.amount_in <= 0:
            raise ValidationError("amount_in must be positive")
        if self.amount_out < 0:
            raise ValidationError("amount_out cannot be negative")
        if self.token_in.chain_id != self.token_out.chain_id:
            raise ValidationError("token_in and token_out must be on the same chain")
        if self.dex.chain_id != self.token_in.chain_id:
            raise ValidationError("dex must operate on the tokens' chain")
        if self.price_impact < 0:
            raise ValidationError("price_impact cannot be negative")
        if self.ttl_seconds <= 0:
            raise ValidationError("ttl_seconds must be positive")
        # Normalise naive datetimes so comparisons are always safe.
        if self.created_at.tzinfo is None:
            object.__setattr__(
                self,
                "created_at",
                self.created_at.replace(tzinfo=timezone.utc),
            )

    # -- queries ----------------------------------------------------------- #

    @property
    def is_expired(self) -> bool:
        age = (datetime.now(timezone.utc) - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def effective_price(self) -> Decimal:
        """Human-readable ratio ``token_out / token_in``.

        Returns ``Decimal(0)`` when it can't be computed.
        """
        if self.amount_in <= 0:
            return Decimal(0)
        in_human = Decimal(self.amount_in) / (Decimal(10) ** self.token_in.decimals)
        if in_human == 0:
            return Decimal(0)
        out_human = Decimal(self.amount_out) / (Decimal(10) ** self.token_out.decimals)
        return out_human / in_human

    # -- transitions ------------------------------------------------------- #

    def to_swap_params(
        self,
        *,
        slippage_bps: int,
        recipient: str,
        deadline: int,
    ) -> "SwapParams":
        """Freeze the quote into executable swap parameters.

        ``deadline`` is an absolute unix timestamp; the application layer is
        responsible for turning a relative deadline into an absolute one
        (the domain stays time-agnostic and deterministic).
        """
        if not 0 <= slippage_bps <= BPS_DENOMINATOR:
            raise InvalidSwapRequestError(
                f"slippage_bps must be within [0, {BPS_DENOMINATOR}], got {slippage_bps}"
            )
        _validate_evm_address(recipient)
        if deadline <= 0:
            raise InvalidSwapRequestError("deadline must be a positive unix timestamp")
        if self.is_expired:
            raise QuoteExpiredError(
                f"Quote from {self.dex.id} expired (ttl={self.ttl_seconds}s)"
            )

        amount_out_min = (
            self.amount_out * (BPS_DENOMINATOR - slippage_bps) // BPS_DENOMINATOR
        )
        return SwapParams(
            token_in=self.token_in,
            token_out=self.token_out,
            amount_in=self.amount_in,
            amount_out_min=amount_out_min,
            recipient=recipient,
            deadline=deadline,
            path=self.path or (self.token_in, self.token_out),
            dex=self.dex,
        )


# --------------------------------------------------------------------------- #
# Swap request / params / result                                               #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SwapRequest:
    chain: Chain
    token_in: Token
    token_out: Token
    amount_in: int
    sender: str
    slippage_bps: int = 50
    recipient: str | None = None  # defaults to sender
    preferred_dex_id: str | None = None
    deadline_seconds: int = 1200

    def __post_init__(self) -> None:
        if self.amount_in <= 0:
            raise InvalidSwapRequestError("amount_in must be positive")
        if self.token_in.chain_id != self.chain.id:
            raise InvalidSwapRequestError("token_in must belong to the request chain")
        if self.token_out.chain_id != self.chain.id:
            raise InvalidSwapRequestError("token_out must belong to the request chain")
        if not 0 <= self.slippage_bps <= BPS_DENOMINATOR:
            raise InvalidSwapRequestError(
                f"slippage_bps must be within [0, {BPS_DENOMINATOR}]"
            )
        if self.deadline_seconds <= 0:
            raise InvalidSwapRequestError("deadline_seconds must be positive")
        _validate_evm_address(self.sender)
        if self.recipient is not None:
            _validate_evm_address(self.recipient)

    @property
    def effective_recipient(self) -> str:
        return self.recipient or self.sender


@dataclass(frozen=True, slots=True)
class SwapParams:
    """DEX-agnostic parameters ready to be encoded by an adapter."""

    token_in: Token
    token_out: Token
    amount_in: int
    amount_out_min: int
    recipient: str
    deadline: int
    path: tuple[Token, ...]
    dex: DEX

    def __post_init__(self) -> None:
        if self.amount_in <= 0:
            raise ValidationError("amount_in must be positive")
        if self.amount_out_min < 0:
            raise ValidationError("amount_out_min cannot be negative")
        if self.deadline <= 0:
            raise ValidationError("deadline must be positive")
        _validate_evm_address(self.recipient)
        if len(self.path) < 2:
            raise ValidationError("path must contain at least token_in and token_out")


class SwapStatus(str, Enum):
    PREPARED = "prepared"
    SENT = "sent"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SwapResult:
    status: SwapStatus
    quote: Quote | None = None
    params: SwapParams | None = None
    tx_hash: str | None = None
    error: str | None = None
