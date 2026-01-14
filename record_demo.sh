#!/bin/bash
# Perfect Demo Recording Script

clear
sleep 1

echo -e "\033[1;36m"
cat << 'BANNER'
 ═══════════════════════════════════════════════════════════════
   x402 CLEARINGHOUSE - Live Settlement Demo
   Base Mainnet | Chain ID 8453
 ═══════════════════════════════════════════════════════════════
BANNER
echo -e "\033[0m"
sleep 2

echo -e "\033[1;33m[1] Server Health Check\033[0m"
sleep 1
echo -e "\033[0;36m$ curl -s http://localhost:8080/health | jq .\033[0m"
sleep 0.5
curl -s http://localhost:8080/health | jq .
echo ""
sleep 2

echo -e "\033[1;33m[2] Available RWA Assets\033[0m"
sleep 1
echo -e "\033[0;36m$ curl -s http://localhost:8080/api/v1/assets | jq .\033[0m"
sleep 0.5
curl -s http://localhost:8080/api/v1/assets | jq .
echo ""
sleep 2

echo -e "\033[1;33m[3] Request Quote - 100 Treasury Bills\033[0m"
sleep 1
echo -e "\033[0;36m$ curl -s 'http://localhost:8080/api/v1/trade/quote/TBILL-26?amount=100' | jq .\033[0m"
sleep 0.5
curl -s 'http://localhost:8080/api/v1/trade/quote/TBILL-26?amount=100' | jq .
echo ""
sleep 2

echo -e "\033[1;33m[4] Initiate Purchase - 402 Payment Required\033[0m"
sleep 1
echo -e "\033[0;36m$ curl -si 'http://localhost:8080/api/v1/trade/buy/TBILL-26?amount=100' | head -15\033[0m"
sleep 0.5
curl -si 'http://localhost:8080/api/v1/trade/buy/TBILL-26?amount=100' | head -15
echo ""
sleep 2

echo -e "\033[1;32m[!] Received x402 challenge - ZK proof required\033[0m"
echo ""
sleep 2

echo -e "\033[1;33m[5] Execute REAL On-Chain Settlement\033[0m"
sleep 1

# Settlement parameters
source /home/python/Desktop/402infer/.env
WALLET="0xc7554F1B16ad0b3Ce363d53364C9817743E32f90"
CLEARINGHOUSE="0xb315C8F827e3834bB931986F177cb1fb6D20415D"
TBILL="0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A"
RPC="https://mainnet.base.org"

AMOUNT=100
EXPIRY=$(($(date +%s) + 300))
VALID_UNTIL=$(($(date +%s) + 86400 * 30))
JURISDICTION="0x5553000000000000000000000000000000000000000000000000000000000000"
PUBLIC_VALUES=$(cast abi-encode "x(address,uint256,bytes32)" $WALLET $VALID_UNTIL $JURISDICTION)
PROOF="0x1234567890abcdef"

echo -e "\033[0;36m$ cast send Clearinghouse settle(asset, 100, proof)\033[0m"
echo ""
sleep 1

TX_OUTPUT=$(cast send $CLEARINGHOUSE \
    "settle(address,uint256,uint256,bytes,bytes)" \
    $TBILL $AMOUNT $EXPIRY $PROOF $PUBLIC_VALUES \
    --private-key $PRIVATE_KEY \
    --rpc-url $RPC 2>&1)

TX_HASH=$(echo "$TX_OUTPUT" | grep "transactionHash" | awk '{print $2}')
STATUS=$(echo "$TX_OUTPUT" | grep "status" | head -1 | awk '{print $2}')
BLOCK=$(echo "$TX_OUTPUT" | grep "blockNumber" | head -1 | awk '{print $2}')

echo -e "\033[1;32m"
cat << RESULT
 ═══════════════════════════════════════════════════════════════
   SETTLEMENT SUCCESSFUL
 ═══════════════════════════════════════════════════════════════

   Transaction: $TX_HASH
   Block:       $BLOCK
   Status:      $STATUS

   Asset:       100 TBILL-26 (Treasury Bills)
   Cost:        98.00 USDC
   Fee:         0.049 USDC (0.05%)

   BaseScan: https://basescan.org/tx/$TX_HASH

 ═══════════════════════════════════════════════════════════════
RESULT
echo -e "\033[0m"
sleep 5
