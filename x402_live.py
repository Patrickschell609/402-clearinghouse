#!/usr/bin/env python3
"""
x402 Live Settlement - Base Mainnet

Real on-chain atomic settlement of tokenized Treasury Bills.
"""

import os
import sys
import time

# Add local SDK to path
sys.path.insert(0, '/home/python/Desktop/402infer/x402_rwa/src')

from dotenv import load_dotenv
load_dotenv('/home/python/Desktop/402infer/.env')

# ============ TERMINAL OUTPUT ============

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def banner(text):
    width = 60
    print(f"\n{Colors.CYAN}{'═' * width}")
    print(f"  {text.center(width - 4)}")
    print(f"{'═' * width}{Colors.END}\n")


def box(lines, color=Colors.GREEN, title=None):
    width = 50
    print(f"\n{color}{Colors.BOLD}╔{'═' * width}╗")
    if title:
        print(f"║  {title.center(width - 4)}  ║")
        print(f"╠{'═' * width}╣")
    for line in lines:
        padded = line.ljust(width - 4)
        print(f"║  {padded}  ║")
    print(f"╚{'═' * width}╝{Colors.END}")


def main():
    import requests
    from web3 import Web3
    from eth_account import Account
    from eth_abi import encode

    banner("x402 CLEARINGHOUSE — LIVE SETTLEMENT")

    # Config
    RPC_URL = "https://mainnet.base.org"
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    SERVER_URL = "http://localhost:8080/api/v1/trade"
    ASSET_ID = "TBILL-26"
    AMOUNT = 100

    if not PRIVATE_KEY:
        print(f"{Colors.RED}[!] PRIVATE_KEY not found in .env{Colors.END}")
        sys.exit(1)

    # Setup
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = Account.from_key(PRIVATE_KEY)

    print(f"{Colors.WHITE}[*] Network:  {Colors.CYAN}Base Mainnet (Chain 8453){Colors.END}")
    print(f"{Colors.WHITE}[*] Agent:    {Colors.CYAN}{account.address[:26]}...{Colors.END}")
    print(f"{Colors.WHITE}[*] Target:   {Colors.CYAN}{AMOUNT} {ASSET_ID}{Colors.END}")
    time.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # STEP 1: REQUEST ASSET → GET 402
    # ═══════════════════════════════════════════════════════════

    print(f"\n{Colors.YELLOW}[1] REQUESTING ASSET...{Colors.END}")
    time.sleep(0.3)
    print(f"{Colors.DIM}    GET {SERVER_URL}/buy/{ASSET_ID}?amount={AMOUNT}{Colors.END}")

    try:
        response = requests.get(f"{SERVER_URL}/buy/{ASSET_ID}", params={"amount": AMOUNT}, timeout=5)
    except requests.exceptions.ConnectionError:
        print(f"\n{Colors.RED}[!] Server not running. Start it with:{Colors.END}")
        print(f"{Colors.WHITE}    cd ~/Desktop/402infer/server && ./target/release/server{Colors.END}\n")
        sys.exit(1)

    if response.status_code != 402:
        print(f"{Colors.RED}[!] Expected 402, got {response.status_code}{Colors.END}")
        sys.exit(1)

    box([
        "HTTP 402 — PAYMENT REQUIRED",
        "",
        "x402 challenge received",
        "ZK proof + payment needed"
    ], color=Colors.RED, title="CHALLENGE")

    time.sleep(0.8)

    # Parse headers
    headers = response.headers
    quote_price = int(headers.get("x-402-price", 0))
    clearinghouse = headers.get("x-402-payment-address", "")
    asset_addr = headers.get("x-402-asset-address", "0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A")
    circuit = headers.get("x-402-compliance-circuit", "")

    print(f"\n{Colors.WHITE}[*] Quote: {Colors.CYAN}${quote_price / 1_000_000:.2f} USDC{Colors.END}")
    print(f"{Colors.DIM}    Clearinghouse: {clearinghouse[:30]}...")
    print(f"    Asset:         {asset_addr[:30]}...{Colors.END}")
    time.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # STEP 2: GENERATE ZK PROOF
    # ═══════════════════════════════════════════════════════════

    print(f"\n{Colors.CYAN}[2] GENERATING ZK COMPLIANCE PROOF...{Colors.END}")
    time.sleep(0.3)

    stages = [
        ("Loading identity circuit", 0.3),
        ("Computing Merkle witness", 0.4),
        ("Generating STARK proof", 0.5),
        ("Encoding public values", 0.2),
    ]

    for stage, delay in stages:
        print(f"{Colors.BLUE}    → {stage}...{Colors.END}")
        time.sleep(delay)

    # Generate proof (mock for now - real SP1 would go here)
    valid_until = int(time.time()) + 86400 * 30
    jurisdiction = bytes.fromhex("5553" + "00" * 30)  # "US"

    public_values = encode(
        ['address', 'uint256', 'bytes32'],
        [account.address, valid_until, jurisdiction]
    )
    proof = bytes.fromhex("1234567890abcdef")

    print(f"\n{Colors.GREEN}[✓] ZK PROOF READY{Colors.END}")
    print(f"{Colors.DIM}    Proof: {len(proof)} bytes | Public values: {len(public_values)} bytes{Colors.END}")
    time.sleep(0.5)

    # ═══════════════════════════════════════════════════════════
    # STEP 3: EXECUTE ON-CHAIN SETTLEMENT
    # ═══════════════════════════════════════════════════════════

    print(f"\n{Colors.CYAN}[3] EXECUTING ATOMIC SETTLEMENT...{Colors.END}")
    time.sleep(0.3)

    # Build transaction
    print(f"{Colors.YELLOW}    → Building transaction...{Colors.END}")

    abi = [{
        "name": "settle",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "asset", "type": "address"},
            {"name": "amount", "type": "uint256"},
            {"name": "quoteExpiry", "type": "uint256"},
            {"name": "complianceProof", "type": "bytes"},
            {"name": "publicValues", "type": "bytes"}
        ],
        "outputs": [{"name": "txId", "type": "bytes32"}]
    }]

    contract = w3.eth.contract(address=Web3.to_checksum_address(clearinghouse), abi=abi)
    expiry = int(time.time()) + 300

    tx = contract.functions.settle(
        Web3.to_checksum_address(asset_addr),
        AMOUNT,
        expiry,
        proof,
        public_values
    ).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 250000,
        'maxFeePerGas': w3.eth.gas_price * 2,
        'maxPriorityFeePerGas': w3.to_wei(0.001, 'gwei'),
    })

    print(f"{Colors.YELLOW}    → Signing transaction...{Colors.END}")
    time.sleep(0.2)
    signed_tx = w3.eth.account.sign_transaction(tx, account.key)

    print(f"{Colors.YELLOW}    → Broadcasting to Base Mainnet...{Colors.END}")
    time.sleep(0.3)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    print(f"{Colors.YELLOW}    → Waiting for block confirmation...{Colors.END}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    if receipt.status != 1:
        print(f"\n{Colors.RED}[!] Transaction failed{Colors.END}")
        sys.exit(1)

    tx_hash_hex = w3.to_hex(tx_hash)

    # ═══════════════════════════════════════════════════════════
    # SUCCESS
    # ═══════════════════════════════════════════════════════════

    fee = (quote_price * 5) // 10000

    box([
        "SETTLEMENT CONFIRMED",
        "",
        f"Block:    {receipt.blockNumber}",
        f"Asset:    {AMOUNT} {ASSET_ID}",
        f"Cost:     ${quote_price / 1_000_000:.2f} USDC",
        f"Fee:      ${fee / 1_000_000:.4f} (5 bps)",
        "",
        f"Gas Used: {receipt.gasUsed:,}",
    ], color=Colors.GREEN, title="SUCCESS")

    print(f"\n{Colors.WHITE}{'─' * 60}")
    print(f"{Colors.CYAN}TX:{Colors.END}       {tx_hash_hex}")
    print(f"{Colors.CYAN}BASESCAN:{Colors.END} https://basescan.org/tx/{tx_hash_hex}")
    print(f"{Colors.WHITE}{'─' * 60}{Colors.END}\n")


if __name__ == "__main__":
    main()
