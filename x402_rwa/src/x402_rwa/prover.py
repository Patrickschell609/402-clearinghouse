"""
x402 ZK Prover Module

Generates zero-knowledge proofs for agent identity verification.
Supports both mock (testing) and real (SP1) proving modes.
"""

import os
import time
import subprocess
import tempfile
from pathlib import Path
from eth_abi import encode


class MockProver:
    """
    Mock prover for testing without SP1 installed.
    Generates deterministic test proofs.
    """
    def generate_proof(self, wallet_address: str, secret_key: str = None) -> tuple:
        """Generate mock proof and public values."""
        time.sleep(0.5)  # Simulate compute

        # Public values: (address, validUntil, jurisdiction)
        valid_until = int(time.time()) + 86400 * 30
        jurisdiction = bytes.fromhex("5553" + "00" * 30)  # "US"

        public_values = encode(
            ['address', 'uint256', 'bytes32'],
            [wallet_address, valid_until, jurisdiction]
        )

        proof = bytes.fromhex("1234567890abcdef")
        return proof, public_values


class SP1Prover:
    """
    Real SP1 prover for production use.
    Generates cryptographic ZK proofs locally.
    """
    def __init__(self, circuit_path: str = None):
        """
        Initialize SP1 prover.

        Args:
            circuit_path: Path to compiled SP1 circuit directory.
                         Defaults to circuits/identity/script
        """
        if circuit_path is None:
            # Default to the identity circuit in the repo
            self.circuit_path = Path(__file__).parent.parent.parent.parent / "circuits" / "identity" / "script"
        else:
            self.circuit_path = Path(circuit_path)

    def generate_proof(self, wallet_address: str, secret_key: str) -> tuple:
        """
        Generate real ZK proof using SP1.

        Args:
            wallet_address: Agent's wallet address (for public values)
            secret_key: Secret identity key (private input, never revealed)

        Returns:
            tuple: (proof_bytes, public_values_bytes)
        """
        print(f"[*] SP1 PROVER: Generating ZK identity proof...")

        # Create temp file for proof output
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            proof_path = f.name

        try:
            # Run the SP1 prover script
            result = subprocess.run(
                [
                    "cargo", "run", "--release", "--",
                    "--secret", secret_key,
                    "--output", proof_path
                ],
                cwd=self.circuit_path,
                capture_output=True,
                text=True,
                timeout=300  # 5 min timeout for proof generation
            )

            if result.returncode != 0:
                raise Exception(f"SP1 prover failed: {result.stderr}")

            # Read the generated proof
            with open(proof_path, 'rb') as f:
                proof = f.read()

            print(f"[+] SP1 PROVER: Proof generated ({len(proof)} bytes)")

        finally:
            # Cleanup
            if os.path.exists(proof_path):
                os.remove(proof_path)

        # Generate public values
        valid_until = int(time.time()) + 86400 * 30
        jurisdiction = bytes.fromhex("5553" + "00" * 30)

        public_values = encode(
            ['address', 'uint256', 'bytes32'],
            [wallet_address, valid_until, jurisdiction]
        )

        return proof, public_values


class X402Prover:
    """
    Unified prover interface.
    Automatically uses SP1 if available, falls back to mock.
    """
    def __init__(self, mode: str = "auto", circuit_path: str = None):
        """
        Initialize prover.

        Args:
            mode: "auto" (detect), "mock" (testing), or "sp1" (production)
            circuit_path: Path to SP1 circuit (only for sp1 mode)
        """
        self.mode = mode
        self.circuit_path = circuit_path
        self._prover = None

    def _get_prover(self):
        if self._prover is not None:
            return self._prover

        if self.mode == "mock":
            self._prover = MockProver()
        elif self.mode == "sp1":
            self._prover = SP1Prover(self.circuit_path)
        else:  # auto
            # Check if SP1 is available
            try:
                result = subprocess.run(
                    ["cargo", "prove", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self._prover = SP1Prover(self.circuit_path)
                else:
                    self._prover = MockProver()
            except:
                self._prover = MockProver()

        return self._prover

    def generate_proof(self, wallet_address: str, secret_key: str = "hello") -> tuple:
        """
        Generate ZK proof.

        Args:
            wallet_address: Agent's wallet address
            secret_key: Secret for identity verification (default: "hello" for testing)

        Returns:
            tuple: (proof_bytes, public_values_bytes)
        """
        prover = self._get_prover()
        return prover.generate_proof(wallet_address, secret_key)
