#!/usr/bin/env python3
"""
x402 Merkle Tree Generator

Generates a Merkle tree of authorized agent identities.
Output the ROOT to paste into the ZK circuit.

Usage:
    python merkle_tree.py
"""

import hashlib
import json

def hash_data(data):
    """Hash a secret to get leaf node."""
    return hashlib.sha256(data.encode()).hexdigest()

def hash_pair(a, b):
    """Hash two nodes together (left + right)."""
    combined = bytes.fromhex(a) + bytes.fromhex(b)
    return hashlib.sha256(combined).hexdigest()

class MerkleTree:
    def __init__(self, secrets):
        self.secrets = secrets
        self.leaves = [hash_data(s) for s in secrets]
        self.tree = [self.leaves]
        self.build()

    def build(self):
        current_level = self.leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    left = current_level[i]
                    right = current_level[i+1]
                    combined = hash_pair(left, right)
                    next_level.append(combined)
                else:
                    # Odd one out, carry up
                    next_level.append(current_level[i])
            self.tree.append(next_level)
            current_level = next_level

    def get_root(self):
        return self.tree[-1][0]

    def get_proof(self, secret):
        """
        Generate Merkle proof for a secret.
        Returns list of (sibling_hash, is_left) tuples.
        """
        target_hash = hash_data(secret)
        try:
            index = self.leaves.index(target_hash)
        except ValueError:
            return None

        proof = []
        current_index = index

        for level in self.tree[:-1]:  # All levels except root
            if current_index % 2 == 0:
                # We're on the left, sibling is on the right
                if current_index + 1 < len(level):
                    sibling = level[current_index + 1]
                    proof.append((sibling, False))  # sibling is on right
                # else: no sibling (odd tree)
            else:
                # We're on the right, sibling is on the left
                sibling = level[current_index - 1]
                proof.append((sibling, True))  # sibling is on left

            current_index //= 2

        return proof

    def verify_proof(self, secret, proof):
        """Verify a Merkle proof."""
        current_hash = hash_data(secret)

        for sibling_hash, sibling_is_left in proof:
            if sibling_is_left:
                current_hash = hash_pair(sibling_hash, current_hash)
            else:
                current_hash = hash_pair(current_hash, sibling_hash)

        return current_hash == self.get_root()


# --- USAGE ---
if __name__ == "__main__":
    # Authorized agents
    secrets = [
        "hello",              # Test secret (SHA256 = 2cf24dba...)
        "agent_007_secret",
        "agent_008_secret",
        "agent_009_secret",
        "ghost_clearance_alpha",
    ]

    tree = MerkleTree(secrets)
    root = tree.get_root()

    print("=" * 60)
    print("  x402 MERKLE TREE - Agent Registry")
    print("=" * 60)
    print()
    print(f"Agents in tree: {len(secrets)}")
    print()
    print("Leaf hashes:")
    for i, (secret, leaf) in enumerate(zip(secrets, tree.leaves)):
        print(f"  [{i}] {secret[:20]:20} → {leaf[:16]}...")
    print()
    print(f"MERKLE ROOT: {root}")
    print()
    print("Paste this into your Rust circuit:")
    print(f'const MERKLE_ROOT: &str = "{root}";')
    print()

    # Generate and verify proof for "hello"
    test_secret = "hello"
    proof = tree.get_proof(test_secret)

    print("-" * 60)
    print(f"Proof for '{test_secret}':")
    print(f"  Proof length: {len(proof)} siblings")
    for i, (sibling, is_left) in enumerate(proof):
        side = "LEFT" if is_left else "RIGHT"
        print(f"  [{i}] {sibling[:16]}... ({side})")

    # Verify
    valid = tree.verify_proof(test_secret, proof)
    print(f"\n  Verification: {'VALID' if valid else 'INVALID'}")
    print()

    # Export for Rust
    print("-" * 60)
    print("Proof data for Rust (hex bytes):")
    proof_bytes = []
    directions = []
    for sibling, is_left in proof:
        proof_bytes.append(sibling)
        directions.append(is_left)

    print(f"  siblings: {json.dumps(proof_bytes)}")
    print(f"  is_left:  {json.dumps(directions)}")
