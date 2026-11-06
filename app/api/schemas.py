"""Pydantic schemas for the HTTP API.

Amount/wei fields are serialized as strings because they routinely exceed
JavaScript's safe integer limit (2^53). The frontend must use BigInt().
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application.ports import TransactionRequest
from app.domain.models import (
    Chain,
    DEX,
    Quote,
    SwapParams,
    SwapRequest,
    SwapResult,
    Token,
)


# --------------------------------------------------------------------------- #
# Domain-facing DTOs (response)                                                #
# --------------------------------------------------------------------------- #


class TokenDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain_id: int
    address: str
    symbol: str
    decimals: int
    name: str | None = None

    @classmethod
    def from_domain(cls, token: Token) -> "TokenDTO":
        return cls(
            chain_id=token.chain_id,
            address=token.address,
            symbol=token.symbol,
            decimals=token.decimals,
            name=token.name,
        )

    def to_domain(self) -> Token:
        return Token(
            chain_id=self.chain_id,
            address=self.address,
            symbol=self.symbol,
            decimals=self.decimals,
            name=self.name,
        )


class DexDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    chain_id: int
    protocol: str
    router_address: str
    factory_address: str | None = None

    @classmethod
    def from_domain(cls, dex: DEX) -> "DexDTO":
        return cls(
            id=dex.id,
            name=dex.name,
            chain_id=dex.chain_id,
            protocol=dex.protocol.value,
            router_address=dex.router_address,
            factory_address=dex.factory_address,
        )


class ChainDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    native_symbol: str
    wrapped_native_address: str
    block_explorer_url: str | None = None

    @classmethod
    def from_domain(cls, chain: Chain) -> "ChainDTO":
        return cls(
            id=chain.id,
            name=chain.name,
            native_symbol=chain.native_symbol,
            wrapped_native_address=chain.wrapped_native_address,
            block_explorer_url=chain.block_explorer_url,
        )


class QuoteDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    token_in: TokenDTO
    token_out: TokenDTO
    amount_in: str
    amount_out: str
    dex: DexDTO
    price_impact: str
    effective_price: str
    path_symbols: list[str]
    gas_estimate: int | None = None
    fee_amount: str | None = None
    created_at: datetime
    ttl_seconds: int

    @classmethod
    def from_domain(cls, quote: Quote) -> "QuoteDTO":
        return cls(
            token_in=TokenDTO.from_domain(quote.token_in),
            token_out=TokenDTO.from_domain(quote.token_out),
            amount_in=str(quote.amount_in),
            amount_out=str(quote.amount_out),
            dex=DexDTO.from_domain(quote.dex),
            price_impact=str(quote.price_impact),
            effective_price=str(quote.effective_price()),
            path_symbols=[t.symbol for t in quote.path],
            gas_estimate=quote.gas_estimate,
            fee_amount=str(quote.fee_amount) if quote.fee_amount is not None else None,
            created_at=quote.created_at,
            ttl_seconds=quote.ttl_seconds,
        )


class SwapParamsDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    token_in: TokenDTO
    token_out: TokenDTO
    amount_in: str
    amount_out_min: str
    recipient: str
    deadline: int
    dex_id: str

    @classmethod
    def from_domain(cls, params: SwapParams) -> "SwapParamsDTO":
        return cls(
            token_in=TokenDTO.from_domain(params.token_in),
            token_out=TokenDTO.from_domain(params.token_out),
            amount_in=str(params.amount_in),
            amount_out_min=str(params.amount_out_min),
            recipient=params.recipient,
            deadline=params.deadline,
            dex_id=params.dex.id,
        )


class TransactionDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain_id: int
    to: str
    data: str
    value: str
    gas: int | None = None
    gas_price: str | None = None
    nonce: int | None = None

    @classmethod
    def from_domain(cls, tx: TransactionRequest) -> "TransactionDTO":
        return cls(
            chain_id=tx.chain_id,
            to=tx.to,
            data=tx.data,
            value=str(tx.value),
            gas=tx.gas,
            gas_price=str(tx.gas_price) if tx.gas_price is not None else None,
            nonce=tx.nonce,
        )


class SwapResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str
    quote: QuoteDTO | None = None
    params: SwapParamsDTO | None = None
    tx_hash: str | None = None
    error: str | None = None

    @classmethod
    def from_domain(cls, result: SwapResult) -> "SwapResultDTO":
        return cls(
            status=result.status.value,
            quote=QuoteDTO.from_domain(result.quote) if result.quote else None,
            params=SwapParamsDTO.from_domain(result.params) if result.params else None,
            tx_hash=result.tx_hash,
            error=result.error,
        )


class SwapPrepareResponse(BaseModel):
    """Response for POST /api/swap/prepare.

    Includes the winning quote, the frozen params, and the actual
    signable transaction (calldata + value) built by the DEX adapter.
    """

    model_config = ConfigDict(frozen=True)

    status: str
    quote: QuoteDTO
    params: SwapParamsDTO
    tx: TransactionDTO


# --------------------------------------------------------------------------- #
# Request DTOs                                                                 #
# --------------------------------------------------------------------------- #


class QuoteRequestIn(BaseModel):
    """Payload for POST /api/quotes — pure comparison, no sender needed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chain_id: int
    token_in: TokenDTO
    token_out: TokenDTO
    amount_in: str = Field(
        ...,
        description="Amount in the token_in's smallest unit (wei-like), as a string",
    )
    preferred_dex_id: str | None = None

    @model_validator(mode="after")
    def _check_chain_consistency(self) -> "QuoteRequestIn":
        if self.token_in.chain_id != self.chain_id:
            raise ValueError("token_in.chain_id must match chain_id")
        if self.token_out.chain_id != self.chain_id:
            raise ValueError("token_out.chain_id must match chain_id")
        return self


class SwapRequestIn(BaseModel):
    """Payload for POST /api/swap/prepare."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chain_id: int
    token_in: TokenDTO
    token_out: TokenDTO
    amount_in: str = Field(..., description="Amount in wei-like units, as string")
    sender: str = Field(..., description="Address that will sign & send the tx")
    recipient: str | None = None
    slippage_bps: int = Field(50, ge=0, le=10_000)
    preferred_dex_id: str | None = None
    deadline_seconds: int = Field(1200, gt=0, le=86_400)

    @model_validator(mode="after")
    def _check_chain_consistency(self) -> "SwapRequestIn":
        if self.token_in.chain_id != self.chain_id:
            raise ValueError("token_in.chain_id must match chain_id")
        if self.token_out.chain_id != self.chain_id:
            raise ValueError("token_out.chain_id must match chain_id")
        return self

    def to_domain(self, chain: Chain) -> SwapRequest:
        return SwapRequest(
            chain=chain,
            token_in=self.token_in.to_domain(),
            token_out=self.token_out.to_domain(),
            amount_in=int(self.amount_in),
            sender=self.sender,
            recipient=self.recipient,
            slippage_bps=self.slippage_bps,
            preferred_dex_id=self.preferred_dex_id,
            deadline_seconds=self.deadline_seconds,
        )
