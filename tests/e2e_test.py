#!/usr/bin/env python3
"""
E2E Integration Test: x402 Clearinghouse Flow

This script demonstrates the complete agent-to-clearinghouse flow:
1. Agent discovers available assets
2. Agent receives 402 challenge with terms
3. Agent generates compliance proof (mocked)
4. Agent executes atomic settlement
5. Agent receives T-Bill tokens

Requirements:
    pip install requests web3 eth-account

Usage:
    # Start server first: cd server && cargo run
    python tests/e2e_test.py
    
    # With custom server URL
    python tests/e2e_test.py --server http://localhost:8080
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Optional, Tuple

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

# Optional web3 for real blockchain interaction
try:
    from eth_account import Account
    from eth_account.messages import encode_defunct
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    print("NOTE: eth-account not installed. Using mock signatures.")


@dataclass
class X402Terms:
    """Parsed x402 challenge from server"""
    asset_id: str
    price: int
    currency: str
    compliance_circuit: str
    payment_address: str
    expiry: int
    quote_id: str
    chain_id: int


class MockProver:
    """
    Mock SP1 prover for testing.
    In production, this would use the actual SP1 SDK.
    """
    
    @staticmethod
    def generate_compliance_proof(
        agent_address: str,
        circuit_id: str,
        valid_until: int
    ) -> Tuple[bytes, bytes]:
        """
        Generate a mock compliance proof.
        
        Returns:
            (proof_bytes, public_values_bytes)
        """
        import hashlib
        
        # Mock proof generation (in production: SP1 prover)
        proof_data = hashlib.sha256(
            f"{agent_address}{circuit_id}{valid_until}".encode()
        ).digest()
        
        # Public values: ABI-encoded (address, uint256, bytes32)
        # address: 32 bytes (12 padding + 20 address)
        # valid_until: 32 bytes
        # jurisdiction_hash: 32 bytes
        
        address_bytes = bytes.fromhex(agent_address[2:] if agent_address.startswith('0x') else agent_address)
        public_values = (
            bytes(12) + address_bytes +  # address padded to 32 bytes
            valid_until.to_bytes(32, 'big') +  # valid_until
            hashlib.sha256(b"US_JURISDICTION").digest()  # jurisdiction hash
        )
        
        return proof_data, public_values


class AutonomousAgent:
    """
    Autonomous trading agent that interacts with the 402 Clearinghouse.
    
    This represents an AI agent or automated system that needs to
    acquire RWA assets programmatically.
    """
    
    def __init__(self, server_url: str, wallet_address: Optional[str] = None, private_key: Optional[str] = None):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Autonomous-Agent/1.0 (x402-RWA)',
            'Accept': 'application/json'
        })
        
        # Wallet setup
        if wallet_address:
            self.wallet_address = wallet_address
        elif private_key and WEB3_AVAILABLE:
            account = Account.from_key(private_key)
            self.wallet_address = account.address
            self.private_key = private_key
        else:
            # Demo wallet
            self.wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f1Ab23"
            self.private_key = None
        
        self.prover = MockProver()
    
    def health_check(self) -> dict:
        """Check server health and get chain info"""
        resp = self.session.get(f"{self.server_url}/health")
        resp.raise_for_status()
        return resp.json()
    
    def list_assets(self) -> list:
        """Discover available RWA assets"""
        resp = self.session.get(f"{self.server_url}/api/v1/assets")
        resp.raise_for_status()
        return resp.json()
    
    def get_quote(self, asset_id: str, amount: int) -> dict:
        """Get a price quote for an asset"""
        resp = self.session.get(
            f"{self.server_url}/api/v1/trade/quote/{asset_id}",
            params={'amount': amount}
        )
        resp.raise_for_status()
        return resp.json()
    
    def request_402_challenge(self, asset_id: str, amount: int) -> X402Terms:
        """
        Request to buy an asset - expects 402 Payment Required response.
        
        This is the key x402 protocol interaction.
        """
        resp = self.session.get(
            f"{self.server_url}/api/v1/trade/buy/{asset_id}",
            params={'amount': amount}
        )
        
        if resp.status_code != 402:
            raise Exception(f"Expected 402 Payment Required, got {resp.status_code}")
        
        # Parse x402 headers
        headers = resp.headers
        
        return X402Terms(
            asset_id=headers.get('X-402-Asset-ID', ''),
            price=int(headers.get('X-402-Price', 0)),
            currency=headers.get('X-402-Currency', 'USDC'),
            compliance_circuit=headers.get('X-402-Compliance-Circuit', ''),
            payment_address=headers.get('X-402-Payment-Address', ''),
            expiry=int(headers.get('X-402-Expiry', 0)),
            quote_id=headers.get('X-402-Quote-ID', ''),
            chain_id=int(headers.get('X-402-Chain-ID', 84532))
        )
    
    def evaluate_terms(self, terms: X402Terms, amount: int) -> bool:
        """
        Risk assessment: Should the agent accept these terms?
        
        This is where an AI agent would apply its decision logic.
        """
        # Price sanity check (T-Bills trade near par)
        price_per_unit = terms.price / amount if amount > 0 else 0
        price_usd = price_per_unit / 1_000_000  # USDC has 6 decimals
        
        if price_usd < 0.90 or price_usd > 1.10:
            print(f"  [!] Price {price_usd:.4f} outside acceptable range")
            return False
        
        # Expiry check
        if terms.expiry < time.time():
            print(f"  [!] Quote already expired")
            return False
        
        # Must have compliance circuit
        if not terms.compliance_circuit:
            print(f"  [!] No compliance circuit specified")
            return False
        
        return True
    
    def execute_settlement(self, asset_id: str, amount: int, terms: X402Terms) -> dict:
        """
        Execute the atomic settlement.
        
        This generates the ZK proof and submits the settlement request.
        """
        # Generate compliance proof
        valid_until = int(time.time()) + (30 * 24 * 60 * 60)  # 30 days
        proof, public_values = self.prover.generate_compliance_proof(
            self.wallet_address,
            terms.compliance_circuit,
            valid_until
        )
        
        # Submit settlement
        payload = {
            'asset': asset_id,
            'amount': amount,
            'quote_id': terms.quote_id,
            'compliance_proof': '0x' + proof.hex(),
            'public_values': '0x' + public_values.hex()
        }
        
        resp = self.session.post(
            f"{self.server_url}/api/v1/trade/buy/{asset_id}",
            json=payload
        )
        
        if not resp.ok:
            raise Exception(f"Settlement failed: {resp.status_code} - {resp.text}")
        
        return resp.json()
    
    def buy_asset(self, asset_id: str, amount: int, dry_run: bool = False) -> Optional[dict]:
        """
        Complete x402 purchase flow.
        
        This is the main entry point for autonomous asset acquisition.
        """
        print(f"\n{'='*60}")
        print(f"  x402 CLEARINGHOUSE - AUTONOMOUS PURCHASE FLOW")
        print(f"{'='*60}")
        print(f"\n  Agent: {self.wallet_address}")
        print(f"  Target: {amount} units of {asset_id}")
        
        # Step 1: Request 402 challenge
        print(f"\n[1] Requesting 402 challenge...")
        terms = self.request_402_challenge(asset_id, amount)
        
        print(f"  ✓ Received 402 Payment Required")
        print(f"    Asset ID:     {terms.asset_id}")
        print(f"    Price:        ${terms.price / 1_000_000:.4f} USDC")
        print(f"    Circuit:      {terms.compliance_circuit[:20]}...")
        print(f"    Pay To:       {terms.payment_address}")
        print(f"    Expiry:       {terms.expiry}")
        print(f"    Quote ID:     {terms.quote_id}")
        
        # Step 2: Evaluate terms
        print(f"\n[2] Evaluating terms...")
        if not self.evaluate_terms(terms, amount):
            print(f"  ✗ Terms rejected by risk model")
            return None
        print(f"  ✓ Terms accepted")
        
        # Step 3: Generate compliance proof
        print(f"\n[3] Generating ZK compliance proof...")
        if dry_run:
            print(f"  [DRY RUN] Skipping proof generation")
        else:
            print(f"  ✓ Proof generated (mock)")
        
        # Step 4: Execute settlement
        if dry_run:
            print(f"\n[4] DRY RUN - Would execute settlement")
            return {
                'status': 'dry_run',
                'terms': terms.__dict__
            }
        
        print(f"\n[4] Executing atomic settlement...")
        result = self.execute_settlement(asset_id, amount, terms)
        
        print(f"\n{'='*60}")
        print(f"  ✓ SETTLEMENT COMPLETE")
        print(f"{'='*60}")
        print(f"    Status:     {result.get('status')}")
        print(f"    TX Hash:    {result.get('tx_hash', 'N/A')}")
        print(f"    Asset:      {result.get('asset_delivered')}")
        print(f"    Amount:     {result.get('amount')}")
        
        return result


def run_e2e_test(server_url: str, dry_run: bool = True):
    """Run the complete E2E test"""
    
    print(f"\n{'#'*60}")
    print(f"  402 CLEARINGHOUSE - E2E INTEGRATION TEST")
    print(f"{'#'*60}")
    print(f"\n  Server: {server_url}")
    print(f"  Mode:   {'DRY RUN' if dry_run else 'LIVE'}")
    
    # Initialize agent
    agent = AutonomousAgent(server_url)
    
    # Test 1: Health check
    print(f"\n[TEST 1] Health Check")
    print("-" * 40)
    try:
        health = agent.health_check()
        print(f"  Status: {health.get('status')}")
        print(f"  Chain:  {health.get('chain_id')}")
        print(f"  Block:  {health.get('block_number')}")
        print(f"  ✓ PASSED")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    # Test 2: List assets
    print(f"\n[TEST 2] Asset Discovery")
    print("-" * 40)
    try:
        assets = agent.list_assets()
        print(f"  Found {len(assets)} assets:")
        for asset in assets:
            print(f"    - {asset.get('id')}: ${asset.get('price_per_unit', 0)/1e6:.4f}")
        print(f"  ✓ PASSED")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    if not assets:
        print("  [SKIP] No assets available for purchase test")
        return True
    
    # Test 3: Get quote
    test_asset = assets[0]['id']
    test_amount = 100
    
    print(f"\n[TEST 3] Quote Request")
    print("-" * 40)
    try:
        quote = agent.get_quote(test_asset, test_amount)
        print(f"  Asset:  {quote.get('asset_id')}")
        print(f"  Amount: {quote.get('amount')}")
        print(f"  Total:  ${quote.get('total_price', 0)/1e6:.4f}")
        print(f"  Fee:    ${quote.get('fee', 0)/1e6:.4f}")
        print(f"  ✓ PASSED")
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        return False
    
    # Test 4: Full purchase flow
    print(f"\n[TEST 4] Complete Purchase Flow")
    print("-" * 40)
    try:
        result = agent.buy_asset(test_asset, test_amount, dry_run=dry_run)
        if result:
            print(f"\n  ✓ PASSED")
        else:
            print(f"\n  ✗ FAILED: Terms rejected")
            return False
    except Exception as e:
        print(f"\n  ✗ FAILED: {e}")
        return False
    
    print(f"\n{'='*60}")
    print(f"  ALL TESTS PASSED")
    print(f"{'='*60}\n")
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="E2E test for 402 Clearinghouse"
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8080",
        help="Server URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run in live mode (execute real transactions)"
    )
    
    args = parser.parse_args()
    
    success = run_e2e_test(args.server, dry_run=not args.live)
    sys.exit(0 if success else 1)
