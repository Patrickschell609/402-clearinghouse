//! ╔══════════════════════════════════════════════════════════════════╗
//! ║                                                                  ║
//! ║   PROOF OF INTELLIGENCE — Host Prover                           ║
//! ║   x402 Clearinghouse zkML Layer                                 ║
//! ║                                                                  ║
//! ║   Author: Patrick Schell (@Patrickschell609)                    ║
//! ║   Generates ZK proofs of AI decision-making                     ║
//! ║                                                                  ║
//! ╚══════════════════════════════════════════════════════════════════╝

use sp1_sdk::{ProverClient, SP1Stdin, HashableKey};
use bincode::{config, serde::encode_to_vec};
use fixed::types::I32F32;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug)]
struct Node {
    feature_index: i32,
    threshold: I32F32,
    left: usize,
    right: usize,
    value: I32F32,
}

#[derive(Serialize, Deserialize, Debug)]
struct TradingModel {
    nodes: Vec<Node>,
    salt: u64,
}

#[derive(Serialize, Deserialize, Debug)]
struct MarketData {
    features: Vec<I32F32>,
}

fn main() {
    println!("╔══════════════════════════════════════════════════════════════╗");
    println!("║   PROOF OF INTELLIGENCE — zkML Prover                       ║");
    println!("║   x402 Clearinghouse                                        ║");
    println!("╚══════════════════════════════════════════════════════════════╝");
    println!();

    // Setup prover
    let client = ProverClient::from_env();
    let elf = include_bytes!("../../program/target/elf-compilation/riscv32im-succinct-zkvm-elf/release/decision-tree-program");
    let (pk, vk) = client.setup(elf);

    // Example: Simple RSI-based trading strategy
    // If RSI < 30 -> Buy (oversold)
    // If RSI >= 30 -> No trade
    let model = TradingModel {
        nodes: vec![
            // Root node: check RSI (feature 0)
            Node {
                feature_index: 0,
                threshold: I32F32::from_num(30),
                left: 1,   // RSI < 30 -> go to node 1
                right: 2,  // RSI >= 30 -> go to node 2
                value: I32F32::ZERO
            },
            // Leaf: Buy signal (1.0)
            Node {
                feature_index: -1,
                threshold: I32F32::ZERO,
                left: 0,
                right: 0,
                value: I32F32::from_num(1)
            },
            // Leaf: No trade (0.0)
            Node {
                feature_index: -1,
                threshold: I32F32::ZERO,
                left: 0,
                right: 0,
                value: I32F32::ZERO
            },
        ],
        salt: 0x402402402402,  // x402 Clearinghouse identifier
    };

    // Market data: RSI = 25 (oversold -> should trigger buy)
    let data = MarketData {
        features: vec![I32F32::from_num(25)],
    };

    println!("[*] Model: RSI Trading Strategy");
    println!("[*] Input: RSI = 25 (oversold)");
    println!("[*] Expected: Buy signal (1.0)");
    println!();

    // Serialize private inputs with bincode 2.0 API
    let config = config::standard();
    let mut stdin = SP1Stdin::new();
    stdin.write_vec(encode_to_vec(&model, config).unwrap());
    stdin.write_vec(encode_to_vec(&data, config).unwrap());

    // Generate Groth16 proof (on-chain verifiable)
    println!("[1] Generating Proof of Intelligence (Groth16)...");
    println!("    This may take a few minutes...");
    let proof = client.prove(&pk, &stdin).groth16().run().expect("Proving failed");

    println!("[✓] Proof generated successfully!");
    println!();
    println!("═══════════════════════════════════════════════════════════════");
    println!("  VERIFICATION KEY (for AIGuardian constructor):");
    println!("  {}", vk.bytes32());
    println!();
    println!("  PROOF SIZE: {} bytes", proof.bytes().len());
    println!();
    println!("  PUBLIC VALUES (hex):");
    let pub_vals = proof.public_values.as_slice();
    println!("  {}", hex::encode(pub_vals));
    println!("═══════════════════════════════════════════════════════════════");
    println!();
    println!("[*] Ready to submit to AIGuardian contract on Base");
    println!();
    println!("Save these values for contract deployment!");
}
