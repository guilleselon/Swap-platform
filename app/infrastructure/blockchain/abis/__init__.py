"""Minimal ABIs — only the functions the platform actually calls."""

from __future__ import annotations

ERC20_ABI: list[dict] = [
    {"constant": True, "inputs": [], "name": "decimals",
     "outputs": [{"name": "", "type": "uint8"}], "stateMutability": "view",
     "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol",
     "outputs": [{"name": "", "type": "string"}], "stateMutability": "view",
     "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}],
     "name": "balanceOf",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view",
     "type": "function"},
    {"constant": True,
     "inputs": [{"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"}],
     "name": "allowance",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view",
     "type": "function"},
    {"constant": False,
     "inputs": [{"name": "spender", "type": "address"},
                {"name": "amount", "type": "uint256"}],
     "name": "approve",
     "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable",
     "type": "function"},
]

UNISWAP_V2_ROUTER_ABI: list[dict] = [
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"},
        ],
        "name": "getAmountsOut",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactETHForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"},
        ],
        "name": "swapExactTokensForETH",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

UNISWAP_V2_FACTORY_ABI: list[dict] = [
    {
        "inputs": [
            {"name": "tokenA", "type": "address"},
            {"name": "tokenB", "type": "address"},
        ],
        "name": "getPair",
        "outputs": [{"name": "pair", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
]

UNISWAP_V2_PAIR_ABI: list[dict] = [
    {"inputs": [], "name": "token0",
     "outputs": [{"name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "token1",
     "outputs": [{"name": "", "type": "address"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "getReserves",
     "outputs": [
         {"name": "reserve0", "type": "uint112"},
         {"name": "reserve1", "type": "uint112"},
         {"name": "blockTimestampLast", "type": "uint32"},
     ],
     "stateMutability": "view", "type": "function"},
]
