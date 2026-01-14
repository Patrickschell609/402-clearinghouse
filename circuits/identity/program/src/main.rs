#![no_main]
sp1_zkvm::entrypoint!(main);

use sp1_zkvm::io;
use sha2::{Sha256, Digest};

/// x402 Identity Circuit
///
/// Proves: "I know a secret that hashes to the authorized value"
/// Reveals: Nothing about the secret itself
///
/// Production: Replace AUTHORIZED_HASH with Merkle root of all KYC'd agents

// SHA256("hello") - test value
// In production: Merkle root of authorized agent identity hashes
const AUTHORIZED_HASH: &str = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";

pub fn main() {
    // PRIVATE INPUT: Agent's secret key (never leaves local machine)
    let secret_key: String = io::read();

    // COMPUTE: Hash the secret
    let mut hasher = Sha256::new();
    hasher.update(secret_key.as_bytes());
    let result = hasher.finalize();
    let computed_hash = hex::encode(result);

    // CONSTRAINT: Must be in the authorized registry
    assert_eq!(
        computed_hash,
        AUTHORIZED_HASH,
        "ACCESS DENIED: Identity not in registry"
    );

    // PUBLIC OUTPUT: Only reveals "authorized = true"
    // Verifier learns nothing about which agent or what secret
    io::commit(&true);
}
