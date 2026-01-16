//! ╔══════════════════════════════════════════════════════════════════╗
//! ║   TRANSFORMER CIRCUIT FOR zkML                                   ║
//! ║   Full attention layer proof: input → attention → output         ║
//! ║                                                                  ║
//! ║   Proves: Given model weights W, input X produced output Y       ║
//! ║   Public: hash(W), hash(X), hash(Y)                             ║
//! ║   Private: W, X (actual values)                                  ║
//! ╚══════════════════════════════════════════════════════════════════╝

use crate::attention::{multi_head_attention, self_attention_simple, AttentionConfig, AttentionWeights};
use crate::quantization::QuantParams;
use crate::exp_table::SCALE;
use sha2::{Sha256, Digest};
use serde::{Deserialize, Serialize};

/// Transformer layer configuration (serializable for circuit input)
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct TransformerConfig {
    /// Model dimension
    pub d_model: usize,
    /// Number of attention heads
    pub n_heads: usize,
    /// Sequence length
    pub seq_len: usize,
    /// Use causal masking (for autoregressive models)
    pub causal: bool,
}

impl TransformerConfig {
    pub fn to_attention_config(&self) -> AttentionConfig {
        AttentionConfig::new(self.d_model, self.n_heads, self.seq_len, self.causal)
    }
}

/// Serializable weights for the transformer layer
#[derive(Serialize, Deserialize, Debug)]
pub struct TransformerWeights {
    /// Query projection weights [d_model * d_model]
    pub w_q: Vec<i32>,
    /// Key projection weights [d_model * d_model]
    pub w_k: Vec<i32>,
    /// Value projection weights [d_model * d_model]
    pub w_v: Vec<i32>,
    /// Output projection weights [d_model * d_model]
    pub w_o: Vec<i32>,
    /// Weight scale (Q8.24)
    pub scale: u32,
    /// Model salt for uniqueness
    pub salt: u64,
}

impl TransformerWeights {
    pub fn to_attention_weights(&self) -> AttentionWeights {
        AttentionWeights {
            w_q: self.w_q.clone(),
            w_k: self.w_k.clone(),
            w_v: self.w_v.clone(),
            w_o: self.w_o.clone(),
            weight_scale: QuantParams::with_scale(self.scale),
        }
    }
}

/// Input to the transformer circuit
#[derive(Serialize, Deserialize, Debug)]
pub struct TransformerInput {
    /// Input embeddings [seq_len * d_model] in Q8.24
    pub embeddings: Vec<i32>,
}

/// Output from the transformer circuit (for verification)
#[derive(Debug)]
pub struct TransformerProof {
    /// Hash of model weights
    pub model_hash: [u8; 32],
    /// Hash of input
    pub input_hash: [u8; 32],
    /// Hash of output
    pub output_hash: [u8; 32],
    /// The actual output (for use, not for proof)
    pub output: Vec<i32>,
}

/// Run the transformer layer and produce proof components
pub fn run_transformer(
    config: &TransformerConfig,
    weights: &TransformerWeights,
    input: &TransformerInput,
) -> TransformerProof {
    // Validate dimensions
    let d_model = config.d_model;
    let seq_len = config.seq_len;

    assert_eq!(
        weights.w_q.len(), d_model * d_model,
        "W_Q dimension mismatch"
    );
    assert_eq!(
        input.embeddings.len(), seq_len * d_model,
        "Input dimension mismatch"
    );

    // Convert to attention format
    let attn_config = config.to_attention_config();
    let attn_weights = weights.to_attention_weights();

    // Run attention
    let output = multi_head_attention(&input.embeddings, &attn_weights, &attn_config);

    // Compute hashes for public values
    let model_hash = hash_weights(weights);
    let input_hash = hash_input(input);
    let output_hash = hash_output(&output);

    TransformerProof {
        model_hash,
        input_hash,
        output_hash,
        output,
    }
}

