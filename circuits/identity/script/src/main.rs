//! x402 Identity Prover Script - Merkle Tree Version
//!
//! Generates ZK proofs for agent identity verification.
//! Usage: cargo run --release -- --secret "hello" --proof-file proof.json

use sp1_sdk::{ProverClient, SP1Stdin};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::fs;

/// The ELF binary of the identity circuit
const ELF: &[u8] = include_bytes!("../../program/elf/riscv32im-succinct-zkvm-elf");

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// The secret key to prove knowledge of
    #[arg(short, long)]
    secret: String,

    /// JSON file containing the Merkle proof (siblings and directions)
    #[arg(short, long, default_value = "merkle_proof.json")]
    proof_file: String,

    /// Output file for the ZK proof
    #[arg(short, long, default_value = "zk_proof.bin")]
    output: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct MerkleProof {
    siblings: Vec<String>,
    directions: Vec<bool>,
}

fn main() {
    sp1_sdk::utils::setup_logger();

    let args = Args::parse();

    println!("[*] x402 Identity Prover (Merkle Tree)");
    println!("[*] Loading Merkle proof from: {}", args.proof_file);

    // Load Merkle proof from file
    let proof_data: MerkleProof = match fs::read_to_string(&args.proof_file) {
        Ok(content) => serde_json::from_str(&content).expect("Invalid proof JSON"),
        Err(_) => {
            // Default proof for "hello" - for testing
            println!("[!] No proof file found, using default for 'hello'");
            MerkleProof {
                siblings: vec![
                    "2262557677467692ff193048ddd3090b720634a75c499fcdc58a1cad3f4623a5".to_string(),
                    "4aab8c62c79fce0347d0f5d05f518a94ebc788b60087a78c7ac19a974c94cfc1".to_string(),
                    "b16b91fd3cca3c6fec0b1bcf813aeb510354ba30818491b8a55ee3a3884906b9".to_string(),
                ],
                directions: vec![false, false, false],
            }
        }
    };

    println!("[*] Proof has {} siblings", proof_data.siblings.len());
    println!("[*] Generating ZK proof...");

    // Initialize the prover client
    let client = ProverClient::from_env();

    // Setup the inputs
    let mut stdin = SP1Stdin::new();
    stdin.write(&args.secret);
    stdin.write(&proof_data.siblings);
    stdin.write(&proof_data.directions);

    // Generate the proof
    let (pk, vk) = client.setup(ELF);
    let proof = client
        .prove(&pk, &stdin)
        .groth16()
        .run()
        .expect("Failed to generate proof");

    // Verify locally first
    client
        .verify(&proof, &vk)
        .expect("Proof verification failed!");

    println!("[+] Proof generated and verified locally");

    // Save proof to file
    let proof_bytes = bincode::serialize(&proof).expect("Failed to serialize proof");
    fs::write(&args.output, &proof_bytes).expect("Failed to write proof");

    println!("[+] ZK Proof saved to: {}", args.output);
    println!("[+] Proof size: {} bytes", proof_bytes.len());

    // Output for on-chain submission
    println!("\n[*] For on-chain submission:");
    println!("0x{}", hex::encode(&proof_bytes[..64.min(proof_bytes.len())]));
}
