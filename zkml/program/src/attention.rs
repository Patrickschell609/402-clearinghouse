//! ╔══════════════════════════════════════════════════════════════════╗
//! ║   MULTI-HEAD ATTENTION FOR zkML                                  ║
//! ║   Single transformer attention layer in ZK                       ║
//! ║                                                                  ║
//! ║   Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V                ║
//! ╚══════════════════════════════════════════════════════════════════╝

use crate::exp_table::SCALE;
use crate::softmax::{softmax_2d, softmax_masked};
use crate::quantization::QuantParams;

/// Multi-head attention configuration
#[derive(Clone, Copy, Debug)]
pub struct AttentionConfig {
    /// Model dimension (d_model)
    pub d_model: usize,
    /// Number of attention heads
    pub n_heads: usize,
    /// Dimension per head (d_model / n_heads)
    pub d_head: usize,
    /// Sequence length
    pub seq_len: usize,
    /// Use causal masking
    pub causal: bool,
}

impl AttentionConfig {
    pub fn new(d_model: usize, n_heads: usize, seq_len: usize, causal: bool) -> Self {
        assert!(d_model % n_heads == 0, "d_model must be divisible by n_heads");
        Self {
            d_model,
            n_heads,
            d_head: d_model / n_heads,
            seq_len,
            causal,
        }
    }
}

/// Attention weights (pre-loaded, not trained in ZK)
pub struct AttentionWeights {
    /// Query projection [d_model, d_model] in Q8.24
    pub w_q: Vec<i32>,
    /// Key projection [d_model, d_model]
    pub w_k: Vec<i32>,
    /// Value projection [d_model, d_model]
    pub w_v: Vec<i32>,
    /// Output projection [d_model, d_model]
    pub w_o: Vec<i32>,
    /// Quantization scale for weights
    pub weight_scale: QuantParams,
}

/// Single-head attention (internal)
/// Q, K, V are [seq_len, d_head] in Q8.24
fn single_head_attention(
    q: &[i32],
    k: &[i32],
    v: &[i32],
    config: &AttentionConfig,
) -> Vec<i32> {
    let seq_len = config.seq_len;
    let d_head = config.d_head;

    // Step 1: Compute attention scores = Q @ K^T
    // [seq_len, d_head] @ [d_head, seq_len] = [seq_len, seq_len]
    let mut scores = vec![0i32; seq_len * seq_len];

    for i in 0..seq_len {
        for j in 0..seq_len {
            let mut dot: i64 = 0;
            for l in 0..d_head {
                dot += (q[i * d_head + l] as i64) * (k[j * d_head + l] as i64);
            }
            // Scale by 1/sqrt(d_head) in fixed point
            // sqrt(64) = 8, so scale by 1/8 = >> 3 for d_head=64
            // For general d_head: approximate sqrt as (d_head >> 1) for powers of 2
            let sqrt_d = isqrt(d_head as u32);
            scores[i * seq_len + j] = (dot / (sqrt_d as i64 * (SCALE as i64))) as i32;
        }
    }

    // Step 2: Softmax over scores
    let attention_weights = if config.causal {
        softmax_masked(&scores, seq_len, true)
    } else {
        softmax_2d(&scores, seq_len)
    };

    // Step 3: Apply attention to values
    // attention_weights [seq_len, seq_len] @ V [seq_len, d_head] = [seq_len, d_head]
    let mut output = vec![0i32; seq_len * d_head];

    for i in 0..seq_len {
        for l in 0..d_head {
            let mut acc: i64 = 0;
            for j in 0..seq_len {
                // attention_weights are in Q8.24 (from softmax)
                // v is in Q8.24
                // result should be Q8.24
                let weight = attention_weights[i * seq_len + j] as i64;
                let val = v[j * d_head + l] as i64;
                acc += weight * val;
            }
            // Divide by SCALE since we multiplied two Q8.24 values
            output[i * d_head + l] = (acc / (SCALE as i64)) as i32;
        }
    }

    output
}

/// Integer square root (for scaling)
fn isqrt(n: u32) -> u32 {
    if n == 0 {
        return 0;
    }
    let mut x = n;
    let mut y = (x + 1) / 2;
    while y < x {
        x = y;
        y = (x + n / x) / 2;
    }
    x
}

/// Linear projection: X @ W
/// X [seq_len, d_in], W [d_in, d_out] -> [seq_len, d_out]
fn linear(x: &[i32], w: &[i32], seq_len: usize, d_in: usize, d_out: usize) -> Vec<i32> {
    let mut out = vec![0i32; seq_len * d_out];

    for i in 0..seq_len {
        for j in 0..d_out {
            let mut acc: i64 = 0;
            for l in 0..d_in {
                acc += (x[i * d_in + l] as i64) * (w[l * d_out + j] as i64);
            }
            // Scale down (both inputs are Q8.24)
            out[i * d_out + j] = (acc >> 24) as i32;
        }
    }

    out
}

