"""
x402 Client - Autonomous RWA Settlement

Usage:
    from x402_rwa import X402Agent

    agent = X402Agent(rpc_url, private_key)
    tx_hash = agent.acquire_asset("http://clearinghouse.example/api/v1/trade", "TBILL-26", 100)

With real ZK identity:
    agent = X402Agent(rpc_url, private_key, identity_secret="your_secret_key")
    tx_hash = agent.acquire_asset(...)
"""

import os
import sys
import time
import requests
from web3 import Web3
from eth_account import Account

from .prover import X402Prover


# ============ DRAMATIC TERMINAL OUTPUT ============

class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def dramatic_print(text, color=Colors.WHITE, delay=0.02):
    """Typewriter effect for dramatic output."""
    for char in text:
        sys.stdout.write(f"{color}{char}{Colors.END}")
        sys.stdout.flush()
        time.sleep(delay)
    print()


def banner(text):
    """Print a styled banner."""
    width = 56
    print(f"\n{Colors.CYAN}{'═' * width}")
    print(f"  {text.center(width - 4)}")
    print(f"{'═' * width}{Colors.END}\n")


def box(lines, color=Colors.GREEN, title=None):
    """Print text in a box."""
    width = 46
    print(f"\n{color}{Colors.BOLD}╔{'═' * width}╗")
    if title:
        print(f"║  {title.center(width - 4)}  ║")
        print(f"╠{'═' * width}╣")
    for line in lines:
        padded = line.ljust(width - 4)
        print(f"║  {padded}  ║")
    print(f"╚{'═' * width}╝{Colors.END}")


def progress_bar(label, duration=1.0, width=30):
    """Animated progress bar."""
    print(f"{Colors.BLUE}{label}{Colors.END}")
    for i in range(width + 1):
        pct = i / width
        filled = '█' * i
        empty = '░' * (width - i)
        sys.stdout.write(f"\r    [{Colors.CYAN}{filled}{Colors.DIM}{empty}{Colors.END}] {int(pct*100):3d}%")
        sys.stdout.flush()
        time.sleep(duration / width)
    print(f" {Colors.GREEN}✓{Colors.END}")


# ============ WALLET ============

class X402Wallet:
    """Handles on-chain settlement transactions."""

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
        price_wei: int,
        verbose: bool = True
    ) -> str:
        """Execute atomic settlement on the Clearinghouse contract."""

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

        expiry = int(time.time()) + 300

        if verbose:
            print(f"{Colors.YELLOW}    → Building transaction...{Colors.END}")
            time.sleep(0.3)

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

        if verbose:
            print(f"{Colors.YELLOW}    → Signing with agent key...{Colors.END}")
            time.sleep(0.2)

        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.key)

        if verbose:
            print(f"{Colors.YELLOW}    → Broadcasting to Base Mainnet...{Colors.END}")
            time.sleep(0.3)

        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        if verbose:
            print(f"{Colors.YELLOW}    → Waiting for confirmation...{Colors.END}")

        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

        if receipt.status != 1:
            raise Exception(f"Transaction failed: {self.w3.to_hex(tx_hash)}")

        return self.w3.to_hex(tx_hash)


# ============ AGENT ============

