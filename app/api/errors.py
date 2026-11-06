"""Translate domain exceptions into HTTP responses.

Every endpoint can let ``DomainError`` bubble up; this module converts it
to a JSON error payload with a meaningful status code.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    DomainError,
    InsufficientLiquidityError,
    InvalidSwapRequestError,
    NoRouteFoundError,
    QuoteExpiredError,
    UnsupportedChainError,
    UnsupportedDexError,
    ValidationError,
)

logger = logging.getLogger(__name__)


_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    ValidationError: 422,               # Unprocessable Entity
    InvalidSwapRequestError: 400,       # Bad Request
    UnsupportedChainError: 400,         # Bad Request
    UnsupportedDexError: 400,           # Bad Request
    InsufficientLiquidityError: 422,    # Unprocessable Entity
    NoRouteFoundError: 404,             # Not Found
    QuoteExpiredError: 410,             # Gone
}


def _status_for(exc: DomainError) -> int:
    """Resolve HTTP status by walking the exception's MRO.

    Subclasses inherit their parent's status unless they have their own.
    """
    for cls in type(exc).__mro__:
        if cls in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[cls]
    return 400  # default for any other DomainError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(
        _request: Request, exc: DomainError
    ) -> JSONResponse:
        status = _status_for(exc)
        logger.info(
            "domain error: %s -> HTTP %d (%s)",
            type(exc).__name__,
            status,
            exc,
        )
        return JSONResponse(
            status_code=status,
            content={
                "error": type(exc).__name__,
                "message": str(exc),
            },
        )
