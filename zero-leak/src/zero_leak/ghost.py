#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   LAYER 3: THE GHOST                                            ║
║   Zero-Leak Defense System                                       ║
║                                                                  ║
║   Author: Patrick Schell (@Patrickschell609)                    ║
║   Type: Emergency Rescue System                                  ║
║   Mission: Extract funds before snipers via MEV bundles          ║
║                                                                  ║
║   "I am faster than the mempool. I move in shadows."            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import requests
from typing import Optional, Tuple, List, Dict, Any

try:
    from web3 import Web3
    from eth_account import Account
    from eth_account.signers.local import LocalAccount
except ImportError:
    Web3 = None
    Account = None
    LocalAccount = None


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


# ════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════

# MEV Relay endpoints
RELAYS = [
    ("Flashbots", "https://relay.flashbots.net"),
    ("Beaverbuild", "https://rpc.beaverbuild.org"),
    ("Titanbuilder", "https://rpc.titanbuilder.xyz"),
    ("Builder0x69", "https://builder0x69.io"),
    ("Rsync", "https://rsync-builder.xyz"),
]

# How many blocks to try
MAX_BLOCKS = 5

# Gas settings
GAS_LIMIT_FUND = 21000
GAS_LIMIT_SWEEP = 21000
PRIORITY_FEE_GWEI = 5


# ════════════════════════════════════════════════════════════════
# CORE FUNCTIONS
# ════════════════════════════════════════════════════════════════

def get_gas_params(w3: Any) -> Tuple[int, int]:
    """Get current gas parameters."""
    block = w3.eth.get_block('pending')
    base_fee = block.get('baseFeePerGas', w3.to_wei(30, 'gwei'))

    priority_fee = w3.to_wei(PRIORITY_FEE_GWEI, 'gwei')
    max_fee = base_fee * 2 + priority_fee

    return max_fee, priority_fee


def build_rescue_bundle(
    w3: Any,
    sponsor: Any,
    victim: Any,
    safe_address: str,
    target_block: int
) -> Tuple[List[str], Dict[str, Any]]:
    """
    Build an atomic bundle:
    1. Sponsor sends ETH to victim (for gas)
    2. Victim sweeps all to safe address

    Returns (list of signed tx hexes, bundle info)
    """

    max_fee, priority_fee = get_gas_params(w3)

    # Calculate how much gas the victim needs
    victim_gas_cost = GAS_LIMIT_SWEEP * max_fee

    # Get current balances
    victim_balance = w3.eth.get_balance(victim.address)
    sponsor_balance = w3.eth.get_balance(sponsor.address)

    print(f"\n{Colors.WHITE}[*] Victim balance:  {w3.from_wei(victim_balance, 'ether'):.6f} ETH{Colors.END}")
    print(f"{Colors.WHITE}[*] Sponsor balance: {w3.from_wei(sponsor_balance, 'ether'):.6f} ETH{Colors.END}")

    if victim_balance == 0:
        print(f"{Colors.YELLOW}[!] Victim wallet is empty. Nothing to rescue.{Colors.END}")
        return [], {}

    # Check if victim can pay for gas themselves
    if victim_balance > victim_gas_cost:
        # No funding needed, just sweep
        sweep_value = victim_balance - victim_gas_cost

        sweep_tx = {
            "to": Web3.to_checksum_address(safe_address),
            "value": sweep_value,
            "gas": GAS_LIMIT_SWEEP,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority_fee,
            "nonce": w3.eth.get_transaction_count(victim.address),
            "chainId": w3.eth.chain_id,
            "type": 2,
        }

        signed_sweep = victim.sign_transaction(sweep_tx)

        bundle_info = {
            "type": "sweep_only",
            "sweep_value": sweep_value,
            "gas_cost": victim_gas_cost,
        }

        return [signed_sweep.raw_transaction.hex()], bundle_info

    else:
        # Need to fund the victim first
        fund_amount = victim_gas_cost + 1000  # Small buffer

        if sponsor_balance < fund_amount + (GAS_LIMIT_FUND * max_fee):
            print(f"{Colors.RED}[!] Sponsor doesn't have enough ETH to fund rescue.{Colors.END}")
            return [], {}

        # TX 1: Sponsor funds victim
        fund_tx = {
            "to": victim.address,
            "value": fund_amount,
            "gas": GAS_LIMIT_FUND,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority_fee,
            "nonce": w3.eth.get_transaction_count(sponsor.address),
            "chainId": w3.eth.chain_id,
            "type": 2,
        }

        signed_fund = sponsor.sign_transaction(fund_tx)

        # TX 2: Victim sweeps everything
        sweep_value = victim_balance

        sweep_tx = {
            "to": Web3.to_checksum_address(safe_address),
            "value": sweep_value,
            "gas": GAS_LIMIT_SWEEP,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": priority_fee,
            "nonce": w3.eth.get_transaction_count(victim.address),
            "chainId": w3.eth.chain_id,
            "type": 2,
        }

        signed_sweep = victim.sign_transaction(sweep_tx)

        bundle_info = {
            "type": "fund_and_sweep",
            "fund_amount": fund_amount,
            "sweep_value": sweep_value,
            "gas_cost": victim_gas_cost,
        }

        return [
            signed_fund.raw_transaction.hex(),
            signed_sweep.raw_transaction.hex()
        ], bundle_info


