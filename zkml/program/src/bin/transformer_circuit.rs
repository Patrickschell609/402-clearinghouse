//! ╔══════════════════════════════════════════════════════════════════╗
//! ║   PROOF OF INTELLIGENCE — Transformer Circuit                    ║
//! ║   x402 Clearinghouse zkML Layer                                  ║
//! ║                                                                  ║
//! ║   Proves: An attention layer produced a specific output          ║
//! ║   Public: model_hash, input_hash, output_hash                   ║
//! ╚══════════════════════════════════════════════════════════════════╝

#![no_main]
use sp1_zkvm::entrypoint;
use sp1_zkvm::io::{read_vec, commit_slice};
use bincode::{config, serde::decode_from_slice};
use sha2::{Digest, Sha256};

// Import our transformer library
use decision_tree_program::{
    TransformerConfig, TransformerWeights, TransformerInput,
    multi_head_attention, AttentionConfig, AttentionWeights,
    quantization::QuantParams,
};

entrypoint!(main);

pub fn main() {
    // Read private inputs (serialized bytes)
    let config_bytes: Vec<u8> = read_vec();
    let weights_bytes: Vec<u8> = read_vec();
    let input_bytes: Vec<u8> = read_vec();

    // Deserialize with bincode 2.0 API
    let bincode_config = config::standard();

    let (config, _): (TransformerConfig, _) =
        decode_from_slice(&config_bytes, bincode_config).expect("Failed to decode config");
    let (weights, _): (TransformerWeights, _) =
        decode_from_slice(&weights_bytes, bincode_config).expect("Failed to decode weights");
    let (input, _): (TransformerInput, _) =
        decode_from_slice(&input_bytes, bincode_config).expect("Failed to decode input");

    // Hash model weights (proves we have the actual model)
    let model_hash = {
        let mut hasher = Sha256::new();
        hasher.update(&weights_bytes);
        hasher.finalize()
    };

    // Hash input (proves data integrity)
    let input_hash = Sha256::digest(&input_bytes);

    // Convert to runtime formats
    let attn_config = AttentionConfig::new(
        config.d_model,
        config.n_heads,
        config.seq_len,
        config.causal,
    );

    let attn_weights = AttentionWeights {
        w_q: weights.w_q,
        w_k: weights.w_k,
        w_v: weights.w_v,
        w_o: weights.w_o,
        weight_scale: QuantParams::with_scale(weights.scale),
    };

    // ═══════════════════════════════════════════════════════════════
    // THE PROOF OF INTELLIGENCE — Execute attention layer
    // ═══════════════════════════════════════════════════════════════
    let output = multi_head_attention(&input.embeddings, &attn_weights, &attn_config);

    // Hash output (proves computation result)
    let output_bytes: Vec<u8> = output.iter()
        .flat_map(|x| x.to_le_bytes())
        .collect();
    let output_hash = Sha256::digest(&output_bytes);

    // ═══════════════════════════════════════════════════════════════
    // COMMIT PUBLIC VALUES (96 bytes total)
    // These are what the Solidity contract will verify
    // ═══════════════════════════════════════════════════════════════
    commit_slice(model_hash.as_slice());   // bytes32: Model identity
    commit_slice(input_hash.as_slice());   // bytes32: Input integrity
    commit_slice(output_hash.as_slice());  // bytes32: Output integrity

    // Optionally commit first output value as a "prediction"
    // This allows on-chain logic to act on the result
    if !output.is_empty() {
        commit_slice(&output[0].to_be_bytes());  // 4 bytes: First output value
    }
}
