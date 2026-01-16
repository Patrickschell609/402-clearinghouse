#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-STABLECOIN CLEARINGHOUSE DEPLOYMENT
# Deploys Clearinghouse402Multi with full stablecoin support
# ═══════════════════════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════════════"
echo "  CLEARINGHOUSE402MULTI DEPLOYMENT"
echo "  Network: Base Mainnet (Chain ID: 8453)"
echo "═══════════════════════════════════════════════════════════════════"

# Check required environment variables
if [ -z "$PRIVATE_KEY" ]; then
    echo "ERROR: PRIVATE_KEY not set"
    echo "Run: export PRIVATE_KEY=0x..."
    exit 1
fi

# Contract directory
CONTRACT_DIR="/home/python/Desktop/402infer/contracts"
cd "$CONTRACT_DIR"

# RPC URL
RPC_URL="https://mainnet.base.org"

# Get deployer address
DEPLOYER=$(cast wallet address --private-key $PRIVATE_KEY)
echo "Deployer/Treasury: $DEPLOYER"

# Base mainnet stablecoin addresses
USDC="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USDT="0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2"
DAI="0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb"
PYUSD="0xCfA3Ef56d303AE4fAabA0592388F19d7C3399FB4"

echo ""
echo "[1/3] Deploying Clearinghouse402Multi..."
echo "─────────────────────────────────────────────────────────────────────"

# Deploy with deployer as treasury
CLEARINGHOUSE_DEPLOY=$(forge create src/Clearinghouse402Multi.sol:Clearinghouse402Multi \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $DEPLOYER \
    --json)

CLEARINGHOUSE_ADDRESS=$(echo $CLEARINGHOUSE_DEPLOY | jq -r '.deployedTo')
echo "Clearinghouse402Multi deployed: $CLEARINGHOUSE_ADDRESS"

# Verify on BaseScan
if [ -n "$BASESCAN_API_KEY" ]; then
    echo "Verifying on BaseScan..."
    forge verify-contract $CLEARINGHOUSE_ADDRESS src/Clearinghouse402Multi.sol:Clearinghouse402Multi \
        --chain-id 8453 \
        --etherscan-api-key $BASESCAN_API_KEY \
        --constructor-args $(cast abi-encode "constructor(address)" $DEPLOYER) \
        --watch || true
fi

echo ""
echo "[2/3] Whitelisting stablecoins..."
echo "─────────────────────────────────────────────────────────────────────"

echo "Whitelisting USDC..."
cast send $CLEARINGHOUSE_ADDRESS "whitelistToken(address,bool)" $USDC true \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY

echo "Whitelisting USDT..."
cast send $CLEARINGHOUSE_ADDRESS "whitelistToken(address,bool)" $USDT true \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY

echo "Whitelisting DAI..."
cast send $CLEARINGHOUSE_ADDRESS "whitelistToken(address,bool)" $DAI true \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY

echo "Whitelisting PYUSD..."
cast send $CLEARINGHOUSE_ADDRESS "whitelistToken(address,bool)" $PYUSD true \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY

echo ""
echo "[3/3] Verifying configuration..."
echo "─────────────────────────────────────────────────────────────────────"

echo "Owner: $(cast call $CLEARINGHOUSE_ADDRESS 'owner()(address)' --rpc-url $RPC_URL)"
echo "Treasury: $(cast call $CLEARINGHOUSE_ADDRESS 'treasury()(address)' --rpc-url $RPC_URL)"
echo "Fee BPS: $(cast call $CLEARINGHOUSE_ADDRESS 'FEE_BPS()(uint256)' --rpc-url $RPC_URL)"
echo "Paused: $(cast call $CLEARINGHOUSE_ADDRESS 'paused()(bool)' --rpc-url $RPC_URL)"

echo ""
echo "Whitelisted tokens:"
echo "  USDC: $(cast call $CLEARINGHOUSE_ADDRESS 'whitelistedTokens(address)(bool)' $USDC --rpc-url $RPC_URL)"
echo "  USDT: $(cast call $CLEARINGHOUSE_ADDRESS 'whitelistedTokens(address)(bool)' $USDT --rpc-url $RPC_URL)"
echo "  DAI:  $(cast call $CLEARINGHOUSE_ADDRESS 'whitelistedTokens(address)(bool)' $DAI --rpc-url $RPC_URL)"
echo "  PYUSD: $(cast call $CLEARINGHOUSE_ADDRESS 'whitelistedTokens(address)(bool)' $PYUSD --rpc-url $RPC_URL)"

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Clearinghouse402Multi: $CLEARINGHOUSE_ADDRESS"
echo ""
echo "Supported Stablecoins:"
echo "  - USDC:  $USDC"
echo "  - USDT:  $USDT"
echo "  - DAI:   $DAI"
echo "  - PYUSD: $PYUSD"
echo ""
echo "Supported Auth Methods:"
echo "  - 0x01: Permit2"
echo "  - 0x02: EIP-2612"
echo "  - 0x03: DAI Permit"
echo "  - 0x04: Direct Transfer"
echo "  - 0x05: ERC-3009"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
