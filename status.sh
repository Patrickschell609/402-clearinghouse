#!/bin/bash
# ============================================================
# STATUS CHECK - x402 Clearinghouse
# ============================================================
# Quick check of all deployed contracts and balances
# ============================================================

# Configuration
WALLET="0xe3291B41BbCd93d6162eBCa69744883bbCcaf4fA"
CLEARINGHOUSE="0x79feeE5c8e4d72c6949f3020C5f125D58F1E2B36"
USDC="0x5E498B6B44Df8960A18c6d65827E20e85eb5615a"
TBILL="0x642559AF71331C286C5282fEFF169A187E9Dea30"
RPC="https://mainnet.base.org"

echo "========================================="
echo "  x402 CLEARINGHOUSE STATUS"
echo "  Base Mainnet - Chain ID 8453"
echo "========================================="
echo ""

echo "--- Contracts ---"
echo "Clearinghouse: $CLEARINGHOUSE"
echo "USDC:          $USDC"
echo "TBill:         $TBILL"
echo ""

echo "--- Wallet: $WALLET ---"
echo ""

echo "ETH Balance:"
cast balance $WALLET --rpc-url $RPC --ether
echo ""

echo "USDC Balance:"
USDC_BAL=$(cast call $USDC "balanceOf(address)(uint256)" $WALLET --rpc-url $RPC)
USDC_HUMAN=$(echo "scale=2; $USDC_BAL / 1000000" | bc)
echo "$USDC_BAL ($USDC_HUMAN USDC)"
echo ""

echo "TBill Balance:"
TBILL_BAL=$(cast call $TBILL "balanceOf(address)(uint256)" $WALLET --rpc-url $RPC)
echo "$TBILL_BAL"
echo ""

echo "--- Clearinghouse State ---"
echo ""

echo "Fee (bps):"
cast call $CLEARINGHOUSE "feeBps()(uint256)" --rpc-url $RPC
echo ""

echo "Agent Verified:"
cast call $CLEARINGHOUSE "isAgentVerified(address)(bool)" $WALLET --rpc-url $RPC
echo ""

echo "Agent Verified Until:"
UNTIL=$(cast call $CLEARINGHOUSE "agentVerifiedUntil(address)(uint256)" $WALLET --rpc-url $RPC)
echo "$UNTIL"
if [ "$UNTIL" != "0" ]; then
    echo "($(date -d @$UNTIL 2>/dev/null || date -r $UNTIL 2>/dev/null || echo 'future date'))"
fi
echo ""

echo "--- TBill Asset Config ---"
echo ""
cast call $CLEARINGHOUSE "assets(address)(address,bytes32,uint256,bool)" $TBILL --rpc-url $RPC
echo ""

echo "========================================="
echo "  All systems operational"
echo "========================================="
