//! x402 Identity Prover Script
//!
//! Generates ZK proofs for agent identity verification.
//! Usage: cargo run --release -- --secret "hello"

use sp1_sdk::{ProverClient, SP1Stdin};
use clap::Parser;

/// The ELF binary of the identity circuit
const ELF: &[u8] = include_bytes!("../../program/elf/riscv32im-succinct-zkvm-elf");

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Args {
    /// The secret key to prove knowledge of
    #[arg(short, long)]
    secret: String,

    /// Output file for the proof
    #[arg(short, long, default_value = "proof.bin")]
    output: String,
}

fn main() {
    // Setup logging
    sp1_sdk::utils::setup_logger();

    let args = Args::parse();

    println!("[*] x402 Identity Prover");
    println!("[*] Generating ZK proof...");

    // Initialize the prover client
    let client = ProverClient::from_env();

    // Setup the inputs
    let mut stdin = SP1Stdin::new();
    stdin.write(&args.secret);

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
    std::fs::write(&args.output, &proof_bytes).expect("Failed to write proof");

    println!("[+] Proof saved to: {}", args.output);
    println!("[+] Proof size: {} bytes", proof_bytes.len());

    // Output the proof bytes in hex for on-chain submission
    println!("\n[*] For on-chain submission:");
    println!("0x{}", hex::encode(&proof_bytes[..64.min(proof_bytes.len())]));
}
