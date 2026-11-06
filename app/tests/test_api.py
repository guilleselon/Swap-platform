"""End-to-end API tests using the FakeRegistry injected via Depends()."""

from __future__ import annotations

import pytest

from app.tests.conftest import (
    USDC_ADDR,
    WETH_ADDR,
    FakeDEXProvider,
    FakeRegistry,
    _chain,
    _dex,
    usdc,
    weth,
)


# --------------------------------------------------------------------------- #
# /health                                                                      #
# --------------------------------------------------------------------------- #


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": "0.1.0"}


# --------------------------------------------------------------------------- #
# /api/chains                                                                  #
# --------------------------------------------------------------------------- #


def test_list_chains_returns_registered(client):
    r = client.get("/api/chains")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == 1
    assert body[0]["native_symbol"] == "ETH"


def test_list_dexes_on_chain(client):
    r = client.get("/api/chains/1/dexes")
    assert r.status_code == 200
    body = r.json()
    assert {d["id"] for d in body} == {"uniswap_v2", "sushiswap"}
    assert all(d["protocol"] == "v2" for d in body)


def test_list_dexes_unsupported_chain(client):
    r = client.get("/api/chains/999/dexes")
    assert r.status_code == 404


# --------------------------------------------------------------------------- #
# POST /api/quotes                                                             #
# --------------------------------------------------------------------------- #


def _quote_payload(amount_in: int = 1_000 * 10**6) -> dict:
    return {
        "chain_id": 1,
        "token_in": {
            "chain_id": 1,
            "address": USDC_ADDR,
            "symbol": "USDC",
            "decimals": 6,
        },
        "token_out": {
            "chain_id": 1,
            "address": WETH_ADDR,
            "symbol": "WETH",
            "decimals": 18,
        },
        "amount_in": str(amount_in),
    }


def test_quotes_returns_all_providers(client):
    r = client.post("/api/quotes", json=_quote_payload())
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    dex_ids = {q["dex"]["id"] for q in body}
    assert dex_ids == {"uniswap_v2", "sushiswap"}
    # amount fields are strings, not ints
    assert all(isinstance(q["amount_out"], str) for q in body)


def test_quotes_unsupported_chain(client):
    payload = _quote_payload()
    payload["chain_id"] = 999
    payload["token_in"]["chain_id"] = 999
    payload["token_out"]["chain_id"] = 999
    r = client.post("/api/quotes", json=payload)
    assert r.status_code == 400
    assert r.json()["error"] == "UnsupportedChainError"


def test_quotes_preferred_dex_filter(client):
    payload = _quote_payload()
    payload["preferred_dex_id"] = "uniswap_v2"
    r = client.post("/api/quotes", json=payload)
    assert r.status_code == 200
    assert {q["dex"]["id"] for q in r.json()} == {"uniswap_v2"}


def test_quotes_invalid_token_chain_mismatch(client):
    payload = _quote_payload()
    payload["token_in"]["chain_id"] = 999  # mismatch with chain_id=1
    r = client.post("/api/quotes", json=payload)
    assert r.status_code == 422  # Pydantic model_validator


def test_quotes_no_route(client):
    # Override with a registry where every provider returns None.
    from app.api.deps import chain_registry_dep, orchestrator_dep
    from app.application import SwapOrchestrator
    from app.tests.conftest import FixedClock
    from datetime import datetime, timezone

    empty_registry = FakeRegistry(
        chains=[_chain(1)],
        providers=[FakeDEXProvider(_dex("uniswap_v2"), None)],
    )
    app = client.app
    app.dependency_overrides[chain_registry_dep] = lambda: empty_registry
    app.dependency_overrides[orchestrator_dep] = lambda: SwapOrchestrator(
        empty_registry, FixedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    )

    r = client.post("/api/quotes", json=_quote_payload())
    assert r.status_code == 200
    assert r.json() == []


# --------------------------------------------------------------------------- #
# POST /api/swap/prepare                                                       #
# --------------------------------------------------------------------------- #


def _swap_payload(amount_in: int = 1_000 * 10**6) -> dict:
    return {
        **_quote_payload(amount_in),
        "sender": "0x0000000000000000000000000000000000000001",
        "slippage_bps": 50,
        "deadline_seconds": 1200,
    }


def test_prepare_swap_happy_path(client):
    r = client.post("/api/swap/prepare", json=_swap_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "prepared"
    # Sushi won (420e15 > 400e15)
    assert body["quote"]["dex"]["id"] == "sushiswap"
    # amount_out_min reflects 0.5% slippage
    expected_min = 420_000_000_000_000_000 * 9950 // 10_000
    assert int(body["params"]["amount_out_min"]) == expected_min
    # Transaction was built
    assert body["tx"]["to"] == "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
    assert body["tx"]["data"] == "0xdeadbeef"
    assert body["tx"]["value"] == "0"


def test_prepare_swap_preferred_dex(client):
    payload = _swap_payload()
    payload["preferred_dex_id"] = "uniswap_v2"
    r = client.post("/api/swap/prepare", json=payload)
    assert r.status_code == 200
    assert r.json()["quote"]["dex"]["id"] == "uniswap_v2"


def test_prepare_swap_unsupported_chain(client):
    payload = _swap_payload()
    payload["chain_id"] = 999
    payload["token_in"]["chain_id"] = 999
    payload["token_out"]["chain_id"] = 999
    r = client.post("/api/swap/prepare", json=payload)
    assert r.status_code == 400
    assert r.json()["error"] == "UnsupportedChainError"


def test_prepare_swap_no_route(client):
    from app.api.deps import chain_registry_dep, orchestrator_dep
    from app.application import SwapOrchestrator
    from app.tests.conftest import FixedClock
    from datetime import datetime, timezone

    empty = FakeRegistry(
        chains=[_chain(1)],
        providers=[FakeDEXProvider(_dex("uniswap_v2"), None)],
    )
    client.app.dependency_overrides[chain_registry_dep] = lambda: empty
    client.app.dependency_overrides[orchestrator_dep] = lambda: SwapOrchestrator(
        empty, FixedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
    )
    r = client.post("/api/swap/prepare", json=_swap_payload())
    assert r.status_code == 404
    assert r.json()["error"] == "NoRouteFoundError"


def test_prepare_swap_invalid_slippage(client):
    payload = _swap_payload()
    payload["slippage_bps"] = 20_000  # > 10000
    r = client.post("/api/swap/prepare", json=payload)
    assert r.status_code == 422  # Pydantic Field(le=10_000)
