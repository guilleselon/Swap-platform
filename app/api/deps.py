"""FastAPI dependency wrappers.

Routes import these type aliases instead of calling ``app.dependencies``
directly, which makes them testable via ``dependency_overrides``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app import dependencies
from app.application import SwapOrchestrator
from app.application.ports import ChainRegistry


def orchestrator_dep() -> SwapOrchestrator:
    return dependencies.get_orchestrator()


def chain_registry_dep() -> ChainRegistry:
    return dependencies.get_chain_registry()


OrchestratorDep = Annotated[SwapOrchestrator, Depends(orchestrator_dep)]
ChainRegistryDep = Annotated[ChainRegistry, Depends(chain_registry_dep)]
