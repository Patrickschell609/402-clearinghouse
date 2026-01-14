#!/bin/bash
# ============================================================
# STATUS CHECK - x402 Clearinghouse
# ============================================================
# Quick check of all deployed contracts and balances
# ============================================================

# Configuration
WALLET="0xc7554F1B16ad0b3Ce363d53364C9817743E32f90"
CLEARINGHOUSE="0xb315C8F827e3834bB931986F177cb1fb6D20415D"
USDC="0x6020Ed65e0008242D9094D107D97dd17599dc21C"
TBILL="0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A"
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