/// Simplified version for testing: self-attention without projections
pub fn run_self_attention(
    input: &[i32],
    seq_len: usize,
    d_model: usize,
    causal: bool,
) -> (Vec<i32>, [u8; 32], [u8; 32]) {
    let output = self_attention_simple(input, seq_len, d_model, causal);

    let input_hash = Sha256::digest(bytemuck::cast_slice::<i32, u8>(input));
    let output_hash = Sha256::digest(bytemuck::cast_slice::<i32, u8>(&output));

    (output, input_hash.into(), output_hash.into())
}

/// Hash model weights
fn hash_weights(weights: &TransformerWeights) -> [u8; 32] {
    let mut hasher = Sha256::new();

    // Hash all weight matrices
    hasher.update(bytemuck::cast_slice::<i32, u8>(&weights.w_q));
    hasher.update(bytemuck::cast_slice::<i32, u8>(&weights.w_k));
    hasher.update(bytemuck::cast_slice::<i32, u8>(&weights.w_v));
    hasher.update(bytemuck::cast_slice::<i32, u8>(&weights.w_o));

    // Include scale and salt
    hasher.update(&weights.scale.to_le_bytes());
    hasher.update(&weights.salt.to_le_bytes());

    hasher.finalize().into()
}

/// Hash input embeddings
fn hash_input(input: &TransformerInput) -> [u8; 32] {
    Sha256::digest(bytemuck::cast_slice::<i32, u8>(&input.embeddings)).into()
}

/// Hash output
fn hash_output(output: &[i32]) -> [u8; 32] {
    Sha256::digest(bytemuck::cast_slice::<i32, u8>(output)).into()
}

/// Create dummy weights for testing
pub fn create_test_weights(d_model: usize) -> TransformerWeights {
    let size = d_model * d_model;

    // Identity-ish initialization (scaled)
    let mut w_q = vec![0i32; size];
    let mut w_k = vec![0i32; size];
    let mut w_v = vec![0i32; size];
    let mut w_o = vec![0i32; size];

    // Set diagonal to ~1.0
    for i in 0..d_model {
        let val = SCALE as i32;  // 1.0 in Q8.24
        w_q[i * d_model + i] = val;
        w_k[i * d_model + i] = val;
        w_v[i * d_model + i] = val;
        w_o[i * d_model + i] = val;
    }

    TransformerWeights {
        w_q,
        w_k,
        w_v,
        w_o,
        scale: SCALE,
        salt: 0x402_402_402_402,  // x402 Transformer identifier
    }
}

/// Create test input embeddings
pub fn create_test_input(seq_len: usize, d_model: usize) -> TransformerInput {
    let mut embeddings = vec![0i32; seq_len * d_model];

    // Simple pattern: position encoding-like
    for i in 0..seq_len {
        for j in 0..d_model {
            // Value based on position
            let val = ((i + 1) as i32 * SCALE as i32) / ((seq_len + 1) as i32);
            embeddings[i * d_model + j] = val / (d_model as i32);
        }
    }

    TransformerInput { embeddings }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transformer_runs() {
        let config = TransformerConfig {
            d_model: 8,
            n_heads: 2,
            seq_len: 4,
            causal: false,
        };

        let weights = create_test_weights(8);
        let input = create_test_input(4, 8);

        let proof = run_transformer(&config, &weights, &input);

        // Check output dimensions
        assert_eq!(proof.output.len(), 4 * 8);

        // Check hashes are non-zero
        assert_ne!(proof.model_hash, [0u8; 32]);
        assert_ne!(proof.input_hash, [0u8; 32]);
        assert_ne!(proof.output_hash, [0u8; 32]);
    }

    #[test]
    fn test_self_attention_simple() {
        let seq_len = 2;
        let d_model = 4;

        let input = vec![SCALE as i32 / 2; seq_len * d_model];

        let (output, in_hash, out_hash) = run_self_attention(&input, seq_len, d_model, false);

        assert_eq!(output.len(), seq_len * d_model);
        assert_ne!(in_hash, [0u8; 32]);
        assert_ne!(out_hash, [0u8; 32]);
    }

    #[test]
    fn test_deterministic_hashes() {
        let weights = create_test_weights(4);

        let hash1 = hash_weights(&weights);
        let hash2 = hash_weights(&weights);

        assert_eq!(hash1, hash2, "Same weights should produce same hash");
    }
}
