// Curated token list per chain. Extend freely.
// The native pseudo-address is recognised by the backend and rewritten
// to the wrapped native token in the router calldata.

export const NATIVE_ADDRESS =
    "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE";

export const TOKENS_BY_CHAIN = {
    1: [
        { address: NATIVE_ADDRESS, symbol: "ETH",  decimals: 18 },
        { address: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", symbol: "WETH", decimals: 18 },
        { address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", symbol: "USDC", decimals: 6  },
        { address: "0xdAC17F958D2ee523a2206206994597C13D831ec7", symbol: "USDT", decimals: 6  },
        { address: "0x6B175474E89094C44Da98b954EedeAC495271d0F", symbol: "DAI",  decimals: 18 },
        { address: "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599", symbol: "WBTC", decimals: 8  },
    ],
    56: [
        { address: NATIVE_ADDRESS, symbol: "BNB",  decimals: 18 },
        { address: "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c", symbol: "WBNB", decimals: 18 },
        { address: "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", symbol: "USDC", decimals: 18 },
        { address: "0x55d398326f99059fF775485246999027B3197955", symbol: "USDT", decimals: 18 },
        { address: "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56", symbol: "BUSD", decimals: 18 },
    ],
    137: [
        { address: NATIVE_ADDRESS, symbol: "MATIC", decimals: 18 },
        { address: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270", symbol: "WMATIC", decimals: 18 },
        { address: "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", symbol: "USDC",   decimals: 6  },
        { address: "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", symbol: "USDT",   decimals: 6  },
        { address: "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", symbol: "DAI",    decimals: 18 },
    ],
    11155111: [
        { address: NATIVE_ADDRESS, symbol: "ETH",  decimals: 18 },
        { address: "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14", symbol: "WETH", decimals: 18 },
        { address: "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238", symbol: "USDC", decimals: 6  },
    ],
};

export function tokensForChain(chainId) {
    return TOKENS_BY_CHAIN[chainId] ?? [];
}

export function isNative(token) {
    return token?.address?.toLowerCase() === NATIVE_ADDRESS.toLowerCase();
}

export function tokenBySymbol(symbol, chainId) {
    const tokens = TOKENS_BY_CHAIN[chainId] ?? [];
    return tokens.find((t) => t.symbol === symbol) ?? null;
}