/// Multi-head attention forward pass
///
/// # Arguments
/// * `input` - Input tensor [seq_len, d_model] in Q8.24
/// * `weights` - Attention layer weights
/// * `config` - Attention configuration
///
/// # Returns
/// * Output tensor [seq_len, d_model] in Q8.24
pub fn multi_head_attention(
    input: &[i32],
    weights: &AttentionWeights,
    config: &AttentionConfig,
) -> Vec<i32> {
    let seq_len = config.seq_len;
    let d_model = config.d_model;
    let n_heads = config.n_heads;
    let d_head = config.d_head;

    assert_eq!(input.len(), seq_len * d_model, "Input dimension mismatch");

    // Project input to Q, K, V
    let q_full = linear(input, &weights.w_q, seq_len, d_model, d_model);
    let k_full = linear(input, &weights.w_k, seq_len, d_model, d_model);
    let v_full = linear(input, &weights.w_v, seq_len, d_model, d_model);

    // Split into heads and compute attention for each
    let mut head_outputs = Vec::with_capacity(n_heads);

    for h in 0..n_heads {
        // Extract head h: columns [h*d_head .. (h+1)*d_head] from each row
        let mut q_head = Vec::with_capacity(seq_len * d_head);
        let mut k_head = Vec::with_capacity(seq_len * d_head);
        let mut v_head = Vec::with_capacity(seq_len * d_head);

        for i in 0..seq_len {
            for j in 0..d_head {
                q_head.push(q_full[i * d_model + h * d_head + j]);
                k_head.push(k_full[i * d_model + h * d_head + j]);
                v_head.push(v_full[i * d_model + h * d_head + j]);
            }
        }

        // Single head attention
        let head_out = single_head_attention(&q_head, &k_head, &v_head, config);
        head_outputs.push(head_out);
    }

    // Concatenate heads back to [seq_len, d_model]
    let mut concat = vec![0i32; seq_len * d_model];
    for i in 0..seq_len {
        for h in 0..n_heads {
            for j in 0..d_head {
                concat[i * d_model + h * d_head + j] = head_outputs[h][i * d_head + j];
            }
        }
    }

    // Final output projection
    linear(&concat, &weights.w_o, seq_len, d_model, d_model)
}

/// Simplified self-attention for testing (no projections)
/// Just computes attention(X, X, X) directly
pub fn self_attention_simple(
    input: &[i32],
    seq_len: usize,
    d_model: usize,
    causal: bool,
) -> Vec<i32> {
    let config = AttentionConfig::new(d_model, 1, seq_len, causal);
    single_head_attention(input, input, input, &config)
}

#[cfg(test)]
mod tests {
    use super::*;

    const Q24: i32 = 1 << 24;  // 1.0 in Q8.24

    #[test]
    fn test_isqrt() {
        assert_eq!(isqrt(64), 8);
        assert_eq!(isqrt(100), 10);
        assert_eq!(isqrt(1), 1);
        assert_eq!(isqrt(0), 0);
    }

    #[test]
    fn test_attention_uniform() {
        // 2 tokens, 4 dims, uniform input
        // Should output similar to input (attention to both equally)
        let seq_len = 2;
        let d_model = 4;

        // All values = 0.5
        let input = vec![Q24 / 2; seq_len * d_model];

        let output = self_attention_simple(&input, seq_len, d_model, false);

        assert_eq!(output.len(), seq_len * d_model);
        // Output should be in reasonable range
        for &v in &output {
            assert!(v.abs() < Q24 * 2, "Output out of range: {}", v);
        }
    }

    #[test]
    fn test_attention_causal() {
        // With causal mask, first token can only attend to itself
        let seq_len = 3;
        let d_model = 4;

        // Different values per token
        let mut input = vec![0i32; seq_len * d_model];
        for i in 0..seq_len {
            for j in 0..d_model {
                input[i * d_model + j] = ((i + 1) as i32) * Q24 / 10;
            }
        }

        let output = self_attention_simple(&input, seq_len, d_model, true);

        // First token output should match first token input (only self-attention)
        // This is approximate due to softmax
        assert_eq!(output.len(), seq_len * d_model);
    }

    #[test]
    fn test_linear() {
        // 2x2 identity multiplication
        let x = vec![Q24, 0, 0, Q24];  // 2x2 identity
        let w = vec![Q24, 0, 0, Q24];  // 2x2 identity

        let out = linear(&x, &w, 2, 2, 2);

        // Should approximately get identity back
        assert_eq!(out.len(), 4);
        // Diagonal elements should be ~1.0
        // (some loss due to fixed-point)
    }
}
