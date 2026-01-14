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


class MerkleTree:
    """Simple Merkle tree for agent registry."""

    def __init__(self, secrets: list):
        import hashlib
        self.secrets = secrets
        self.leaves = [hashlib.sha256(s.encode()).hexdigest() for s in secrets]
        self.tree = [self.leaves]
        self._build()

    def _hash_pair(self, a: str, b: str) -> str:
        import hashlib
        combined = bytes.fromhex(a) + bytes.fromhex(b)
        return hashlib.sha256(combined).hexdigest()

    def _build(self):
        current_level = self.leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    next_level.append(self._hash_pair(current_level[i], current_level[i+1]))
                else:
                    next_level.append(current_level[i])
            self.tree.append(next_level)
            current_level = next_level

    def get_root(self) -> str:
        return self.tree[-1][0]

    def get_proof(self, secret: str) -> dict:
        """
        Get Merkle proof for a secret.

        Returns:
            dict with:
                - root: The Merkle root
                - path: List of sibling hashes
                - bits: List of bools - True if we're the RIGHT node at each level
        """
        import hashlib
        target_hash = hashlib.sha256(secret.encode()).hexdigest()
        try:
            index = self.leaves.index(target_hash)
        except ValueError:
            return None

        proof_path = []
        index_bits = []

        for level in self.tree[:-1]:  # Don't include root
            is_right_node = (index % 2 == 1)
            sibling_index = index - 1 if is_right_node else index + 1

            if sibling_index < len(level):
                proof_path.append(level[sibling_index])
                index_bits.append(is_right_node)

            index //= 2

        return {
            "root": self.get_root(),
            "path": proof_path,
            "bits": index_bits
        }


# Default agent registry
DEFAULT_REGISTRY = [
    "hello",
    "agent_007_secret",
    "agent_008_secret",
    "agent_009_secret",
    "ghost_clearance_alpha",
]


class MockProver:
    """
    Mock prover for testing without SP1 installed.
    Generates deterministic test proofs with Merkle tree support.
    """
    def __init__(self, registry: list = None):
        self.tree = MerkleTree(registry or DEFAULT_REGISTRY)

    def generate_proof(self, wallet_address: str, secret_key: str = None) -> tuple:
        """Generate mock proof and public values."""
        time.sleep(0.5)  # Simulate compute

        # Get Merkle proof if secret is in registry
        merkle_data = None
        if secret_key:
            merkle_data = self.tree.get_proof(secret_key)
            if merkle_data is None:
                raise ValueError(f"Secret '{secret_key}' not in registry")

        # Public values: (address, validUntil, jurisdiction)
        valid_until = int(time.time()) + 86400 * 30
        jurisdiction = bytes.fromhex("5553" + "00" * 30)  # "US"

        public_values = encode(
            ['address', 'uint256', 'bytes32'],
            [wallet_address, valid_until, jurisdiction]
        )

        # Mock proof - in production this would be real SP1 proof bytes
        proof = bytes.fromhex("1234567890abcdef")
        return proof, public_values

    def get_merkle_data(self, secret_key: str) -> dict:
        """Get Merkle proof data for SP1 input."""
        return self.tree.get_proof(secret_key)


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
