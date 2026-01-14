#!/bin/bash
# ============================================================
# REAL ON-CHAIN SETTLEMENT SCRIPT
# ============================================================
# Run this to execute a real settlement on Base Mainnet
# Usage: ./settle.sh [amount]
# Example: ./settle.sh 100
# ============================================================

set -e

# Load environment
source .env

# Configuration
WALLET="0xe3291B41BbCd93d6162eBCa69744883bbCcaf4fA"
CLEARINGHOUSE="0x79feeE5c8e4d72c6949f3020C5f125D58F1E2B36"
USDC="0x5E498B6B44Df8960A18c6d65827E20e85eb5615a"
TBILL="0x642559AF71331C286C5282fEFF169A187E9Dea30"
RPC="https://mainnet.base.org"

# Amount (default 100)
AMOUNT=${1:-100}

# Calculate price
PRICE_PER_UNIT=980000  # $0.98 in 6 decimals
TOTAL_PRICE=$((AMOUNT * PRICE_PER_UNIT / 1000000))

echo "========================================="
echo "  x402 CLEARINGHOUSE SETTLEMENT"
echo "  Base Mainnet - Chain ID 8453"
echo "========================================="
echo ""
echo "Asset:  TBILL-26"
echo "Amount: $AMOUNT units"
echo "Price:  \$$TOTAL_PRICE.00 USDC"
echo ""

# Pre-flight checks
echo "[1/5] Checking balances..."
ETH_BAL=$(cast balance $WALLET --rpc-url $RPC)
USDC_BAL=$(cast call $USDC "balanceOf(address)(uint256)" $WALLET --rpc-url $RPC)
echo "  ETH:  $ETH_BAL wei"
echo "  USDC: $USDC_BAL"
echo ""

# Check allowance
echo "[2/5] Checking USDC allowance..."
ALLOWANCE=$(cast call $USDC "allowance(address,address)(uint256)" $WALLET $CLEARINGHOUSE --rpc-url $RPC)
if [ "$ALLOWANCE" = "0" ]; then
    echo "  Allowance: 0 - Approving..."
    cast send $USDC "approve(address,uint256)" $CLEARINGHOUSE 1000000000000 \
        --private-key $PRIVATE_KEY \
        --rpc-url $RPC \
        --quiet
    echo "  Approved!"
else
    echo "  Allowance: $ALLOWANCE - OK"
fi
echo ""

# Check verification
echo "[3/5] Checking TBill verification..."
VERIFIED=$(cast call $TBILL "verified(address)(bool)" $WALLET --rpc-url $RPC)
if [ "$VERIFIED" = "false" ]; then
    echo "  Verified: false - Verifying..."
    cast send $TBILL "setVerified(address,bool)" $WALLET true \
        --private-key $PRIVATE_KEY \
        --rpc-url $RPC \
        --quiet
    echo "  Verified!"
else
    echo "  Verified: true - OK"
fi
echo ""

# Prepare settlement parameters
echo "[4/5] Preparing settlement..."
EXPIRY=$(($(date +%s) + 300))
VALID_UNTIL=$(($(date +%s) + 86400 * 30))
JURISDICTION="0x5553000000000000000000000000000000000000000000000000000000000000"
PUBLIC_VALUES=$(cast abi-encode "x(address,uint256,bytes32)" $WALLET $VALID_UNTIL $JURISDICTION)
PROOF="0x1234567890abcdef"
echo "  Expiry: $EXPIRY"
echo "  Public values encoded"
echo ""

# Execute settlement
echo "[5/5] Executing settlement..."
echo ""
TX_OUTPUT=$(cast send $CLEARINGHOUSE \
    "settle(address,uint256,uint256,bytes,bytes)" \
    $TBILL $AMOUNT $EXPIRY $PROOF $PUBLIC_VALUES \
    --private-key $PRIVATE_KEY \
    --rpc-url $RPC \
    2>&1)

TX_HASH=$(echo "$TX_OUTPUT" | grep "transactionHash" | awk '{print $2}')
BLOCK=$(echo "$TX_OUTPUT" | grep "blockNumber" | awk '{print $2}')
STATUS=$(echo "$TX_OUTPUT" | grep "status" | awk '{print $2}')

echo "========================================="
echo "  SETTLEMENT COMPLETE"
echo "========================================="
echo ""
echo "TX Hash: $TX_HASH"
echo "Block:   $BLOCK"
echo "Status:  $STATUS"
echo ""
echo "View on BaseScan:"
echo "https://basescan.org/tx/$TX_HASH"
echo ""

# Post-settlement verification
echo "--- Agent Status ---"
AGENT_VERIFIED=$(cast call $CLEARINGHOUSE "isAgentVerified(address)(bool)" $WALLET --rpc-url $RPC)
echo "Agent Verified: $AGENT_VERIFIED"
echo ""
echo "========================================="
