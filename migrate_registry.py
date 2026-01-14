#!/usr/bin/env python3
"""
x402 Registry Migration Script

Migrates from inline ZK verification to the AgentRegistry identity layer.
Run this after deploying AgentRegistry.sol with Foundry.

Usage:
    # First deploy the contract:
    forge create src/AgentRegistry.sol:AgentRegistry \
        --rpc-url https://mainnet.base.org \
        --private-key $PRIVATE_KEY

    # Then run this script:
    python migrate_registry.py
"""

import os
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL", "https://mainnet.base.org")

# Your existing Merkle root
MERKLE_ROOT = "0x263f639b87bbf5e98a3099282ffed1eca3bd946818592b0bda8fe546426afc2b"

# Existing clearinghouse to whitelist
CLEARINGHOUSE = "0xb315C8F827e3834bB931986F177cb1fb6D20415D"

REGISTRY_ABI = [
    {"inputs": [{"name": "_newRoot", "type": "bytes32"}], "name": "updateRoot", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "protocol", "type": "address"}], "name": "whitelistProtocol", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [], "name": "authorizedRoot", "outputs": [{"name": "", "type": "bytes32"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "totalAgents", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]


def migrate():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    account = Account.from_key(PRIVATE_KEY)

    print("=" * 60)
    print("  x402 REGISTRY MIGRATION")
    print("=" * 60)
    print(f"\nAdmin: {account.address}")
    print(f"Chain: {w3.eth.chain_id}")

    # Get registry address
    print("\n[1] Enter the AgentRegistry address from forge create:")
    registry_addr = input("    Registry Address > ").strip()

    if not w3.is_address(registry_addr):
        print("[!] Invalid address")
        return

    registry = w3.eth.contract(address=registry_addr, abi=REGISTRY_ABI)

    # Check current root
    current_root = registry.functions.authorizedRoot().call()
    print(f"\n[*] Current root: {w3.to_hex(current_root)}")

    if current_root != bytes(32):
        print("[!] Root already set. Skipping root update.")
    else:
        print(f"\n[2] Setting Merkle root: {MERKLE_ROOT}")

        tx = registry.functions.updateRoot(MERKLE_ROOT).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 100000,
            'maxFeePerGas': w3.eth.gas_price * 2,
            'maxPriorityFeePerGas': w3.to_wei(0.001, 'gwei'),
        })

        signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"    TX: {w3.to_hex(tx_hash)}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt.status == 1:
            print(f"    Confirmed in block {receipt.blockNumber}")
        else:
            print("    FAILED!")
            return

    # Whitelist clearinghouse
    print(f"\n[3] Whitelisting Clearinghouse: {CLEARINGHOUSE}")

    tx = registry.functions.whitelistProtocol(CLEARINGHOUSE).build_transaction({
        'from': account.address,
        'nonce': w3.eth.get_transaction_count(account.address),
        'gas': 100000,
        'maxFeePerGas': w3.eth.gas_price * 2,
        'maxPriorityFeePerGas': w3.to_wei(0.001, 'gwei'),
    })

    signed = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"    TX: {w3.to_hex(tx_hash)}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt.status == 1:
        print(f"    Confirmed in block {receipt.blockNumber}")
    else:
        print("    FAILED!")
        return

    # Summary
    print("\n" + "=" * 60)
    print("  MIGRATION COMPLETE")
    print("=" * 60)
    print(f"\n  AgentRegistry: {registry_addr}")
    print(f"  Merkle Root:   {MERKLE_ROOT}")
    print(f"  Clearinghouse: {CLEARINGHOUSE} (whitelisted)")
    print("\n  Next steps:")
    print("  1. Verify registry on BaseScan")
    print("  2. Agents can self-register with register(proof, leaf)")
    print("  3. Other protocols can call checkEligibility(agent)")
    print("=" * 60)


if __name__ == "__main__":
    migrate()
