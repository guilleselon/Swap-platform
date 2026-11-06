"""HTTP API layer (FastAPI).

This package contains:
- ``schemas``: Pydantic DTOs for requests and responses
- ``errors``:  DomainError -> HTTPException mapping
- ``deps``:    FastAPI ``Depends()`` wrappers around ``app.dependencies``
- ``routes``:  Endpoint modules (added incrementally)
"""

from .errors import register_exception_handlers

__all__ = ["register_exception_handlers"]
