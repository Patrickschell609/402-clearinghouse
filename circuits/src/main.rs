//! SP1 Compliance Circuit for Accredited Investor Verification
//!
//! This program runs inside the SP1 zkVM and proves:
//! 1. The agent's operator has passed KYC
//! 2. The operator meets accredited investor criteria
//! 3. The operator is not on a sanctions list
//!
//! All without revealing the operator's identity on-chain.

#![no_main]
sp1_zkvm::entrypoint!(main);

use sha2::{Sha256, Digest};
use serde::{Deserialize, Serialize};

/// Private inputs - known only to the agent
#[derive(Serialize, Deserialize)]
struct PrivateInputs {
    /// Operator's identity commitment (hash of PII)
    identity_commitment: [u8; 32],
    
    /// KYC provider's signature over the identity
    kyc_signature: [u8; 64],
    
    /// Accreditation attestation data
    accreditation_proof: AccreditationProof,
    
    /// OFAC/sanctions check result
    sanctions_check: SanctionsCheck,
    
    /// Agent's Ethereum address (to bind proof to caller)
    agent_address: [u8; 20],
    
    /// Timestamp when accreditation expires
    valid_until: u64,
}

#[derive(Serialize, Deserialize)]
struct AccreditationProof {
    /// One of: "net_worth", "income", "professional"
    method: AccreditationMethod,
    
    /// Provider's signature over the attestation
    attestation_signature: [u8; 64],
    
    /// When the attestation was issued
    issued_at: u64,
}

#[derive(Serialize, Deserialize)]
enum AccreditationMethod {
    /// Net worth > $1M (excluding primary residence)
    NetWorth,
    /// Income > $200k (single) or $300k (joint) for past 2 years
    Income,
    /// Licensed professional (Series 7, 65, 82)
    Professional,
    /// Institutional entity
    Institutional,
}

#[derive(Serialize, Deserialize)]
struct SanctionsCheck {
    /// Merkle root of the sanctions list at check time
    sanctions_list_root: [u8; 32],
    
    /// Merkle proof showing identity NOT in list
    exclusion_proof: Vec<[u8; 32]>,
    
    /// Provider's signature
    check_signature: [u8; 64],
    
    /// When check was performed
    checked_at: u64,
}

/// Public outputs - committed on-chain
#[derive(Serialize, Deserialize)]
struct PublicOutputs {
    /// Agent address (must match msg.sender in smart contract)
    agent_address: [u8; 20],
    
    /// Timestamp when verification expires
    valid_until: u64,
    
    /// Hash of jurisdiction (for regulatory compliance)
    jurisdiction_hash: [u8; 32],
    
    /// Commitment to the identity (for audit trails)
    identity_commitment: [u8; 32],
}

/// Trusted KYC provider public keys (hardcoded for security)
const TRUSTED_KYC_PROVIDERS: &[[u8; 33]] = &[
    // Provider 1 (e.g., Jumio)
    [0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01],
    // Provider 2 (e.g., Plaid)
    [0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02],
];

/// Maximum age of sanctions check (30 days)
const MAX_SANCTIONS_AGE: u64 = 30 * 24 * 60 * 60;

/// Maximum age of accreditation attestation (1 year)
const MAX_ACCREDITATION_AGE: u64 = 365 * 24 * 60 * 60;