class X402Agent:
    """
    High-level agent interface for acquiring tokenized RWAs.

    Example:
        agent = X402Agent("https://mainnet.base.org", os.getenv("PRIVATE_KEY"))
        tx = agent.acquire_asset("http://localhost:8080/api/v1/trade", "TBILL-26", 100)
    """

    DEFAULT_ASSETS = {
        "TBILL-26": "0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A",
        "cbBTC": "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf",
        "cbXRP": "0xcb585250f852C6c6bf90434AB21A00f02833a4af",
    }

    def __init__(
        self,
        rpc_url: str,
        private_key: str,
        identity_secret: str = "hello",
        prover_mode: str = "auto"
    ):
        self.prover = X402Prover(mode=prover_mode)
        self.wallet = X402Wallet(rpc_url, private_key)
        self.identity_secret = identity_secret

    def acquire_asset(
        self,
        server_url: str,
        asset_id: str,
        amount: int,
        verbose: bool = True
    ) -> str:
        """
        Acquire tokenized RWA in a single function call.

        Handles the complete x402 flow:
        1. HTTP 402 negotiation
        2. ZK compliance proof generation
        3. Atomic on-chain settlement
        """

        if verbose:
            banner("x402 CLEARINGHOUSE — AGENT ACQUISITION")

            print(f"{Colors.WHITE}[*] Target: {Colors.CYAN}{asset_id}{Colors.END}")
            print(f"{Colors.WHITE}[*] Amount: {Colors.CYAN}{amount} units{Colors.END}")
            print(f"{Colors.WHITE}[*] Agent:  {Colors.CYAN}{self.wallet.address[:22]}...{Colors.END}")
            print(f"{Colors.WHITE}[*] Chain:  {Colors.CYAN}Base Mainnet (8453){Colors.END}")
            time.sleep(0.5)

        # ═══════════════════════════════════════════════════════
        # STEP 1: INITIATE PURCHASE → EXPECT 402
        # ═══════════════════════════════════════════════════════

        if verbose:
            print(f"\n{Colors.YELLOW}[1] INITIATING PURCHASE REQUEST...{Colors.END}")
            time.sleep(0.3)
            print(f"{Colors.DIM}    GET {server_url}/buy/{asset_id}?amount={amount}{Colors.END}")
            time.sleep(0.5)

        url = f"{server_url}/buy/{asset_id}"
        response = requests.get(url, params={"amount": amount})

        if response.status_code != 402:
            raise Exception(f"Expected 402, got {response.status_code}")

        if verbose:
            box([
                "HTTP 402 — PAYMENT REQUIRED",
                "",
                "ZK compliance proof needed",
                "Submit proof + payment to settle"
            ], color=Colors.RED, title="CHALLENGE RECEIVED")
            time.sleep(0.8)

        # ═══════════════════════════════════════════════════════
        # STEP 2: PARSE x402 HEADERS
        # ═══════════════════════════════════════════════════════

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
            print(f"\n{Colors.WHITE}[*] x402 Headers Received:{Colors.END}")
            print(f"{Colors.DIM}    Price:       {Colors.WHITE}${quote_price / 1_000_000:.2f} USDC{Colors.END}")
            print(f"{Colors.DIM}    Circuit:     {Colors.WHITE}{circuit_id[:20]}...{Colors.END}")
            print(f"{Colors.DIM}    Clearinghouse: {Colors.WHITE}{clearinghouse[:20]}...{Colors.END}")
            print(f"{Colors.DIM}    Asset:       {Colors.WHITE}{asset_addr[:20]}...{Colors.END}")
            time.sleep(0.5)

        # ═══════════════════════════════════════════════════════
        # STEP 3: GENERATE ZK PROOF
        # ═══════════════════════════════════════════════════════

        if verbose:
            print(f"\n{Colors.CYAN}[2] GENERATING ZERO-KNOWLEDGE PROOF...{Colors.END}")
            time.sleep(0.3)

            stages = [
                ("Loading SP1 circuit", 0.3),
                ("Injecting identity commitment", 0.25),
                ("Computing Merkle witness", 0.35),
                ("Generating STARK proof", 0.5),
                ("Compressing proof bytes", 0.2),
            ]

            for stage, delay in stages:
                print(f"{Colors.BLUE}    → {stage}...{Colors.END}")
                time.sleep(delay)

        proof, public_values = self.prover.generate_proof(
            self.wallet.address,
            self.identity_secret
        )

        if verbose:
            print(f"\n{Colors.GREEN}[✓] ZK PROOF GENERATED{Colors.END}")
            print(f"{Colors.DIM}    Proof size: {len(proof)} bytes")
            print(f"    Public values: {len(public_values)} bytes{Colors.END}")
            time.sleep(0.5)

        # ═══════════════════════════════════════════════════════
        # STEP 4: EXECUTE ATOMIC SETTLEMENT
        # ═══════════════════════════════════════════════════════

        if verbose:
            print(f"\n{Colors.CYAN}[3] EXECUTING ATOMIC SETTLEMENT...{Colors.END}")
            time.sleep(0.3)

        tx_hash = self.wallet.settle_trade(
            clearinghouse,
            asset_addr,
            amount,
            proof,
            public_values,
            quote_price,
            verbose=verbose
        )

        # ═══════════════════════════════════════════════════════
        # SUCCESS
        # ═══════════════════════════════════════════════════════

        if verbose:
            fee = (quote_price * 5) // 10000  # 5 bps

            box([
                "SETTLEMENT SUCCESSFUL",
                "",
                f"Asset:  {amount} {asset_id}",
                f"Cost:   ${quote_price / 1_000_000:.2f} USDC",
                f"Fee:    ${fee / 1_000_000:.4f} (5 bps)",
                "",
                f"TX: {tx_hash[:24]}...",
            ], color=Colors.GREEN, title="CONFIRMED")

            print(f"\n{Colors.WHITE}{'─' * 56}")
            print(f"{Colors.CYAN}BASESCAN:{Colors.END} https://basescan.org/tx/{tx_hash}")
            print(f"{Colors.WHITE}{'─' * 56}{Colors.END}\n")

        return tx_hash

    # Alias
    buy_asset = acquire_asset


