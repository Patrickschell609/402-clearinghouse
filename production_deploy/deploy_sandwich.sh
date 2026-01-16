#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# SANDWICH MODEL DEPLOYMENT SCRIPT
# Deploys updated AgentRegistry + AIGuardian with TEE/MPC support
# ═══════════════════════════════════════════════════════════════════════════════

set -e

echo "═══════════════════════════════════════════════════════════════════"
echo "  SANDWICH MODEL DEPLOYMENT"
echo "  Network: Base Mainnet (Chain ID: 8453)"
echo "═══════════════════════════════════════════════════════════════════"

# Check required environment variables
if [ -z "$PRIVATE_KEY" ]; then
    echo "ERROR: PRIVATE_KEY not set"
    echo "Run: export PRIVATE_KEY=0x..."
    exit 1
fi

if [ -z "$BASESCAN_API_KEY" ]; then
    echo "WARNING: BASESCAN_API_KEY not set - contracts won't be verified"
fi

# Contract directory
CONTRACT_DIR="/home/python/Desktop/402infer/contracts"
cd "$CONTRACT_DIR"

# RPC URL
RPC_URL="https://mainnet.base.org"

echo ""
echo "[1/4] Deploying AgentRegistry..."
echo "─────────────────────────────────────────────────────────────────────"

REGISTRY_DEPLOY=$(forge create src/AgentRegistry.sol:AgentRegistry \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --json)

REGISTRY_ADDRESS=$(echo $REGISTRY_DEPLOY | jq -r '.deployedTo')
echo "AgentRegistry deployed: $REGISTRY_ADDRESS"

# Verify on BaseScan
if [ -n "$BASESCAN_API_KEY" ]; then
    echo "Verifying on BaseScan..."
    forge verify-contract $REGISTRY_ADDRESS src/AgentRegistry.sol:AgentRegistry \
        --chain-id 8453 \
        --etherscan-api-key $BASESCAN_API_KEY \
        --watch || true
fi

echo ""
echo "[2/4] Deploying AIGuardian..."
echo "─────────────────────────────────────────────────────────────────────"

# SP1 Verifier on Base mainnet (Succinct Labs)
SP1_VERIFIER="0xDd2ffa97F680032332EA4905586e2366584Ae0be"

# Program vKey (from your SP1 circuit compilation)
# UPDATE THIS with your actual vKey!
PROGRAM_VKEY="0x007c7f386f0ccc16d2a18c3ef536e4c91b0839a2b91b5935ced528715ec581f6"

GUARDIAN_DEPLOY=$(forge create src/AIGuardian.sol:AIGuardian \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    --constructor-args $SP1_VERIFIER $PROGRAM_VKEY \
    --json)

GUARDIAN_ADDRESS=$(echo $GUARDIAN_DEPLOY | jq -r '.deployedTo')
echo "AIGuardian deployed: $GUARDIAN_ADDRESS"

# Verify on BaseScan
if [ -n "$BASESCAN_API_KEY" ]; then
    echo "Verifying on BaseScan..."
    forge verify-contract $GUARDIAN_ADDRESS src/AIGuardian.sol:AIGuardian \
        --chain-id 8453 \
        --etherscan-api-key $BASESCAN_API_KEY \
        --constructor-args $(cast abi-encode "constructor(address,bytes32)" $SP1_VERIFIER $PROGRAM_VKEY) \
        --watch || true
fi

echo ""
echo "[3/4] Configuring contracts..."
echo "─────────────────────────────────────────────────────────────────────"

# Set registry in AIGuardian
echo "Setting registry in AIGuardian..."
cast send $GUARDIAN_ADDRESS "setRegistry(address)" $REGISTRY_ADDRESS \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY

# Whitelist AIGuardian in Registry
echo "Whitelisting AIGuardian in Registry..."
cast send $REGISTRY_ADDRESS "whitelistProtocol(address)" $GUARDIAN_ADDRESS \
    --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY

echo ""
echo "[4/4] Deployment Summary"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "AgentRegistry:  $REGISTRY_ADDRESS"
echo "AIGuardian:     $GUARDIAN_ADDRESS"
echo "SP1 Verifier:   $SP1_VERIFIER"
echo "Program vKey:   $PROGRAM_VKEY"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "═══════════════════════════════════════════════════════════════════"

# Save addresses to file
cat > "$CONTRACT_DIR/deployed_addresses.json" << EOF
{
  "network": "base-mainnet",
  "chainId": 8453,
  "deployedAt": "$(date -Iseconds)",
  "contracts": {
    "AgentRegistry": "$REGISTRY_ADDRESS",
    "AIGuardian": "$GUARDIAN_ADDRESS",
    "SP1Verifier": "$SP1_VERIFIER"
  },
  "configuration": {
    "programVKey": "$PROGRAM_VKEY"
  }
}
EOF

echo ""
echo "Addresses saved to: $CONTRACT_DIR/deployed_addresses.json"
