import os
import requests
from web3 import Web3
from eth_account import Account
import json
import time
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
RPC_URL = "https://mainnet.base.org"
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# Contract addresses (Base Mainnet)
TBILL_ADDRESS = "0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A"

class X402Prover:
    """
    Handles the ZK Proof generation.
    In production, this wraps the SP1 binary or client.
    """
    def generate_proof(self, circuit_id: str, wallet_address: str) -> tuple:
        print(f"[*] PROVER: Spinning up SP1 for circuit {circuit_id[:10]}...")
        # REAL IMPLEMENTATION:
        # return sp1.prove(circuit_id, identity_inputs)

        # MOCK IMPLEMENTATION
        time.sleep(1)  # Simulate compute time

        # Generate public values: (address, validUntil, jurisdiction)
        valid_until = int(time.time()) + 86400 * 30  # 30 days
        jurisdiction = bytes.fromhex("5553" + "00" * 30)  # "US" padded to bytes32

        # ABI encode: (address, uint256, bytes32)
        from eth_abi import encode
        public_values = encode(
            ['address', 'uint256', 'bytes32'],
            [wallet_address, valid_until, jurisdiction]
        )

        proof = bytes.fromhex("1234567890abcdef")

        return proof, public_values

class X402Wallet:
    """
    Handles the On-Chain Settlement.
    """
    def __init__(self, rpc_url, private_key):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = Account.from_key(private_key)
        self.chain_id = self.w3.eth.chain_id
        print(f"[*] WALLET: Connected to Chain ID {self.chain_id} as {self.account.address}")

    def settle_trade(self, clearinghouse_addr, asset_addr, amount, proof, public_values, price_wei):
        """
        Executes the atomic swap on the Clearinghouse contract.
        Matches: settle(address asset, uint256 amount, uint256 expiry, bytes proof, bytes publicValues)
        """
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

        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(clearinghouse_addr),
            abi=abi
        )

        print(f"[*] WALLET: Constructing Atomic Swap TX...")
        print(f"    - Pay: {price_wei / 10**6} USDC")
        print(f"    - Get: {amount} units of asset")

        # Expiry 5 minutes from now
        expiry = int(time.time()) + 300

        # Build Transaction
        tx = contract.functions.settle(
            Web3.to_checksum_address(asset_addr),
            int(amount),
            expiry,
            proof,
            public_values
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 200000,
            'maxFeePerGas': self.w3.eth.gas_price * 2,
            'maxPriorityFeePerGas': self.w3.to_wei(0.001, 'gwei'),
        })

        # Sign & Send
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        print(f"[*] WALLET: Broadcast! Hash: {self.w3.to_hex(tx_hash)}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        if receipt.status == 1:
            print(f"[*] WALLET: Confirmed in block {receipt.blockNumber}")
        else:
            print(f"[X] WALLET: Transaction failed!")

        return self.w3.to_hex(tx_hash)

class X402Agent:
    """
    The High-Level Agent Interface.
    One function call to acquire tokenized RWAs.
    """
    def __init__(self, rpc_url, private_key):
        self.prover = X402Prover()
        self.wallet = X402Wallet(rpc_url, private_key)

    def acquire_asset(self, server_url: str, asset_id: str, amount: int):
        """
        The money shot: one function call to acquire tokenized assets.
        Handles: 402 negotiation → ZK proof → atomic settlement
        """
        print(f"\n{'='*60}")
        print(f"  x402 AGENT: ACQUIRING {amount} units of {asset_id}")
        print(f"{'='*60}")

        # 1. DISCOVERY - Hit endpoint to get 402 challenge
        url = f"{server_url}/buy/{asset_id}"
        print(f"\n[1] NEGOTIATION: GET {url}?amount={amount}")

        try:
            response = requests.get(url, params={"amount": amount})
        except Exception as e:
            print(f"[X] Network Error: {e}")
            return None

        # 2. PARSE 402 CHALLENGE
        if response.status_code != 402:
            print(f"[?] Expected 402, got {response.status_code}")
            return None

        print("[*] Received 402 PAYMENT REQUIRED")
        headers = response.headers

        quote_price = int(headers.get("x-402-price", 0))
        circuit_id = headers.get("x-402-compliance-circuit", "")
        clearinghouse = headers.get("x-402-payment-address", "")
        asset_addr = headers.get("x-402-asset-address", TBILL_ADDRESS)

        print(f"    Price:        {quote_price / 10**6:.2f} USDC")
        print(f"    Circuit:      {circuit_id[:20]}...")
        print(f"    Clearinghouse: {clearinghouse}")
        print(f"    Asset:        {asset_addr}")

        # 3. GENERATE ZK COMPLIANCE PROOF
        print(f"\n[2] ZK PROOF GENERATION")
        proof, public_values = self.prover.generate_proof(
            circuit_id,
            self.wallet.account.address
        )
        print(f"    Proof:        {proof.hex()[:20]}...")
        print(f"    Public vals:  {len(public_values)} bytes")

        # 4. EXECUTE ATOMIC SETTLEMENT
        print(f"\n[3] ON-CHAIN SETTLEMENT")
        try:
            tx_hash = self.wallet.settle_trade(
                clearinghouse,
                asset_addr,
                amount,
                proof,
                public_values,
                quote_price
            )

            print(f"\n{'='*60}")
            print(f"  [$] SUCCESS: ASSET ACQUIRED")
            print(f"  TX: {tx_hash}")
            print(f"  View: https://basescan.org/tx/{tx_hash}")
            print(f"{'='*60}")
            return tx_hash

        except Exception as e:
            print(f"\n[X] SETTLEMENT FAILED: {e}")
            return None

    # Alias for backward compatibility
    buy_asset = acquire_asset

# --- USAGE EXAMPLE ---
if __name__ == "__main__":
    SERVER_URL = "http://localhost:8080/api/v1/trade"

    if not PRIVATE_KEY:
        print("[X] ERROR: Set PRIVATE_KEY in .env")
        exit(1)

    # Initialize agent with real credentials
    agent = X402Agent(RPC_URL, PRIVATE_KEY)

    # One line to acquire tokenized T-Bills
    agent.acquire_asset(SERVER_URL, "TBILL-26", 100)
