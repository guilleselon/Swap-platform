"""Quote comparison endpoint — returns ALL quotes, does not select a winner."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ChainRegistryDep, OrchestratorDep
from app.api.schemas import QuoteDTO, QuoteRequestIn
from app.domain.exceptions import UnsupportedChainError

router = APIRouter()


@router.post(
    "/quotes",
    response_model=list[QuoteDTO],
    summary="Get quotes from every DEX for a given pair",
)
async def get_quotes(
    payload: QuoteRequestIn,
    orchestrator: OrchestratorDep,
    registry: ChainRegistryDep,
) -> list[QuoteDTO]:
    if registry.get_chain(payload.chain_id) is None:
        raise UnsupportedChainError(
            f"Chain {payload.chain_id} is not supported"
        )

    quotes = await orchestrator.get_quotes(
        chain_id=payload.chain_id,
        token_in=payload.token_in.to_domain(),
        token_out=payload.token_out.to_domain(),
        amount_in=int(payload.amount_in),
        preferred_dex_id=payload.preferred_dex_id,
    )
    return [QuoteDTO.from_domain(q) for q in quotes]
