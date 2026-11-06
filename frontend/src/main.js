// main.js — entry point del frontend.
//
// Diseño:
//   - Cotización: SIEMPRE en Ethereum (QUOTE_CHAIN_ID = 1).
//   - Ejecución: el usuario elige entre Ethereum o Sepolia.
//   - Si ejecuta en la misma chain donde cotizó, se respeta el DEX elegido.
//   - Si ejecuta cross-chain (Sepolia), el backend elige el único DEX disponible.

import {
    connectWallet,
    currentAddress,
    getAllowance,
    getCurrentChainId,
    isWalletAvailable,
    onAccountsChanged,
    onChainChanged,
    sendApprove,
    sendTransaction,
    shortAddress,
    chainName,
    switchChain,
    waitForReceipt,
} from "./wallet.js";

import { getQuotes, listChains, prepareSwap } from "./api.js";

import {
    clearQuotes,
    formatAmount,
    getSelectedToken,
    hideStatus,
    parseAmount,
    renderChains,
    renderQuotes,
    renderTokens,
    showStatus,
    showStatusLink,
} from "./ui.js";

import { isNative, tokenBySymbol } from "./tokens.js";

const $ = (id) => document.getElementById(id);

// Chain de cotización: fija en Ethereum mainnet.
const QUOTE_CHAIN_ID = 1;

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------

const state = {
    address: null,
    walletChainId: null,
    chains: [],
    executionChainId: 1,
    currentQuotes: [],
    busy: false,
};

// ---------------------------------------------------------------------------
// Helpers de UI
// ---------------------------------------------------------------------------

function setBusy(v) {
    state.busy = v;
    refreshQuoteBtn();
}

function refreshQuoteBtn() {
    const btn = $("quote-btn");
    const ready =
        !state.busy &&
        !!getSelectedToken($("token-in-select")) &&
        !!getSelectedToken($("token-out-select")) &&
        $("amount-in").value.trim() !== "";
    btn.disabled = !ready;
    btn.textContent = state.busy ? "Loading…" : "Get quotes";
}

function clearQuotesAndStatus() {
    clearQuotes($("quotes-container"));
    hideStatus($("swap-status"));
    state.currentQuotes = [];
}

function renderConnectButton() {
    const btn = $("connect-btn");
    if (state.address) {
        btn.textContent = `${shortAddress(state.address)} · ${chainName(state.walletChainId)}`;
        btn.classList.add("connected");
    } else {
        btn.textContent = "Connect Wallet";
        btn.classList.remove("connected");
    }
}

function getChainById(id) {
    return state.chains.find((c) => c.id === id) ?? null;
}

// ---------------------------------------------------------------------------
// Selección de chain y tokens
// ---------------------------------------------------------------------------

function onQuoteChainChanged() {
    const chainId = QUOTE_CHAIN_ID;
    const inSel = $("token-in-select");
    const outSel = $("token-out-select");
    inSel.dataset.chainId = String(chainId);
    outSel.dataset.chainId = String(chainId);
    renderTokens(inSel, chainId, { placeholder: "Select token" });
    renderTokens(outSel, chainId, { placeholder: "Select token" });

    // Preselección de USDC / WETH si están disponibles.
    const usdc = [...inSel.options].find((o) => o.value === "USDC");
    if (usdc) inSel.value = "USDC";
    const weth = [...outSel.options].find((o) => o.value === "WETH");
    if (weth) outSel.value = "WETH";

    clearQuotesAndStatus();
    refreshQuoteBtn();
}

function onExecutionChainChanged(chainId) {
    state.executionChainId = chainId;
    // Los tokens de cotización no cambian; los de ejecución se resuelven
    // en handleSwap() con tokenBySymbol().
}

// ---------------------------------------------------------------------------
// Fetch de quotes (siempre contra Ethereum)
// ---------------------------------------------------------------------------

