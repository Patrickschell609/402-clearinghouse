//! ╔══════════════════════════════════════════════════════════════════╗
//! ║                                                                  ║
//! ║   PROOF OF INTELLIGENCE — Decision Tree Circuit                 ║
//! ║   x402 Clearinghouse zkML Layer                                 ║
//! ║                                                                  ║
//! ║   Author: Patrick Schell (@Patrickschell609)                    ║
//! ║   Proves: An AI strategy computed a specific decision           ║
//! ║                                                                  ║
//! ╚══════════════════════════════════════════════════════════════════╝

#![no_main]
use sp1_zkvm::entrypoint;
use sp1_zkvm::io::{read_vec, commit_slice};
use bincode::{config, serde::decode_from_slice};
use fixed::types::I32F32;
use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};

entrypoint!(main);

/// A node in the decision tree
/// If feature_index < 0, this is a leaf node
#[derive(Serialize, Deserialize, Debug)]
struct Node {
    feature_index: i32,     // -1 if leaf node
    threshold: I32F32,      // Ignored if leaf
    left: usize,            // Child indices
    right: usize,
    value: I32F32,          // Prediction if leaf
}

/// The trading strategy model
/// Contains the decision tree structure and a salt for uniqueness
#[derive(Serialize, Deserialize, Debug)]
struct TradingModel {
    nodes: Vec<Node>,
    salt: u64,              // For model uniqueness/privacy
}

/// Market data input
/// Features could be: RSI, MACD, Volume, Price Delta, etc.
#[derive(Serialize, Deserialize, Debug)]
struct MarketData {
    features: Vec<I32F32>,
}

/// Traverse the decision tree and return the prediction
fn evaluate(model: &TradingModel, data: &MarketData) -> I32F32 {
    let mut idx: usize = 0;  // Start at root
    loop {
        let node = &model.nodes[idx];
        if node.feature_index < 0 {
            return node.value;  // Leaf: return prediction
        }
        let feature_val = data.features[node.feature_index as usize];
        if feature_val < node.threshold {
            idx = node.left;
        } else {
            idx = node.right;
        }
    }
}

pub fn main() {
    // Read private inputs (serialized bytes)
    let model_bytes: Vec<u8> = read_vec();
    let data_bytes: Vec<u8> = read_vec();

    // Deserialize with bincode 2.0 API
    let config = config::standard();
    let (model, _): (TradingModel, _) = decode_from_slice(&model_bytes, config).unwrap();
    let (data, _): (MarketData, _) = decode_from_slice(&data_bytes, config).unwrap();

    // Hash model (includes salt) inside circuit
    // This proves we have the actual model, not just a hash
    let model_hash = Sha256::digest(&model_bytes);

    // Hash input data for integrity
    let data_hash = Sha256::digest(&data_bytes);

    // Execute inference — THE PROOF OF INTELLIGENCE
    let prediction = evaluate(&model, &data);

    // Commit public values (exactly 72 bytes: 32 + 32 + 8)
    // These are what the Solidity contract will verify
    commit_slice(model_hash.as_slice());                 // bytes32: Model identity
    commit_slice(data_hash.as_slice());                  // bytes32: Data integrity
    commit_slice(&prediction.to_bits().to_be_bytes());   // 8 bytes: Prediction (big-endian)
}
