"""Static knowledge about supported chains and DEXes.

To add a new EVM chain: add a ``Chain`` here, and at least one ``DEX`` to
``DEXES_BY_CHAIN``. Then set ``RPC_URL_<id>`` in .env.
"""

from __future__ import annotations

from app.domain.models import Chain, DEX, ProtocolVersion

# --------------------------------------------------------------------------- #
# Chains                                                                       #
# --------------------------------------------------------------------------- #

CHAINS: dict[int, Chain] = {
    1: Chain(
        id=1,
        name="Ethereum",
        native_symbol="ETH",
        wrapped_native_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        block_explorer_url="https://etherscan.io",
    ),
    56: Chain(
        id=56,
        name="BNB Smart Chain",
        native_symbol="BNB",
        wrapped_native_address="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        block_explorer_url="https://bscscan.com",
    ),
    137: Chain(
        id=137,
        name="Polygon",
        native_symbol="MATIC",
        wrapped_native_address="0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        block_explorer_url="https://polygonscan.com",
    ),
    11155111: Chain(
        id=11155111,
        name="Sepolia",
        native_symbol="ETH",
        wrapped_native_address="0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",
        block_explorer_url="https://sepolia.etherscan.io",
    ),    
}

# --------------------------------------------------------------------------- #
# DEXes                                                                        #
# --------------------------------------------------------------------------- #

DEXES_BY_CHAIN: dict[int, list[DEX]] = {
    1: [
        DEX(
            id="uniswap_v2",
            name="Uniswap V2",
            chain_id=1,
            router_address="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            factory_address="0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            protocol=ProtocolVersion.V2,
        ),
        DEX(
            id="sushiswap",
            name="SushiSwap",
            chain_id=1,
            router_address="0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
            factory_address="0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
            protocol=ProtocolVersion.V2,
        ),
    ],
    56: [
        DEX(
            id="pancakeswap_v2",
            name="PancakeSwap V2",
            chain_id=56,
            router_address="0x10ED43C718714eb63d5aA57B78B54704E256024E",
            factory_address="0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
            protocol=ProtocolVersion.V2,
        ),
    ],
    137: [
        DEX(
            id="quickswap",
            name="QuickSwap",
            chain_id=137,
            router_address="0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
            factory_address="0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32",
            protocol=ProtocolVersion.V2,
        ),
    ],
    11155111: [
        DEX(
            id="uniswap_v2_sepolia",
            name="Uniswap V2 (Sepolia)",
            chain_id=11155111,
            router_address="0xeE567Fe1712Faf6149d80dA1E6934E354124CfE3",
            factory_address="0xF62c03E08ada871A0bEb309762E260a7a6a880E6",
            protocol=ProtocolVersion.V2,
        ),
    ],
}
