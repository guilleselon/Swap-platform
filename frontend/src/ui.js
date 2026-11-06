// ui.js — DOM rendering helpers. No state, no fetch.

import { tokensForChain } from "./tokens.js";

export function renderChains(select, chains) {
    select.innerHTML = "";
    if (chains.length === 0) {
        const opt = document.createElement("option");
        opt.textContent = "No chains enabled";
        opt.value = "";
        select.appendChild(opt);
        select.disabled = true;
        return;
    }
    for (const c of chains) {
        const opt = document.createElement("option");
        opt.value = String(c.id);
        opt.textContent = `${c.name} (${c.native_symbol})`;
        select.appendChild(opt);
    }
    select.disabled = false;
}

export function renderTokens(select, chainId, { placeholder = "Select token" } = {}) {
    select.innerHTML = "";
    const tokens = tokensForChain(chainId);
    if (tokens.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "—";
        select.appendChild(opt);
        return;
    }
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = placeholder;
    select.appendChild(blank);

    for (const t of tokens) {
        const opt = document.createElement("option");
        opt.value = t.symbol;
        opt.textContent = t.symbol;
        opt.dataset.address = t.address;
        opt.dataset.decimals = String(t.decimals);
        select.appendChild(opt);
    }
}

export function getSelectedToken(select) {
    const opt = select.options[select.selectedIndex];
    if (!opt || !opt.value) return null;
    return {
        address: opt.dataset.address,
        symbol: opt.value,
        decimals: parseInt(opt.dataset.decimals, 10),
        chain_id: parseInt(select.dataset.chainId || "0", 10),
    };
}

export function clearQuotes(container) {
    container.innerHTML = "";
}

export function renderQuotes(container, quotes, tokenOut, onSwap) {
    container.innerHTML = "";
    if (quotes.length === 0) {
        const msg = document.createElement("p");
        msg.style.color = "var(--text-muted)";
        msg.style.fontSize = "0.9rem";
        msg.textContent = "No route found for this pair. Try a different amount.";
        container.appendChild(msg);
        return;
    }

    // Sort by amount_out descending; first is the best.
    const sorted = [...quotes].sort(
        (a, b) => (BigInt(b.amount_out) > BigInt(a.amount_out) ? 1 : -1)
    );
    const bestId = sorted[0].dex.id;

    for (const q of sorted) {
        const row = document.createElement("div");
        row.className = "quote-row" + (q.dex.id === bestId ? " best" : "");

        const left = document.createElement("div");
        left.className = "quote-left";

        const dexName = document.createElement("span");
        dexName.className = "quote-dex";
        dexName.textContent = q.dex.name;
        left.appendChild(dexName);

        if (q.dex.id === bestId) {
            const badge = document.createElement("span");
            badge.className = "quote-badge";
            badge.textContent = "BEST";
            left.appendChild(badge);
        }

        const amount = document.createElement("span");
        amount.className = "quote-amount";
        amount.textContent = `${formatAmount(q.amount_out, tokenOut.decimals)} ${tokenOut.symbol}`;

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-primary btn-small";
        btn.textContent = "Swap";
        btn.addEventListener("click", () => {
            const all = container.querySelectorAll("button");
            all.forEach((b) => { b.disabled = true; });
            onSwap(q).finally(() => {
                all.forEach((b) => { b.disabled = false; });
            });
        });

        row.appendChild(left);
        row.appendChild(amount);
        row.appendChild(btn);
        container.appendChild(row);
    }
}

export function showStatus(el, message, type = "info") {
    el.hidden = false;
    el.className = `status-banner status-${type}`;
    el.innerHTML = "";
    el.appendChild(document.createTextNode(message));
}

export function showStatusLink(el, message, linkText, href) {
    el.hidden = false;
    el.className = "status-banner status-success";
    el.innerHTML = "";
    el.appendChild(document.createTextNode(message + " "));
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener";
    a.textContent = linkText;
    a.style.color = "var(--accent)";
    el.appendChild(a);
}

export function hideStatus(el) {
    el.hidden = true;
    el.innerHTML = "";
}

// -- Amount formatting -----------------------------------------------------

export function formatAmount(weiStr, decimals) {
    const n = BigInt(weiStr);
    const base = 10n ** BigInt(decimals);
    const whole = n / base;
    const frac = (n % base).toString().padStart(decimals, "0").replace(/0+$/, "");
    return frac ? `${whole}.${frac}` : whole.toString();
}

export function parseAmount(humanStr, decimals) {
    if (!humanStr || humanStr === ".") return 0n;
    const [whole = "0", frac = ""] = String(humanStr).split(".");
    const wholeBig = BigInt(whole || "0");
    const fracPadded = (frac + "0".repeat(decimals)).slice(0, decimals);
    return wholeBig * (10n ** BigInt(decimals)) + BigInt(fracPadded || "0");
}