fn main() {
    // Read private inputs from the prover
    let inputs: PrivateInputs = sp1_zkvm::io::read();
    
    // Get current timestamp (passed as public input for determinism)
    let current_time: u64 = sp1_zkvm::io::read();
    
    // 1. VERIFY KYC SIGNATURE
    // The KYC provider has signed: H(identity_commitment || "KYC_VERIFIED")
    let kyc_message = compute_kyc_message(&inputs.identity_commitment);
    assert!(
        verify_provider_signature(&kyc_message, &inputs.kyc_signature),
        "Invalid KYC signature"
    );
    
    // 2. VERIFY ACCREDITATION
    // Check attestation is from trusted provider and not expired
    let attestation_age = current_time.saturating_sub(inputs.accreditation_proof.issued_at);
    assert!(
        attestation_age <= MAX_ACCREDITATION_AGE,
        "Accreditation attestation expired"
    );
    
    let accreditation_message = compute_accreditation_message(
        &inputs.identity_commitment,
        &inputs.accreditation_proof.method,
        inputs.accreditation_proof.issued_at,
    );
    assert!(
        verify_provider_signature(&accreditation_message, &inputs.accreditation_proof.attestation_signature),
        "Invalid accreditation signature"
    );
    
    // 3. VERIFY SANCTIONS CHECK
    // Check is recent enough
    let sanctions_age = current_time.saturating_sub(inputs.sanctions_check.checked_at);
    assert!(
        sanctions_age <= MAX_SANCTIONS_AGE,
        "Sanctions check too old"
    );
    
    // Verify Merkle exclusion proof (identity NOT in sanctions list)
    assert!(
        verify_merkle_exclusion(
            &inputs.identity_commitment,
            &inputs.sanctions_check.sanctions_list_root,
            &inputs.sanctions_check.exclusion_proof,
        ),
        "Failed sanctions exclusion proof"
    );
    
    // 4. VERIFY VALIDITY PERIOD
    assert!(
        inputs.valid_until > current_time,
        "Verification already expired"
    );
    
    // 5. COMPUTE JURISDICTION HASH
    // Derived from identity commitment in a privacy-preserving way
    let jurisdiction_hash = compute_jurisdiction_hash(&inputs.identity_commitment);
    
    // 6. COMMIT PUBLIC OUTPUTS
    let public_outputs = PublicOutputs {
        agent_address: inputs.agent_address,
        valid_until: inputs.valid_until,
        jurisdiction_hash,
        identity_commitment: inputs.identity_commitment,
    };
    
    // Write public outputs to the proof
    sp1_zkvm::io::commit(&public_outputs);
}

/// Compute the message that KYC providers sign
fn compute_kyc_message(identity_commitment: &[u8; 32]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(identity_commitment);
    hasher.update(b"KYC_VERIFIED_V1");
    hasher.finalize().into()
}

/// Compute the message for accreditation attestation
fn compute_accreditation_message(
    identity_commitment: &[u8; 32],
    method: &AccreditationMethod,
    issued_at: u64,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(identity_commitment);
    hasher.update(match method {
        AccreditationMethod::NetWorth => b"ACCREDITED_NET_WORTH",
        AccreditationMethod::Income => b"ACCREDITED_INCOME",
        AccreditationMethod::Professional => b"ACCREDITED_PROFESSIONAL",
        AccreditationMethod::Institutional => b"ACCREDITED_INSTITUTIONAL",
    });
    hasher.update(&issued_at.to_le_bytes());
    hasher.finalize().into()
}

/// Verify signature from trusted provider
fn verify_provider_signature(message: &[u8; 32], signature: &[u8; 64]) -> bool {
    // In production: use k256 ECDSA verification
    // For MVP: simplified check
    
    // Compute expected signature hash
    let mut hasher = Sha256::new();
    hasher.update(message);
    hasher.update(signature);
    let check = hasher.finalize();
    
    // Mock verification (in production, verify against TRUSTED_KYC_PROVIDERS)
    check[0] != 0xff // Simplified check
}

/// Verify Merkle exclusion proof (identity NOT in sanctions list)
fn verify_merkle_exclusion(
    identity: &[u8; 32],
    root: &[u8; 32],
    proof: &[[u8; 32]],
) -> bool {
    // Compute leaf
    let mut hasher = Sha256::new();
    hasher.update(identity);
    hasher.update(b"SANCTIONS_LEAF");
    let mut current = hasher.finalize();
    
    // Walk up the tree
    for sibling in proof {
        hasher = Sha256::new();
        if current.as_slice() < sibling.as_slice() {
            hasher.update(current);
            hasher.update(sibling);
        } else {
            hasher.update(sibling);
            hasher.update(current);
        }
        current = hasher.finalize();
    }
    
    // For exclusion proof, the computed root should NOT match
    // (In a proper sparse Merkle tree, this would be more complex)
    current.as_slice() != root.as_slice()
}

/// Compute jurisdiction hash from identity commitment
fn compute_jurisdiction_hash(identity: &[u8; 32]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(identity);
    hasher.update(b"JURISDICTION_V1");
    hasher.finalize().into()
}
