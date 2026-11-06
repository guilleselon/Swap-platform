// wallet.js — MetaMask wrapper. Zero dependencies.
// All calls go through window.ethereum (EIP-1193).

const CHAIN_NAMES = {
    1: "Ethereum",
    56: "BNB Chain",
    137: "Polygon",
};

// -- ERC20 function selectors ----------------------------------------------
const SEL_ALLOWANCE = "0xdd62ed3e"; // allowance(address,address)
const SEL_APPROVE   = "0x095ea7b3"; // approve(address,uint256)

export function isWalletAvailable() {
    return typeof window.ethereum !== "undefined";
}

export async function connectWallet() {
    if (!isWalletAvailable()) {
        throw new Error(
            "No EVM wallet detected. Install MetaMask (https://metamask.io)."
        );
    }
    const accounts = await window.ethereum.request({
        method: "eth_requestAccounts",
    });
    if (!accounts || accounts.length === 0) {
        throw new Error("No account was authorized.");
    }
    const chainIdHex = await window.ethereum.request({ method: "eth_chainId" });
    return { address: accounts[0], chainId: parseInt(chainIdHex, 16) };
}

export async function getCurrentChainId() {
    const hex = await window.ethereum.request({ method: "eth_chainId" });
    return parseInt(hex, 16);
}

export function onAccountsChanged(handler) {
    if (!isWalletAvailable()) return () => {};
    const listener = (accounts) => handler(accounts?.[0] ?? null);
    window.ethereum.on("accountsChanged", listener);
    return () => window.ethereum.removeListener("accountsChanged", listener);
}

export function onChainChanged(handler) {
    if (!isWalletAvailable()) return () => {};
    const listener = (hex) => handler(parseInt(hex, 16));
    window.ethereum.on("chainChanged", listener);
    return () => window.ethereum.removeListener("chainChanged", listener);
}

export async function switchChain(chainId) {
    const hex = "0x" + chainId.toString(16);
    try {
        await window.ethereum.request({
            method: "wallet_switchEthereumChain",
            params: [{ chainId: hex }],
        });
    } catch (err) {
        if (err?.code === 4902) {
            throw new Error(
                `Chain ${chainId} is not configured in your wallet. ` +
                `Add it manually in MetaMask.`
            );
        }
        throw err;
    }
}

// -- ERC20 helpers ---------------------------------------------------------

function pad32(hexNo0x) {
    return hexNo0x.toLowerCase().padStart(64, "0");
}

async function ethCall(to, data) {
    const result = await window.ethereum.request({
        method: "eth_call",
        params: [{ to, data }, "latest"],
    });
    return result;
}

export async function getAllowance(tokenAddress, owner, spender) {
    const data =
        SEL_ALLOWANCE +
        pad32(owner.slice(2)) +
        pad32(spender.slice(2));
    const raw = await ethCall(tokenAddress, data);
    if (!raw || raw === "0x") return 0n;
    return BigInt(raw);
}

export async function sendApprove(tokenAddress, spender, amount) {
    const data =
        SEL_APPROVE +
        pad32(spender.slice(2)) +
        pad32(amount.toString(16));
    return window.ethereum.request({
        method: "eth_sendTransaction",
        params: [{ from: (await currentAddress()), to: tokenAddress, data, value: "0x0" }],
    });
}

export async function currentAddress() {
    const accounts = await window.ethereum.request({ method: "eth_accounts" });
    if (!accounts || accounts.length === 0) {
        throw new Error("Wallet is not connected.");
    }
    return accounts[0];
}

// -- Transactions ----------------------------------------------------------

export async function sendTransaction({ from, to, data, value }) {
    return window.ethereum.request({
        method: "eth_sendTransaction",
        params: [{
            from,
            to,
            data,
            value: value ? "0x" + BigInt(value).toString(16) : "0x0",
        }],
    });
}

export async function waitForReceipt(txHash, { timeoutMs = 120_000, pollMs = 2_000 } = {}) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        const receipt = await window.ethereum.request({
            method: "eth_getTransactionReceipt",
            params: [txHash],
        });
        if (receipt) return receipt;
        await new Promise((r) => setTimeout(r, pollMs));
    }
    throw new Error("Timed out waiting for transaction confirmation.");
}

// -- Misc ------------------------------------------------------------------

export function shortAddress(addr) {
    if (!addr) return "";
    return addr.slice(0, 6) + "…" + addr.slice(-4);
}

export function chainName(chainId) {
    return CHAIN_NAMES[chainId] ?? `Chain ${chainId}`;
}
