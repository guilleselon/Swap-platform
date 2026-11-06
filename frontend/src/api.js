// api.js — thin fetch wrappers for the backend endpoints.

async function request(method, path, body) {
    const opts = {
        method,
        headers: { "Content-Type": "application/json" },
    };
    if (body !== undefined) opts.body = JSON.stringify(body);

    const res = await fetch(path, opts);
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
        const err = new Error(
            data.message || data.detail || `HTTP ${res.status}`
        );
        err.code = data.error || `HTTP_${res.status}`;
        err.status = res.status;
        throw err;
    }
    return data;
}

export async function listChains() {
    return request("GET", "/api/chains");
}

export async function listDexes(chainId) {
    return request("GET", `/api/chains/${chainId}/dexes`);
}

export async function getQuotes({ chainId, tokenIn, tokenOut, amountIn, preferredDexId }) {
    return request("POST", "/api/quotes", {
        chain_id: chainId,
        token_in: tokenIn,
        token_out: tokenOut,
        amount_in: String(amountIn),
        preferred_dex_id: preferredDexId ?? null,
    });
}

export async function prepareSwap({
    chainId, tokenIn, tokenOut, amountIn,
    sender, slippageBps, preferredDexId, deadlineSeconds,
}) {
    return request("POST", "/api/swap/prepare", {
        chain_id: chainId,
        token_in: tokenIn,
        token_out: tokenOut,
        amount_in: String(amountIn),
        sender,
        slippage_bps: slippageBps,
        preferred_dex_id: preferredDexId ?? null,
        deadline_seconds: deadlineSeconds ?? 1200,
    });
}
