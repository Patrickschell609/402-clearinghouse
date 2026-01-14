"""
x402 Client - Autonomous RWA Settlement

Usage:
    from x402_rwa import X402Agent

    agent = X402Agent(rpc_url, private_key)
    tx_hash = agent.acquire_asset("http://clearinghouse.example/api/v1/trade", "TBILL-26", 100)
"""

import os
import time
import requests
from web3 import Web3
from eth_account import Account
from eth_abi import encode


class X402Prover:
    """
    Handles ZK Proof generation.
    In production, wraps SP1 binary or remote prover network.
    """
    def generate_proof(self, circuit_id: str, wallet_address: str) -> tuple:
        """
        Generate ZK compliance proof for the given circuit.

        Returns:
            tuple: (proof_bytes, public_values_bytes)
        """
        # REAL IMPLEMENTATION:
        # return sp1.prove(circuit_id, identity_inputs)

        # MOCK IMPLEMENTATION - replace with real SP1 prover
        time.sleep(0.5)  # Simulate compute time

        # Public values: (address, validUntil, jurisdiction)
        valid_until = int(time.time()) + 86400 * 30  # 30 days
        jurisdiction = bytes.fromhex("5553" + "00" * 30)  # "US" padded to bytes32

        public_values = encode(
            ['address', 'uint256', 'bytes32'],
            [wallet_address, valid_until, jurisdiction]
        )

        proof = bytes.fromhex("1234567890abcdef")

        return proof, public_values


class X402Wallet:
    """
    Handles on-chain settlement transactions.
    """
    def __init__(self, rpc_url: str, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = Account.from_key(private_key)
        self.chain_id = self.w3.eth.chain_id

    @property
    def address(self) -> str:
        return self.account.address

    def settle_trade(
        self,
        clearinghouse_addr: str,
        asset_addr: str,
        amount: int,
        proof: bytes,
        public_values: bytes,
        price_wei: int
    ) -> str:
        """
        Execute atomic settlement on the Clearinghouse contract.

        Args:
            clearinghouse_addr: Clearinghouse contract address
            asset_addr: RWA token address
            amount: Number of units to acquire
            proof: ZK compliance proof bytes
            public_values: ABI-encoded public values
            price_wei: Price in USDC atomic units (6 decimals)

        Returns:
            str: Transaction hash
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

        expiry = int(time.time()) + 300  # 5 minutes

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

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status != 1:
            raise Exception(f"Transaction failed: {self.w3.to_hex(tx_hash)}")

        return self.w3.to_hex(tx_hash)


class X402Agent:
    """
    High-level agent interface for acquiring tokenized RWAs.

    Example:
        agent = X402Agent("https://mainnet.base.org", os.getenv("PRIVATE_KEY"))
        tx = agent.acquire_asset("http://clearinghouse.io/api/v1/trade", "TBILL-26", 100)
    """

    # Default asset addresses (Base Mainnet)
    DEFAULT_ASSETS = {
        "TBILL-26": "0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A"
    }

    def __init__(self, rpc_url: str, private_key: str):
        """
        Initialize the x402 agent.

        Args:
            rpc_url: RPC endpoint URL (e.g., https://mainnet.base.org)
            private_key: Wallet private key (hex string with 0x prefix)
        """
        self.prover = X402Prover()
        self.wallet = X402Wallet(rpc_url, private_key)

    def acquire_asset(
        self,
        server_url: str,
        asset_id: str,
        amount: int,
        verbose: bool = True
    ) -> str:
        """
        Acquire tokenized RWA in a single function call.

        Handles the complete flow:
        1. HTTP 402 negotiation
        2. ZK compliance proof generation
        3. Atomic on-chain settlement

        Args:
            server_url: x402 server base URL
            asset_id: Asset ticker (e.g., "TBILL-26")
            amount: Number of units to acquire
            verbose: Print progress to stdout

        Returns:
            str: Transaction hash on success

        Raises:
            Exception: On negotiation or settlement failure
        """
        if verbose:
            print(f"\n[x402] Acquiring {amount} units of {asset_id}")

        # 1. GET 402 CHALLENGE
        url = f"{server_url}/buy/{asset_id}"
        response = requests.get(url, params={"amount": amount})

        if response.status_code != 402:
            raise Exception(f"Expected 402, got {response.status_code}")

        # 2. PARSE x402 HEADERS
        headers = response.headers
        quote_price = int(headers.get("x-402-price", 0))
        circuit_id = headers.get("x-402-compliance-circuit", "")
        clearinghouse = headers.get("x-402-payment-address", "")
        asset_addr = headers.get(
            "x-402-asset-address",
            self.DEFAULT_ASSETS.get(asset_id, "")
        )

        if not all([quote_price, circuit_id, clearinghouse, asset_addr]):
            raise Exception("Malformed x402 headers")

        if verbose:
            print(f"[x402] Price: {quote_price / 10**6:.2f} USDC")

        # 3. GENERATE ZK PROOF
        proof, public_values = self.prover.generate_proof(
            circuit_id,
            self.wallet.address
        )

        if verbose:
            print(f"[x402] Proof generated")

        # 4. EXECUTE SETTLEMENT
        tx_hash = self.wallet.settle_trade(
            clearinghouse,
            asset_addr,
            amount,
            proof,
            public_values,
            quote_price
        )

        if verbose:
            print(f"[x402] Settled: {tx_hash}")

        return tx_hash

    # Alias
    buy_asset = acquire_asset
