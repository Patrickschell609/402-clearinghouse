#!/bin/bash
# ============================================================
# 402 CLEARINGHOUSE - STARTUP SCRIPT
# ============================================================
#
# Read this entire file before doing anything.
#
# This project is an x402-compliant API gateway that lets AI 
# agents buy tokenized Treasury Bills using ZK proofs.
#
# ============================================================
# PROJECT STRUCTURE
# ============================================================
#
# /contracts    - Solidity smart contracts (Foundry)
# /server       - Rust HTTP server (Axum) - the x402 API
# /circuits     - SP1 ZK compliance circuit (Rust)
# /agent        - Example autonomous agent client
# /docs         - OpenAPI spec
# /tests        - E2E integration tests
#
# ============================================================
# STEP 1: DEPLOY CONTRACTS TO BASE SEPOLIA
# ============================================================
#
# Prerequisites:
#   - Foundry installed (curl -L https://foundry.paradigm.xyz | bash && foundryup)
#   - A wallet with Base Sepolia ETH (get from faucet)
#
# Commands:
#   cd contracts
#   cp ../.env.example ../.env
#   # Edit .env and add your PRIVATE_KEY
#   forge install
#   forge build
#   forge script script/Deploy.s.sol --rpc-url https://sepolia.base.org --broadcast
#
# Save the output addresses - you'll need them for the server.
#
# ============================================================
# STEP 2: CONFIGURE ENVIRONMENT
# ============================================================
#
# Edit .env with the deployed contract addresses:
#
#   CLEARINGHOUSE_ADDRESS=0x...  (from deploy output)
#   USDC_ADDRESS=0x...           (from deploy output)
#   TBILL_ADDRESS=0x...          (from deploy output)
#
# ============================================================
# STEP 3: START THE SERVER
# ============================================================
#
# Prerequisites:
#   - Rust installed (curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh)
#
# Commands:
#   cd server
#   cargo build --release
#   cargo run --release
#
# Server will start on http://localhost:8080
#
# ============================================================
# STEP 4: TEST THE FLOW
# ============================================================
#
# In a new terminal:
#
#   # List available assets
#   curl http://localhost:8080/api/v1/assets
#
#   # Get a quote
#   curl "http://localhost:8080/api/v1/trade/quote/TBILL-26?amount=100"
#
#   # Trigger 402 challenge
#   curl -i "http://localhost:8080/api/v1/trade/buy/TBILL-26?amount=100"
#   # Should return 402 Payment Required with X-402-* headers
#
#   # Run the agent demo
#   cd agent
#   cargo run -- buy --asset TBILL-26 --amount 100 --dry-run
#
#   # Run E2E test
#   pip install requests
#   python tests/e2e_test.py
#
# ============================================================
# WHAT SUCCESS LOOKS LIKE
# ============================================================
#
# 1. Server responds to /health with chain info
# 2. GET /trade/buy returns 402 with custom headers
# 3. Agent demo shows the full negotiate → prove → settle flow
# 4. E2E test passes all checks
#
# ============================================================
# PRIORITY TASKS
# ============================================================
#
# 1. Get contracts deployed to Base Sepolia
# 2. Get server running and responding to health checks
# 3. Verify 402 challenge flow works
# 4. Run the agent demo end-to-end
# 5. Record a terminal demo showing an agent buying a T-Bill
#
# ============================================================
# KEY FILES TO UNDERSTAND
# ============================================================
#
# contracts/src/Clearinghouse402.sol  - The settlement contract
# server/src/handlers.rs              - x402 protocol logic
# server/src/services/blockchain.rs   - Chain interaction
# circuits/src/main.rs                - ZK compliance circuit
# agent/src/main.rs                   - Agent client demo
# docs/openapi.yaml                   - Full API spec
#
# ============================================================
# IF THINGS BREAK
# ============================================================
#
# - Contract deploy fails: Check PRIVATE_KEY in .env, ensure wallet has Sepolia ETH
# - Server won't start: Check CLEARINGHOUSE_ADDRESS and USDC_ADDRESS are set
# - 402 not returning: Check the asset is listed (look at Deploy.s.sol)
# - Agent fails: Make sure server is running on port 8080
#
# ============================================================

set -e

echo "========================================"
echo "  402 CLEARINGHOUSE - QUICK START"
echo "========================================"
echo ""

# Check for required tools
command -v cargo >/dev/null 2>&1 || { echo "Rust not installed. Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"; exit 1; }
command -v forge >/dev/null 2>&1 || { echo "Foundry not installed. Run: curl -L https://foundry.paradigm.xyz | bash && foundryup"; exit 1; }

echo "✓ Rust installed"
echo "✓ Foundry installed"
echo ""

# Check for .env
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add:"
    echo "   - PRIVATE_KEY (wallet with Base Sepolia ETH)"
    echo "   - Contract addresses (after deployment)"
    echo ""
    exit 1
fi

echo "✓ .env exists"
echo ""

# Source environment
source .env

# Check required vars
if [ -z "$CLEARINGHOUSE_ADDRESS" ] || [ "$CLEARINGHOUSE_ADDRESS" = "0x..." ]; then
    echo "⚠️  CLEARINGHOUSE_ADDRESS not set in .env"
    echo ""
    echo "Run deployment first:"
    echo "  cd contracts && forge script script/Deploy.s.sol --rpc-url https://sepolia.base.org --broadcast"
    echo ""
    echo "Then update .env with the output addresses."
    exit 1
fi

echo "✓ Environment configured"
echo ""
echo "Starting server..."
echo ""

cd server
cargo run --release