async function handleGetQuotes() {
    clearQuotesAndStatus();
    if (!state.address) {
        showStatus($("swap-status"), "Connect your wallet first.", "error");
        return;
    }
    const tokenIn = getSelectedToken($("token-in-select"));
    const tokenOut = getSelectedToken($("token-out-select"));
    const amountStr = $("amount-in").value.trim();
    if (!tokenIn || !tokenOut || !amountStr) return;
    if (tokenIn.address.toLowerCase() === tokenOut.address.toLowerCase()) {
        showStatus($("swap-status"), "Token in and token out must differ.", "error");
        return;
    }
    const amountWei = parseAmount(amountStr, tokenIn.decimals);
    if (amountWei <= 0n) {
        showStatus($("swap-status"), "Amount must be positive.", "error");
        return;
    }

    setBusy(true);
    showStatus($("swap-status"), "Fetching quotes on Ethereum…", "info");
    try {
        const quotes = await getQuotes({
            chainId: QUOTE_CHAIN_ID,
            tokenIn: { ...tokenIn, chain_id: QUOTE_CHAIN_ID },
            tokenOut: { ...tokenOut, chain_id: QUOTE_CHAIN_ID },
            amountIn: amountWei,
        });
        state.currentQuotes = quotes;
        hideStatus($("swap-status"));
        renderQuotes(
            $("quotes-container"),
            quotes,
            tokenOut,
            (quote) => handleSwap(quote, tokenIn, tokenOut, amountWei),
        );
    } catch (err) {
        showStatus($("swap-status"), `Error: ${err.message}`, "error");
    } finally {
        setBusy(false);
    }
}

// ---------------------------------------------------------------------------
// Flujo de swap (en la red de ejecución elegida)
// ---------------------------------------------------------------------------

async function handleSwap(quote, tokenIn, tokenOut, amountWei) {
    if (state.busy) return;
    const status = $("swap-status");
    const execChainId = state.executionChainId;

    // Resolver tokens en la chain de ejecución (direcciones pueden diferir).
    const execTokenIn = tokenBySymbol(tokenIn.symbol, execChainId);
    const execTokenOut = tokenBySymbol(tokenOut.symbol, execChainId);
    if (!execTokenIn || !execTokenOut) {
        showStatus(
            status,
            `Los tokens ${tokenIn.symbol}→${tokenOut.symbol} no están disponibles ` +
            `en la red de ejecución (chain ${execChainId}).`,
            "error",
        );
        return;
    }

    try {
        setBusy(true);

        // 1. Asegurar que la wallet está en la chain de ejecución.
        const walletChain = await getCurrentChainId();
        if (walletChain !== execChainId) {
            showStatus(status, `Switching wallet to chain ${execChainId}…`, "info");
            await switchChain(execChainId);
        }

        const sender = await currentAddress();

        // 2. Preparar swap.
        // preferredDexId solo se respeta si cotización y ejecución comparten chain.
        // En cross-chain dejamos que el backend elija el único DEX disponible.
        showStatus(status, "Preparing swap…", "info");
        const prepared = await prepareSwap({
            chainId: execChainId,
            tokenIn: { ...execTokenIn, chain_id: execChainId },
            tokenOut: { ...execTokenOut, chain_id: execChainId },
            amountIn: amountWei,
            sender,
            slippageBps: Math.round(parseFloat($("slippage-input").value) * 100),
            preferredDexId:
                execChainId === QUOTE_CHAIN_ID ? quote.dex.id : null,
        });

        const { tx, params, quote: freshQuote } = prepared;

        // 3. Approval si el token de entrada es ERC20.
        if (!isNative(execTokenIn)) {
            showStatus(status, `Checking ${execTokenIn.symbol} allowance…`, "info");
            const allowance = await getAllowance(
                execTokenIn.address,
                sender,
                freshQuote.dex.router_address,
            );
            if (allowance < BigInt(params.amount_in)) {
                showStatus(
                    status,
                    `Approve ${execTokenIn.symbol} in your wallet…`,
                    "info",
                );
                const approveHash = await sendApprove(
                    execTokenIn.address,
                    freshQuote.dex.router_address,
                    BigInt(params.amount_in),
                );
                showStatus(status, "Waiting for approval confirmation…", "info");
                const receipt = await waitForReceipt(approveHash);
                if (receipt.status !== "0x1") {
                    throw new Error("Approval transaction failed.");
                }
            }
        }

        // 4. Enviar el swap.
        showStatus(
            status,
            `Confirm swap in your wallet (${freshQuote.dex.name})…`,
            "info",
        );
        const txHash = await sendTransaction({
            from: sender,
            to: tx.to,
            data: tx.data,
            value: tx.value,
        });

        // 5. Link al explorer de la chain de ejecución.
        const chain = getChainById(execChainId);
        const explorer = chain?.block_explorer_url
            ? `${chain.block_explorer_url}/tx/${txHash}`
            : `https://etherscan.io/tx/${txHash}`;

        showStatusLink(
            status,
            `Swap enviado en ${freshQuote.dex.name} (chain ${execChainId}).`,
            "Ver en explorer →",
            explorer,
        );
        clearQuotes($("quotes-container"));
    } catch (err) {
        if (err?.code === 4001) {
            showStatus(status, "Transacción rechazada en la wallet.", "error");
        } else {
            showStatus(status, `Error: ${err?.message ?? String(err)}`, "error");
        }
    } finally {
        setBusy(false);
    }
}

