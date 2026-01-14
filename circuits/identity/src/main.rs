#![no_main]
sp1_zkvm::entrypoint!(main);

use sp1_zkvm::io;
use sha2::{Sha256, Digest};

// THE "REGISTRY"
// In production, this is a Merkle Root of all KYC'd agents.
// For MVP, this is the SHA256 hash of your secret access key.
// Example: SHA256("agent_007_clearance")
const AUTHORIZED_HASH: &str = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";

pub fn main() {
    // 1. INPUT: The Agent reads its secret key into the ZKVM
    // This happens locally. The secret never leaves the machine.
    let secret_key = io::read::<String>();

    // 2. LOGIC: Hash the secret
    let mut hasher = Sha256::new();
    hasher.update(secret_key.as_bytes());
    let result = hasher.finalize();
    let computed_hash = hex::encode(result);

    // 3. CONSTRAINT: Assert the secret matches the Whitelist
    if computed_hash != AUTHORIZED_HASH {
        panic!("ACCESS DENIED: Identity not found in Registry.");
    }

    // 4. OUTPUT: Publicly commit to "Success"
    // The Verifier (Contract) sees this and knows:
    // "The entity generating this proof DEFINITELY knows the secret key."
    io::commit(&true);
}