def submit_to_relay(relay_name: str, relay_url: str, bundle: List[str], target_block: int) -> bool:
    """Submit bundle to a single relay."""

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_sendBundle",
        "params": [{
            "txs": [f"0x{tx}" if not tx.startswith("0x") else tx for tx in bundle],
            "blockNumber": hex(target_block),
        }]
    }

    headers = {
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(relay_url, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            result = response.json()
            if "error" not in result:
                return True
        return False

    except Exception:
        return False


def submit_bundle_to_all_relays(bundle: List[str], target_block: int) -> int:
    """Submit bundle to all relays simultaneously."""

    successful = 0

    for relay_name, relay_url in RELAYS:
        success = submit_to_relay(relay_name, relay_url, bundle, target_block)
        if success:
            print(f"  {Colors.GREEN}✓{Colors.END} {relay_name}")
            successful += 1
        else:
            print(f"  {Colors.DIM}✗ {relay_name}{Colors.END}")

    return successful


def run_rescue(
    rpc_url: Optional[str] = None,
    sponsor_pk: Optional[str] = None,
    leaked_pk: Optional[str] = None,
    safe_address: Optional[str] = None
) -> int:
    """Run the emergency rescue. Returns 0 on success, 1 on failure."""

    if Web3 is None:
        print(f"{Colors.RED}[ERROR]{Colors.END} web3 not installed. Run: pip install web3 eth-account")
        return 1

    # Get config from args or environment
    rpc_url = rpc_url or os.getenv("RPC_URL") or os.getenv("ETH_RPC_URL")
    sponsor_pk = sponsor_pk or os.getenv("SPONSOR_PK")
    leaked_pk = leaked_pk or os.getenv("LEAKED_PK")
    safe_address = safe_address or os.getenv("SAFE_ADDRESS")

    # Validate
    missing = []
    if not rpc_url:
        missing.append("RPC_URL")
    if not sponsor_pk:
        missing.append("SPONSOR_PK")
    if not leaked_pk:
        missing.append("LEAKED_PK")
    if not safe_address:
        missing.append("SAFE_ADDRESS")

    if missing:
        print(f"\n{Colors.RED}[ERROR]{Colors.END} Missing required configuration:")
        for m in missing:
            print(f"  - {m}")
        print(f"\nSet via environment variables or command line arguments.")
        print(f"Run with --help for usage.\n")
        return 1

    # Initialize
    print(f"\n{Colors.CYAN}{'═' * 60}")
    print(f"  LAYER 3: THE GHOST — Emergency Rescue Protocol")
    print(f"{'═' * 60}{Colors.END}\n")

    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        print(f"{Colors.RED}[ERROR]{Colors.END} Cannot connect to RPC: {rpc_url}")
        return 1

    sponsor = Account.from_key(sponsor_pk)
    victim = Account.from_key(leaked_pk)

    print(f"{Colors.WHITE}[*] Network:     Chain {w3.eth.chain_id}{Colors.END}")
    print(f"{Colors.WHITE}[*] Sponsor:     {sponsor.address[:20]}...{Colors.END}")
    print(f"{Colors.WHITE}[*] Compromised: {victim.address[:20]}...{Colors.END}")
    print(f"{Colors.WHITE}[*] Safe:        {safe_address[:20]}...{Colors.END}")

    # Build bundle
    print(f"\n{Colors.YELLOW}[1] Building rescue bundle...{Colors.END}")

    current_block = w3.eth.block_number
    target_block = current_block + 1

    bundle, info = build_rescue_bundle(w3, sponsor, victim, safe_address, target_block)

    if not bundle:
        print(f"\n{Colors.RED}[!] Could not build rescue bundle. Exiting.{Colors.END}\n")
        return 1

    print(f"\n{Colors.GREEN}[✓] Bundle ready:{Colors.END}")
    print(f"    Type: {info.get('type', 'unknown')}")
    if 'sweep_value' in info:
        print(f"    Rescue amount: {w3.from_wei(info['sweep_value'], 'ether'):.6f} ETH")

    # Submit to relays
    print(f"\n{Colors.YELLOW}[2] Submitting to MEV relays...{Colors.END}")

    for attempt in range(MAX_BLOCKS):
        target_block = w3.eth.block_number + 1
        print(f"\n{Colors.CYAN}    Target block: {target_block}{Colors.END}")

        successful = submit_bundle_to_all_relays(bundle, target_block)

        if successful > 0:
            print(f"\n{Colors.GREEN}[✓] Bundle submitted to {successful} relay(s){Colors.END}")
        else:
            print(f"\n{Colors.YELLOW}[!] No relays accepted bundle{Colors.END}")

        # Wait for block
        print(f"\n{Colors.DIM}    Waiting for block {target_block}...{Colors.END}")

        while w3.eth.block_number < target_block:
            time.sleep(1)

        # Check if rescue succeeded
        new_victim_balance = w3.eth.get_balance(victim.address)

        if new_victim_balance == 0:
            print(f"\n{Colors.GREEN}{'═' * 60}")
            print(f"  ✓ RESCUE SUCCESSFUL")
            print(f"{'═' * 60}{Colors.END}")
            print(f"\n{Colors.WHITE}Funds extracted to: {safe_address}{Colors.END}\n")
            return 0
        else:
            print(f"{Colors.YELLOW}    Bundle not included. Retrying...{Colors.END}")

    # If we get here, rescue failed
    print(f"\n{Colors.RED}{'═' * 60}")
    print(f"  WARNING: RESCUE INCOMPLETE")
    print(f"{'═' * 60}{Colors.END}")
    print(f"\n{Colors.WHITE}Bundle was not included after {MAX_BLOCKS} blocks.")
    print(f"The snipers may have been faster, or the network is congested.")
    print(f"Try again or use a higher priority fee.{Colors.END}\n")

    return 1


if __name__ == "__main__":
    sys.exit(run_rescue())
