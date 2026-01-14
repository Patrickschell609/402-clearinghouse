#!/usr/bin/env python3
"""
x402 Merkle Tree Generator - Full Implementation

Generates a Merkle tree of authorized agent identities.
Outputs ROOT and proof data for the ZK circuit.

Usage:
    python merkle_tree.py

    # Or import:
    from merkle_tree import MerkleTree
    tree = MerkleTree(["agent_001", "agent_002", ...])
    proof = tree.get_proof("agent_002")
"""

import hashlib
import json


def hash_data(data):
    """Hash a secret to get leaf node."""
    return hashlib.sha256(data.encode()).hexdigest()


def hash_pair(a, b):
    """Hash two nodes together (left || right).
    Must match Rust circuit's hashing exactly.
    """
    combined = bytes.fromhex(a) + bytes.fromhex(b)
    return hashlib.sha256(combined).hexdigest()


class MerkleTree:
    """
    Merkle tree for agent registry.

    Usage:
        tree = MerkleTree(["secret1", "secret2", ...])
        root = tree.get_root()
        proof = tree.get_proof("secret1")
    """

    def __init__(self, secrets):
        self.secrets = secrets
        self.leaves = [hash_data(s) for s in secrets]
        self.levels = [self.leaves]
        self.build()

    def build(self):
        current_level = self.leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    left, right = current_level[i], current_level[i+1]
                    next_level.append(hash_pair(left, right))
                else:
                    # Odd node - carry up
                    next_level.append(current_level[i])
            self.levels.append(next_level)
            current_level = next_level

    def get_root(self):
        """Get the Merkle root hash."""
        return self.levels[-1][0]

    def get_proof(self, secret):
        """
        Generate Merkle proof for a secret.

        Returns:
            dict with:
                - root: The Merkle root
                - path: List of sibling hashes along the path
                - bits: List of bools - True if we're the right node at each level
        """
        target_hash = hash_data(secret)
        try:
            index = self.levels[0].index(target_hash)
        except ValueError:
            return None

        proof_path = []
        index_bits = []

        for level in self.levels[:-1]:  # Don't include root level
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

    def verify_proof(self, secret, proof):
        """Verify a Merkle proof."""
        current_hash = hash_data(secret)

        for sibling, is_right in zip(proof['path'], proof['bits']):
            if is_right:
                # We're on the right, sibling is on the left
                current_hash = hash_pair(sibling, current_hash)
            else:
                # We're on the left, sibling is on the right
                current_hash = hash_pair(current_hash, sibling)

        return current_hash == proof['root']


# Default registry for x402
DEFAULT_REGISTRY = [
    "hello",                    # Test secret
    "agent_007_secret",
    "agent_008_secret",
    "agent_009_secret",
    "ghost_clearance_alpha",
]


if __name__ == "__main__":
    print("=" * 60)
    print("  x402 MERKLE TREE - Agent Registry")
    print("=" * 60)
    print()

    # Build tree
    tree = MerkleTree(DEFAULT_REGISTRY)
    root = tree.get_root()

    print(f"Agents in tree: {len(DEFAULT_REGISTRY)}")
    print()

    print("Leaf hashes:")
    for i, (secret, leaf) in enumerate(zip(DEFAULT_REGISTRY, tree.leaves)):
        print(f"  [{i}] {secret[:20]:20} → {leaf[:16]}...")
    print()

    print(f"MERKLE ROOT: {root}")
    print()
    print("For Rust circuit:")
    print(f'const MERKLE_ROOT: &str = "{root}";')
    print()

    # Generate and verify proof for "hello"
    print("-" * 60)
    test_secret = "hello"
    proof = tree.get_proof(test_secret)

    print(f"Proof for '{test_secret}':")
    print(f"  Root: {proof['root'][:20]}...")
    print(f"  Path length: {len(proof['path'])} siblings")
    print()

    for i, (sibling, is_right) in enumerate(zip(proof['path'], proof['bits'])):
        position = "RIGHT (we're right, sibling left)" if is_right else "LEFT (we're left, sibling right)"
        print(f"  [{i}] {sibling[:16]}... | {position}")
    print()

    # Verify
    valid = tree.verify_proof(test_secret, proof)
    print(f"Verification: {'✓ VALID' if valid else '✗ INVALID'}")
    print()

    # Export for Rust/SP1
    print("-" * 60)
    print("JSON for SP1 prover:")
    print(json.dumps({
        "path": proof['path'],
        "bits": proof['bits']
    }, indent=2))
    print()

    # Test all secrets
    print("-" * 60)
    print("Verifying all agents:")
    for secret in DEFAULT_REGISTRY:
        p = tree.get_proof(secret)
        v = tree.verify_proof(secret, p)
        status = "✓" if v else "✗"
        print(f"  {status} {secret}")