// ---------------------------------------------------------------------------
// Conexión de wallet
// ---------------------------------------------------------------------------

async function handleConnect() {
    try {
        const { address, chainId } = await connectWallet();
        state.address = address;
        state.walletChainId = chainId;
        renderConnectButton();
        hideStatus($("swap-status"));
        refreshQuoteBtn();
    } catch (err) {
        showStatus($("swap-status"), err?.message ?? String(err), "error");
    }
}

// ---------------------------------------------------------------------------
// Carga inicial de chains
// ---------------------------------------------------------------------------

async function loadChains() {
    const chainSel = $("chain-select");
    try {
        const chains = await listChains();
        state.chains = chains;

        if (!chains.length) {
            chainSel.innerHTML = "";
            const opt = document.createElement("option");
            opt.textContent = "No chains enabled";
            opt.value = "";
            chainSel.appendChild(opt);
            showStatus(
                $("swap-status"),
                "Backend no tiene chains habilitadas. Configura RPC_URL_1 en .env.",
                "error",
            );
            return;
        }

        renderChains(chainSel, chains);
        chainSel.value = String(QUOTE_CHAIN_ID);
        onQuoteChainChanged();
    } catch (err) {
        chainSel.innerHTML = "";
        const opt = document.createElement("option");
        opt.textContent = "Failed to load chains";
        opt.value = "";
        chainSel.appendChild(opt);
        showStatus($("swap-status"), `Error: ${err.message}`, "error");
    }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function init() {
    const connectBtn = $("connect-btn");

    if (!isWalletAvailable()) {
        connectBtn.textContent = "Install MetaMask";
        connectBtn.disabled = true;
        showStatus(
            $("swap-status"),
            "No EVM wallet detected. Install MetaMask to use this app.",
            "error",
        );
    } else {
        connectBtn.addEventListener("click", handleConnect);
        onAccountsChanged((addr) => {
            state.address = addr;
            if (!addr) state.walletChainId = null;
            renderConnectButton();
            refreshQuoteBtn();
        });
        onChainChanged((chainId) => {
            state.walletChainId = chainId;
            renderConnectButton();
        });
    }

    // Selector de cotización: fijo en Ethereum, deshabilitado.
    const chainSel = $("chain-select");
    if (chainSel) chainSel.disabled = true;

    // Selector de ejecución: controla state.executionChainId.
    const execSel = $("execution-chain-select");
    if (execSel) {
        execSel.addEventListener("change", (e) => {
            onExecutionChainChanged(parseInt(e.target.value, 10) || 1);
        });
        state.executionChainId = parseInt(execSel.value, 10) || 1;
    }

    $("token-in-select").addEventListener("change", () => {
        clearQuotesAndStatus();
        refreshQuoteBtn();
    });
    $("token-out-select").addEventListener("change", () => {
        clearQuotesAndStatus();
        refreshQuoteBtn();
    });
    $("amount-in").addEventListener("input", () => {
        clearQuotesAndStatus();
        refreshQuoteBtn();
    });
    $("quote-btn").addEventListener("click", handleGetQuotes);

    renderConnectButton();
    loadChains();
}

init();
