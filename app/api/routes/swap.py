"""Swap preparation endpoint.

Returns the winning quote, frozen params, and a signable EVM transaction.
The transaction is NOT signed and NOT broadcast — that's the frontend's
wallet job. Backend never touches private keys.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import ChainRegistryDep, OrchestratorDep
from app.api.schemas import (
    QuoteDTO,
    SwapParamsDTO,
    SwapPrepareResponse,
    SwapRequestIn,
    TransactionDTO,
)
from app.domain.exceptions import UnsupportedChainError, UnsupportedDexError

router = APIRouter()


@router.post(
    "/swap/prepare",
    response_model=SwapPrepareResponse,
    summary="Prepare a signable swap transaction",
)
async def prepare_swap(
    payload: SwapRequestIn,
    orchestrator: OrchestratorDep,
    registry: ChainRegistryDep,
) -> SwapPrepareResponse:
    chain = registry.get_chain(payload.chain_id)
    if chain is None:
        raise UnsupportedChainError(
            f"Chain {payload.chain_id} is not supported"
        )

    request = payload.to_domain(chain)
    result = await orchestrator.prepare_swap(request)

    # The orchestrator already guarantees these are set for PREPARED results.
    assert result.quote is not None and result.params is not None

    provider = registry.get_dex_provider(
        payload.chain_id, result.quote.dex.id
    )
    if provider is None:
        raise UnsupportedDexError(
            f"DEX '{result.quote.dex.id}' is not available on chain "
            f"{payload.chain_id}"
        )

    tx = await provider.build_swap_tx(result.params, sender=payload.sender)

    return SwapPrepareResponse(
        status=result.status.value,
        quote=QuoteDTO.from_domain(result.quote),
        params=SwapParamsDTO.from_domain(result.params),
        tx=TransactionDTO.from_domain(tx),
    )
