//! ╔══════════════════════════════════════════════════════════════════╗
//! ║                                                                  ║
//! ║   TRANSFORMER PROVER — Host-side proof generation               ║
//! ║   x402 Clearinghouse zkML Layer                                 ║
//! ║                                                                  ║
//! ║   Generates ZK proofs of transformer attention computation      ║
//! ║                                                                  ║
//! ╚══════════════════════════════════════════════════════════════════╝

use sp1_sdk::{ProverClient, SP1Stdin, HashableKey};
use bincode::{config, serde::encode_to_vec};
use serde::{Deserialize, Serialize};
use std::time::Instant;

const SCALE: i32 = 1 << 24;  // Q8.24 fixed-point

/// Transformer configuration (must match circuit)
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct TransformerConfig {
    pub d_model: usize,
    pub n_heads: usize,
    pub seq_len: usize,
    pub causal: bool,
}

/// Transformer weights (must match circuit)
#[derive(Serialize, Deserialize, Debug)]
pub struct TransformerWeights {
    pub w_q: Vec<i32>,
    pub w_k: Vec<i32>,
    pub w_v: Vec<i32>,
    pub w_o: Vec<i32>,
    pub scale: u32,
    pub salt: u64,
}

/// Transformer input (must match circuit)
#[derive(Serialize, Deserialize, Debug)]
pub struct TransformerInput {
    pub embeddings: Vec<i32>,
}

/// Create identity-ish weights for testing
fn create_test_weights(d_model: usize) -> TransformerWeights {
    let size = d_model * d_model;
    let mut w_q = vec![0i32; size];
    let mut w_k = vec![0i32; size];
    let mut w_v = vec![0i32; size];
    let mut w_o = vec![0i32; size];

    // Identity diagonal
    for i in 0..d_model {
        w_q[i * d_model + i] = SCALE;
        w_k[i * d_model + i] = SCALE;
        w_v[i * d_model + i] = SCALE;
        w_o[i * d_model + i] = SCALE;
    }

    TransformerWeights {
        w_q, w_k, w_v, w_o,
        scale: SCALE as u32,
        salt: 0x402_402_402_402,
    }
}

/// Create test input
fn create_test_input(seq_len: usize, d_model: usize) -> TransformerInput {
    let mut embeddings = vec![0i32; seq_len * d_model];

    for i in 0..seq_len {
        for j in 0..d_model {
            embeddings[i * d_model + j] = (SCALE / 2) / (d_model as i32);
        }
    }

    TransformerInput { embeddings }
}

fn main() {
    println!("╔══════════════════════════════════════════════════════════════╗");
    println!("║   TRANSFORMER ATTENTION PROVER                               ║");
    println!("║   x402 Clearinghouse zkML                                    ║");
    println!("╚══════════════════════════════════════════════════════════════╝");
    println!();

    // Configuration
    let config = TransformerConfig {
        d_model: 16,     // Small for testing (prod: 64-512)
        n_heads: 2,      // 2 attention heads
        seq_len: 4,      // 4 tokens
        causal: true,    // Autoregressive
    };

    println!("[*] Configuration:");
    println!("    d_model: {}", config.d_model);
    println!("    n_heads: {}", config.n_heads);
    println!("    seq_len: {}", config.seq_len);
    println!("    causal: {}", config.causal);
    println!();

    // Create test data
    let weights = create_test_weights(config.d_model);
    let input = create_test_input(config.seq_len, config.d_model);

    println!("[*] Test data created:");
    println!("    Weights: 4 matrices of {}x{}", config.d_model, config.d_model);
    println!("    Input: {} tokens x {} dims", config.seq_len, config.d_model);
    println!();

    // Setup prover
    println!("[1] Setting up SP1 prover...");
    let client = ProverClient::from_env();

    // Load the transformer circuit ELF (built with cargo prove build)
    let elf = include_bytes!("../../../program/target/elf-compilation/riscv32im-succinct-zkvm-elf/release/transformer-circuit");

    let (pk, vk) = client.setup(elf);
    println!("    [✓] Prover setup complete");
    println!();

    // Serialize inputs
    println!("[2] Serializing circuit inputs...");
    let bincode_cfg = config::standard();
    let mut stdin = SP1Stdin::new();
    stdin.write_vec(encode_to_vec(&config, bincode_cfg).unwrap());
    stdin.write_vec(encode_to_vec(&weights, bincode_cfg).unwrap());
    stdin.write_vec(encode_to_vec(&input, bincode_cfg).unwrap());
    println!("    [✓] Inputs serialized");
    println!();

    // Generate proof
    println!("[3] Generating Groth16 proof...");
    println!("    This may take several minutes...");
    println!();

    let start = Instant::now();
    let proof = client.prove(&pk, &stdin)
        .groth16()
        .run()
        .expect("Proving failed");
    let elapsed = start.elapsed();

    println!("[✓] Proof generated successfully!");
    println!();
    println!("═══════════════════════════════════════════════════════════════");
    println!("  BENCHMARK RESULTS");
    println!("═══════════════════════════════════════════════════════════════");
    println!("  Proof generation time: {:.2}s", elapsed.as_secs_f64());
    println!("  Proof size: {} bytes", proof.bytes().len());
    println!();
    println!("  VERIFICATION KEY (for TransformerGuardian):");
    println!("  {}", vk.bytes32());
    println!();
    println!("  PUBLIC VALUES ({} bytes):", proof.public_values.as_slice().len());
    let pub_vals = proof.public_values.as_slice();

    // Parse public values (96 bytes = 3 hashes of 32 bytes each)
    if pub_vals.len() >= 96 {
        println!("  Model Hash:  0x{}", hex::encode(&pub_vals[0..32]));
        println!("  Input Hash:  0x{}", hex::encode(&pub_vals[32..64]));
        println!("  Output Hash: 0x{}", hex::encode(&pub_vals[64..96]));
    }

    if pub_vals.len() > 96 {
        println!("  First Output: 0x{}", hex::encode(&pub_vals[96..]));
    }
    println!("═══════════════════════════════════════════════════════════════");
    println!();

    // Check against targets
    println!("  TARGET COMPARISON:");
    println!("  ─────────────────────────────────────────────────────────────");
    let proof_time_ok = elapsed.as_secs() < 10;
    let proof_size_ok = proof.bytes().len() < 500;

    println!("  Proof time < 10s: {} ({:.2}s)",
        if proof_time_ok { "✓" } else { "✗" },
        elapsed.as_secs_f64()
    );
    println!("  Proof size < 500 bytes: {} ({} bytes)",
        if proof_size_ok { "✓" } else { "✗" },
        proof.bytes().len()
    );
    println!();

    println!("[*] Ready for on-chain verification!");
}
