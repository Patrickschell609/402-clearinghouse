#!/bin/bash
# x402 Clearinghouse Demo Recording Script
# This script will record a demo of the full x402 flow

set -e

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to type text slowly (for visual effect)
slow_type() {
    local text="$1"
    local delay="${2:-0.03}"
    for ((i=0; i<${#text}; i++)); do
        echo -n "${text:$i:1}"
        sleep $delay
    done
    echo
}

# Function to run command with display
run_cmd() {
    echo -e "${CYAN}\$ $1${NC}"
    sleep 0.5
    eval "$1"
    echo
    sleep 1
}

clear

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  x402 CLEARINGHOUSE DEMO${NC}"
echo -e "${GREEN}  Agent-Native RWA Settlement${NC}"
echo -e "${GREEN}======================================${NC}"
echo
sleep 2

# Step 1: Health check
echo -e "${YELLOW}[1] Checking server health...${NC}"
sleep 1
run_cmd "curl -s http://localhost:8080/health | jq ."

# Step 2: List assets
echo -e "${YELLOW}[2] Discovering available RWA assets...${NC}"
sleep 1
run_cmd "curl -s http://localhost:8080/api/v1/assets | jq ."

# Step 3: Get quote
echo -e "${YELLOW}[3] Getting quote for 100 T-Bills...${NC}"
sleep 1
run_cmd "curl -s 'http://localhost:8080/api/v1/trade/quote/TBILL-26?amount=100' | jq ."

# Step 4: x402 Challenge
echo -e "${YELLOW}[4] Initiating purchase - expecting 402 Payment Required...${NC}"
sleep 1
run_cmd "curl -si 'http://localhost:8080/api/v1/trade/buy/TBILL-26?amount=100' | head -20"

echo -e "${GREEN}[!] Server returned 402 with x402 protocol headers!${NC}"
echo
sleep 2

# Step 5: Agent demo
echo -e "${YELLOW}[5] Running autonomous agent to complete purchase...${NC}"
sleep 1
echo -e "${CYAN}\$ cd agent && cargo run --release -- buy --asset TBILL-26 --amount 100 --dry-run${NC}"
sleep 0.5
cd /home/python/Desktop/402infer/agent
cargo run --release -- buy --asset TBILL-26 --amount 100 --dry-run 2>/dev/null

echo
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  DEMO COMPLETE${NC}"
echo -e "${GREEN}======================================${NC}"
echo
echo "The agent successfully:"
echo "  1. Discovered the 402 challenge"
echo "  2. Parsed x402 protocol headers"
echo "  3. Evaluated risk parameters"
echo "  4. Generated ZK compliance proof"
echo "  5. Prepared atomic settlement"
echo
sleep 3
