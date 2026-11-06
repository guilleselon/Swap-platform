"""Environment-driven settings.

RPC URLs come from .env as ``RPC_URL_<chain_id>`` (e.g. RPC_URL_1).
Chains without an URL are silently excluded from the runtime registry.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # allow running without python-dotenv installed
    def load_dotenv(*_a, **_k):
        return False

# Load .env from project root, regardless of the CWD.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


KNOWN_CHAIN_IDS: tuple[int, ...] = (1, 56, 137, 42161, 10, 11155111)


def rpc_url(chain_id: int) -> str | None:
    return os.getenv(f"RPC_URL_{chain_id}")


def rpc_urls() -> dict[int, str]:
    """All configured RPC URLs, keyed by chain id."""
    return {
        cid: url
        for cid in KNOWN_CHAIN_IDS
        if (url := rpc_url(cid))
    }


MAX_SLIPPAGE_BPS: int = int(os.getenv("MAX_SLIPPAGE_BPS", "1000"))
DEFAULT_DEADLINE_SECONDS: int = int(os.getenv("DEFAULT_DEADLINE_SECONDS", "1200"))
DEFAULT_QUOTE_TTL_SECONDS: int = int(os.getenv("DEFAULT_QUOTE_TTL_SECONDS", "30"))
