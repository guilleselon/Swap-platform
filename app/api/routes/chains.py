"""Chain discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import ChainRegistryDep
from app.api.schemas import ChainDTO, DexDTO

router = APIRouter()


@router.get("/chains", response_model=list[ChainDTO], summary="List supported chains")
async def list_chains(registry: ChainRegistryDep) -> list[ChainDTO]:
    return [ChainDTO.from_domain(c) for c in registry.list_chains()]


@router.get(
    "/chains/{chain_id}/dexes",
    response_model=list[DexDTO],
    summary="List DEXes available on a chain",
)
async def list_dexes(chain_id: int, registry: ChainRegistryDep) -> list[DexDTO]:
    chain = registry.get_chain(chain_id)
    if chain is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chain {chain_id} is not supported",
        )
    providers = registry.list_dex_providers(chain_id)
    return [DexDTO.from_domain(p.dex) for p in providers]