# ============ DEMO MODE ============

def demo():
    """Run a demonstration of the x402 flow (dry run)."""
    banner("x402 CLEARINGHOUSE — DEMO MODE")

    print(f"{Colors.WHITE}This demo simulates the x402 acquisition flow.")
    print(f"No real transactions will be executed.{Colors.END}\n")

    time.sleep(1)

    # Simulated flow
    print(f"\n{Colors.YELLOW}[1] INITIATING PURCHASE REQUEST...{Colors.END}")
    time.sleep(0.5)
    print(f"{Colors.DIM}    GET http://localhost:8080/api/v1/trade/buy/TBILL-26?amount=100{Colors.END}")
    time.sleep(0.8)

    box([
        "HTTP 402 — PAYMENT REQUIRED",
        "",
        "ZK compliance proof needed",
        "Submit proof + payment to settle"
    ], color=Colors.RED, title="CHALLENGE RECEIVED")

    time.sleep(1)

    print(f"\n{Colors.CYAN}[2] GENERATING ZERO-KNOWLEDGE PROOF...{Colors.END}")
    stages = [
        ("Loading SP1 circuit", 0.4),
        ("Injecting identity commitment", 0.3),
        ("Computing Merkle witness", 0.5),
        ("Generating STARK proof", 0.7),
        ("Compressing proof bytes", 0.3),
    ]
    for stage, delay in stages:
        print(f"{Colors.BLUE}    → {stage}...{Colors.END}")
        time.sleep(delay)

    print(f"\n{Colors.GREEN}[✓] ZK PROOF GENERATED — 1,247 bytes{Colors.END}")
    time.sleep(0.5)

    print(f"\n{Colors.CYAN}[3] EXECUTING ATOMIC SETTLEMENT...{Colors.END}")
    print(f"{Colors.YELLOW}    → Building transaction...{Colors.END}")
    time.sleep(0.4)
    print(f"{Colors.YELLOW}    → Signing with agent key...{Colors.END}")
    time.sleep(0.3)
    print(f"{Colors.YELLOW}    → Broadcasting to Base Mainnet...{Colors.END}")
    time.sleep(0.6)
    print(f"{Colors.YELLOW}    → Waiting for confirmation...{Colors.END}")
    time.sleep(1)

    tx_hash = "0x9f4a49f45de208588284fa6b4614f56c7ca95e5cd9a413d7b307b464a45e86be"

    box([
        "SETTLEMENT SUCCESSFUL",
        "",
        "Asset:  100 TBILL-26",
        "Cost:   $98.05 USDC",
        "Fee:    $0.0490 (5 bps)",
        "",
        f"TX: {tx_hash[:24]}...",
    ], color=Colors.GREEN, title="CONFIRMED")

    print(f"\n{Colors.WHITE}{'─' * 56}")
    print(f"{Colors.CYAN}BASESCAN:{Colors.END} https://basescan.org/tx/{tx_hash}")
    print(f"{Colors.WHITE}{'─' * 56}{Colors.END}\n")


if __name__ == "__main__":
    demo()
