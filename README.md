# Swap Aggregator — Educational MVP

> WARNING: This is NOT a product. It is an MVP built to learn.
>
> The code works: you can connect to Sepolia, quote against Uniswap V2 and
> SushiSwap on Ethereum, and execute real swaps on Sepolia.
> But it is NOT production-ready and must NOT be used with real funds
> without first reading the [Limitations and risks](#-limitations-and-risks)
> section.
>
> If you want to build something serious, use this repository as a starting
> point and rewrite what is needed. Do not deploy it as-is.

---

## What is this?

A multi-chain, multi-DEX EVM swap aggregator that compares prices in real
time across DEXes, lets the user pick the best one, and builds the
transaction for the user to sign from their own wallet.

The backend never custodies funds or private keys. It only:

1. Reads prices from the DEX contracts (via RPC).
2. Compares and ranks quotes.
3. Builds the transaction calldata.
4. Returns it to the frontend so the user's wallet can sign it.

Nothing else. If this backend disappeared tomorrow, the user could execute
the same swap by going directly to Uniswap or SushiSwap.

### What this MVP demonstrates

- Layered architecture (Hexagonal / Ports & Adapters): domain, application,
  infrastructure, and API fully decoupled.
- Concurrent quoting of multiple DEXes with per-provider fault tolerance.
- Pure, network-free domain (34 tests, no network mocks, deterministic fakes).
- Cross-chain flow: quote on Ethereum, execute on Sepolia (useful for
  testing without spending real ETH).
- Non-custodial MetaMask integration: approve + swap always signed by the user.

### What this MVP does NOT demonstrate

- How to aggregate complex routes (split across DEXes, optimized multi-hop).
- How to protect against MEV, front-running, or sandwich attacks.
- How to operate with real money safely.

---

## Architecture
+------------------------------+
| Frontend (vanilla JS) |
| - wallet.js (MetaMask) |
| - api.js (fetch) |
| - ui.js (DOM) |
| - tokens.js (token lists) |
+--------------+---------------+
| HTTP/JSON
+--------------v---------------+
| API Layer (FastAPI) |
| - /api/chains |
| - /api/quotes |
| - /api/swap/prepare |
+--------------+---------------+
| Python calls
+--------------v---------------+
| Application (orchestration)|
| - SwapOrchestrator |
| - Ports (Protocols) |
+--------------+---------------+
+----------+----------+
| |
+-----------v----------+ +-------v------------+
| Domain (pure) | | Infrastructure |
| - Models | | - Web3Client |
| - quote_service | | - UniswapV2Provider |
| - routing_service | | - ChainRegistry |
| (no web3, no fastapi)| | (web3.py) |
+----------------------+ +---------------------+

text

### Rule of thumb

Each layer only knows the layer immediately below it, and always through a
Protocol (typing.Protocol), never a concrete class. That means:

- Domain imports neither web3 nor fastapi — it is pure Python.
- Application has no idea if a DEX is Uniswap or Sushi — it only knows
  DEXProvider.
- API does not instantiate anything directly — it asks for dependencies
  from dependencies.py.
- Swapping UniswapV2Provider for UniswapV3Provider does not touch domain
  or application.
- Swapping FastAPI for Flask only touches app/api/ and app/main.py.

---

## MVP features

### Backend

- Multi-chain: Ethereum, BNB Chain, Polygon, Sepolia. Extendable by adding
  an entry in config/chains.py plus its RPC_URL_<id> in .env.
- Multi-DEX: Uniswap V2, SushiSwap, PancakeSwap V2, QuickSwap. All share
  the same UniswapV2Provider (they are ABI-compatible). Sepolia uses its
  own instance.
- Concurrent quoting: fires all quotes in parallel (asyncio.gather) and
  tolerates one DEX failing without blocking the rest.
- Quote ranking: sorts by effective price and flags the best one.
- Configurable slippage: in basis points, applied in the domain
  (amount_out_min = amount_out * (10000 - slippage_bps) / 10000).
- Multi-hop paths: if no direct pair exists, tries via wrapped native
  (WETH, WBNB, WMATIC).
- Price-impact estimation: per hop, aggregated.
- Checksum normalization: the adapter handles lowercase addresses that
  MetaMask sometimes returns.
- Domain-to-HTTP error mapping: DomainError maps to semantic codes
  (400, 404, 410, 422).

### Frontend

- Non-custodial: the wallet signs everything. The backend never sees keys.
- Wallet detection: window.ethereum, accountsChanged, chainChanged.
- Quote-chain selector (fixed to Ethereum) and execution-chain selector
  (Ethereum / Sepolia).
- Quote comparison: ordered list with the best one highlighted.
- Automatic approve: checks allowance; if insufficient, sends approve
  before the swap.
- Transparent chain switching: if the wallet is on another chain, calls
  switchChain before signing.
- Explorer link: opens the execution chain's explorer with the tx hash.

### Tests

- 34 tests across 4 files (test_domain, test_application,
  test_uniswap_v2, test_api).
- Domain and application tested with deterministic fakes, no network.
- Infrastructure tested with mocked Web3, no real RPC.
- API tested with TestClient and dependency_overrides.

---

## How to run (development)

### Requirements

- Python >= 3.11
- Node.js is NOT needed (frontend is vanilla JS, no build step)
- MetaMask installed in the browser
- An RPC URL for the chain(s) you want to use (PublicNode is free and
  needs no API key)

### 1. Clone and install

```bash
git clone <your-repo>
cd swap-platform-v2
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
2. Configure .env
bash
cp .env.example .env
Edit .env with your RPCs:

env
RPC_URL_1=https://ethereum-rpc.publicnode.com
RPC_URL_11155111=https://ethereum-sepolia-rpc.publicnode.com
Note: only chains with RPC_URL_<id> defined are enabled at startup.

3. Start the server
bash
uvicorn app.main:app --reload
You will see in the logs which chains were enabled:

text
INFO app.bootstrap: Chain 1 (Ethereum): 2 DEX(es) -> uniswap_v2, sushiswap
INFO app.bootstrap: Chain 11155111 (Sepolia): 1 DEX(es) -> uniswap_v2_sepolia
4. Open the app
App: http://127.0.0.1:8000/

Swagger UI: http://127.0.0.1:8000/docs

5. Try a swap on Sepolia (recommended)
Connect MetaMask.

You need Sepolia ETH for gas -> faucet
(https://cloud.google.com/application/web3/faucet/ethereum/sepolia).

Execution chain: Sepolia.

From: ETH -> To: USDC, amount 0.001.

Get quotes -> you will see real Ethereum mainnet prices.

Swap -> MetaMask will ask to switch to Sepolia -> confirm -> you will
see the hash on sepolia.etherscan.io.

Tip: the price you sign is Ethereum's, not Sepolia's.
Sepolia liquidity is extremely low and the swap may revert with
INSUFFICIENT_OUTPUT_AMOUNT. Raise slippage to 10-20% for testing and do
not be surprised if it fails. This does not happen on mainnet.

6. Run the tests
bash
pytest -q                # -> 34 passed
pytest -q --cov=app      # with coverage
ruff check app           # linting
ruff format app          # formatting
Structure
text
swap-platform-v2/
|-- app/
|   |-- domain/              # pure layer — no web3, no fastapi
|   |   |-- models.py        # Chain, Token, DEX, Quote, SwapRequest, ...
|   |   |-- exceptions.py
|   |   +-- services/        # quote_service, routing_service
|   |-- application/         # orchestration
|   |   |-- ports.py         # Protocols: Clock, DEXProvider, ChainRegistry
|   |   +-- swap_orchestrator.py
|   |-- infrastructure/      # concrete adapters
|   |   |-- blockchain/      # Web3Client + ABIs
|   |   |-- dex_providers/   # UniswapV2Provider
|   |   +-- registry.py      # Web3ChainRegistry
|   |-- api/                 # HTTP layer
|   |   |-- schemas.py       # Pydantic DTOs
|   |   |-- errors.py        # DomainError -> HTTPException
|   |   |-- deps.py          # FastAPI Depends()
|   |   +-- routes/          # chains, quotes, swap
|   |-- config/              # settings + chains/DEXes static data
|   |-- main.py              # FastAPI bootstrap
|   |-- dependencies.py      # singletons (lru_cache)
|   +-- tests/
|-- frontend/
|   |-- index.html
|   |-- styles.css
|   +-- src/                 # wallet, api, ui, tokens, main
|-- pyproject.toml
|-- .env.example
+-- README.md
Limitations and risks
This section is the most important one in this README. If you plan to use
this MVP as a base for something serious, read this first.

Security — do not use with real funds until these are fixed
No MEV protection. Your transactions are visible in the public mempool.
A bot can sandwich your swap: it sees your swap and manipulates the
price against you before and after. This is the #1 problem of real
dApps. Fixes: Flashbots Protect RPC, MEV Blocker, or an RFQ contract.

No price verification before signing. Between when the user sees the
quote and when they sign, the price may have moved. Only slippage
protects them. For production: re-quote at the exact moment before
eth_sendTransaction.

Price impact is an estimate. It does not include router fees nor the
real impact on the pool. Large swaps may differ significantly from
the reported number.

No rate limiting or authentication. Anyone can fire N requests per
second to /api/quotes. In production with a paid RPC, this directly
becomes your bill.

No RPC failure handling. If the RPC fails, every quote fails. There is
no retry, no fallback to other RPCs, no circuit breaker.

No audit. The code has not been reviewed by a security expert. Even
though the design is non-custodial (the backend never touches keys),
nothing is formally auditable.

Correctness — works, but edge cases not covered
Only Uniswap V2 ABI. On mainnet, V3 moves ~80% of the volume. The
prices you see are worse than those a real user would get.
UniswapV3Provider is the highest-impact improvement.

No route splitting. If Uniswap quotes 100 USDC per 1 ETH and Sushi
quotes 101, this MVP sends you to Sushi with 100% of the volume. Real
aggregators (1inch, Paraswap) split your order across multiple DEXes
to minimize slippage. This requires your own contract.

Price impact does not subtract fees. Pool fees (0.3% on V2) are baked
into the price but not reported separately. The user does not see a
breakdown.

Cross-chain quote/exec is only for testing. The current design quotes
on Ethereum and executes on Sepolia. Prices come from mainnet and may
not correspond to Sepolia -> slippage warning. Useful for demo only.

Tokens hardcoded in the frontend. tokens.js has ~5 tokens per chain.
No dynamic token discovery, no verified token lists, no custom token
import.

No balances in the UI. The user can attempt a swap without holding the
token. MetaMask will block it, but it is bad UX.

Operational — not ready to deploy
No database. No swap history, no preferences, no users. For
production you would need Postgres (or similar) + SIWE auth.

No observability. No Prometheus metrics, no distributed tracing, no
alerting. If a DEX starts failing, you find out via scattered logs.

No Dockerfile or compose. No reproducible image, no CI/CD, no
automated deployment.

No HTTPS, no configured CORS. The dev server exposes 127.0.0.1:8000.
In production you need a reverse proxy (nginx, Caddy), TLS, HSTS,
explicit CORS.

Frontend not bundled. Serves source files as-is. Fast for development,
slow for production (multiple requests, no minification, no automatic
cache busting).

Dependencies not strictly pinned. pyproject.toml uses ranges (>=x,<y).
For production, pin exact versions and audit with pip-audit / safety.

What is actually well done
Layered architecture with ports & adapters: easy to extend and test.

Pure domain: everything else can change without touching business rules.

34 deterministic tests with no network: fast and reliable.

Non-custodial by design: the backend never sees keys.

Domain-to-HTTP error mapping with semantic codes.

Checksum normalization in the adapter (where it belongs).

Environment-driven configuration, no secrets hardcoded.

Roadmap to make it serious
If you want to move from MVP to product, this is a reasonable order.

Phase 1 — Correctness foundations
UniswapV3Provider — immediate price impact.

Balance checks in the frontend before signing.

Re-quote at signing time (do not trust the viewed quote).

RPC fallback with exponential retry and circuit breaker.

Integration tests against a local Anvil node (mainnet fork).

Phase 2 — User protection
MEV protection via Flashbots Protect RPC (one line of change on the
tx, huge protection).

Price-impact warning when it crosses a configurable threshold
(e.g. 2%).

Destination contract verification in the frontend (show
"Uniswap V2 Router" instead of a raw address).

Verified token list (Uniswap / CoinGecko token lists).

Phase 3 — Product
SIWE auth + database (swap history, preferences).

Observability: Prometheus, OpenTelemetry, alerts.

Rate limiting by IP and by user.

Dockerfile + compose + CI/CD.

Your own aggregation contract if you plan to charge a fee or split
routes.

External audit before handling real funds.

Phase 4 — Scale
Quote caching (Redis, TTL 10-30s).

WebSocket or SSE to refresh quotes live.

Multi-wallet support (WalletConnect, Coinbase Wallet, Rabby).

More chains — Base, Arbitrum, Optimism, Avalanche.

Contributing
This is an educational project. If you use it to learn:

Fork freely. Modify it, break it, experiment.

Issues welcome if you find bugs.

PRs welcome if you fix something, but please keep the layer separation.

Do not open PRs to "fix" the lack of MEV protection without discussing
it first — it is a conscious MVP design choice.

Useful references
Uniswap V2 docs: https://docs.uniswap.org/contracts/v2/overview

Uniswap V3 docs: https://docs.uniswap.org/contracts/v3/overview

1inch Aggregation API: https://portal.1inch.dev/

0x API docs: https://0x.org/docs

EIP-55 checksum: https://eips.ethereum.org/EIPS/eip-55

SIWE (EIP-4361): https://eips.ethereum.org/EIPS/eip-4361

Flashbots Protect: https://protect.flashbots.net/

License
MIT. Use it, learn from it, improve it. But do not ship it as a product
without fixing the limitations above.
