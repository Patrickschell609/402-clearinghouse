#!/usr/bin/env python3
"""
x402 Admin Console - God Mode for Your Clearinghouse

Commands:
    python admin_cli.py status              # View inventory and revenue
    python admin_cli.py restock --amount 1000   # Add T-Bills to inventory
    python admin_cli.py set-treasury 0x...  # Change treasury address
"""

import os
import sys
import argparse
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Load environment
load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL", "https://mainnet.base.org")

if not PRIVATE_KEY:
    print("[CRITICAL] No PRIVATE_KEY found in .env")
    sys.exit(1)

# Contract addresses (Base Mainnet - YOUR deployment)
CLEARINGHOUSE_ADDR = "0xb315C8F827e3834bB931986F177cb1fb6D20415D"
TBILL_ADDR = "0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A"
USDC_ADDR = "0x6020Ed65e0008242D9094D107D97dd17599dc21C"  # Your MockUSDC
ADMIN_WALLET = "0xc7554F1B16ad0b3Ce363d53364C9817743E32f90"

# ABIs
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "_to", "type": "address"}, {"name": "_amount", "type": "uint256"}], "name": "mint", "outputs": [], "type": "function"},
]

CLEARINGHOUSE_ABI = [
    {"inputs": [], "name": "treasury", "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "feeBps", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "newTreasury", "type": "address"}], "name": "setTreasury", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "agent", "type": "address"}], "name": "isAgentVerified", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
]


class AdminConsole:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.account = Account.from_key(PRIVATE_KEY)
        self.chain_id = self.w3.eth.chain_id
        print(f"\n[#] ADMIN SESSION: {self.account.address}")
        print(f"[#] Chain: {self.chain_id} (Base Mainnet)")

    def send_tx(self, contract, func_call):
        """Sign and send transaction."""
        tx_params = {
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 200000,
            'maxFeePerGas': self.w3.eth.gas_price * 2,
            'maxPriorityFeePerGas': self.w3.to_wei(0.001, 'gwei'),
        }
        tx = func_call.build_transaction(tx_params)
        signed = self.w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"    TX: {self.w3.to_hex(tx_hash)}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt.status == 1:
            print(f"    Confirmed in block {receipt.blockNumber}")
        else:
            print(f"    FAILED!")
        return self.w3.to_hex(tx_hash)

    def check_status(self):
        """View inventory, treasury, and balances."""
        tbill = self.w3.eth.contract(address=TBILL_ADDR, abi=ERC20_ABI)
        usdc = self.w3.eth.contract(address=USDC_ADDR, abi=ERC20_ABI)
        ch = self.w3.eth.contract(address=CLEARINGHOUSE_ADDR, abi=CLEARINGHOUSE_ABI)

        # Balances
        inventory = tbill.functions.balanceOf(CLEARINGHOUSE_ADDR).call()
        treasury_addr = ch.functions.treasury().call()
        treasury_balance = usdc.functions.balanceOf(treasury_addr).call()
        fee_bps = ch.functions.feeBps().call()
        admin_usdc = usdc.functions.balanceOf(ADMIN_WALLET).call()
        admin_tbill = tbill.functions.balanceOf(ADMIN_WALLET).call()
        agent_verified = ch.functions.isAgentVerified(ADMIN_WALLET).call()

        print("\n" + "=" * 50)
        print("  x402 CLEARINGHOUSE STATUS")
        print("=" * 50)
        print(f"\nClearinghouse: {CLEARINGHOUSE_ADDR}")
        print(f"Treasury:      {treasury_addr}")
        print(f"Fee:           {fee_bps} bps ({fee_bps/100:.2f}%)")
        print()
        print(f"INVENTORY (T-Bills in contract): {inventory:,} units")
        print(f"TREASURY BALANCE (fees):         ${treasury_balance / 1_000_000:,.2f} USDC")
        print()
        print(f"--- Admin Wallet ({ADMIN_WALLET[:10]}...) ---")
        print(f"  USDC:       ${admin_usdc / 1_000_000:,.2f}")
        print(f"  T-Bills:    {admin_tbill:,}")
        print(f"  Verified:   {'YES' if agent_verified else 'NO'}")
        print("=" * 50)

    def restock_inventory(self, amount):
        """Mint T-Bills to the clearinghouse."""
        print(f"\n[+] RESTOCKING {amount:,} T-BILLS to Clearinghouse...")
        tbill = self.w3.eth.contract(address=TBILL_ADDR, abi=ERC20_ABI)

        try:
            self.send_tx(tbill, tbill.functions.mint(CLEARINGHOUSE_ADDR, int(amount)))
            print(f"[+] Clearinghouse now has {amount:,} more T-Bills for sale")
        except Exception as e:
            print(f"[!] Mint failed: {e}")
            print("[!] Trying transfer from admin wallet...")
            self.send_tx(tbill, tbill.functions.transfer(CLEARINGHOUSE_ADDR, int(amount)))

    def set_treasury(self, new_treasury):
        """Change the treasury address (where fees go)."""
        print(f"\n[+] SETTING TREASURY to {new_treasury}...")
        ch = self.w3.eth.contract(address=CLEARINGHOUSE_ADDR, abi=CLEARINGHOUSE_ABI)
        self.send_tx(ch, ch.functions.setTreasury(new_treasury))
        print(f"[+] Treasury updated!")

    def mint_usdc(self, amount):
        """Mint USDC to admin wallet (for testing)."""
        print(f"\n[+] MINTING ${amount:,} USDC to admin wallet...")
        usdc = self.w3.eth.contract(address=USDC_ADDR, abi=ERC20_ABI)
        # Amount in 6 decimals
        self.send_tx(usdc, usdc.functions.mint(ADMIN_WALLET, int(amount * 1_000_000)))
        print(f"[+] Minted ${amount:,} USDC")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='x402 Admin Console')
    parser.add_argument('action', choices=['status', 'restock', 'set-treasury', 'mint-usdc'],
                        help='Action to perform')
    parser.add_argument('--amount', type=int, help='Amount for restock/mint', default=1000)
    parser.add_argument('--address', type=str, help='Address for set-treasury')

    args = parser.parse_args()
    admin = AdminConsole()

    if args.action == "status":
        admin.check_status()
    elif args.action == "restock":
        admin.restock_inventory(args.amount)
    elif args.action == "set-treasury":
        if not args.address:
            print("[!] --address required for set-treasury")
        else:
            admin.set_treasury(args.address)
    elif args.action == "mint-usdc":
        admin.mint_usdc(args.amount)
