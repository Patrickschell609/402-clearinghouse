//! ╔══════════════════════════════════════════════════════════════════╗
//! ║   STABLE SOFTMAX FOR zkML                                        ║
//! ║   Uses table lookup for exp computation                          ║
//! ║                                                                  ║
//! ║   softmax(x_i) = exp(x_i - max(x)) / sum(exp(x_j - max(x)))     ║
//! ╚══════════════════════════════════════════════════════════════════╝

use crate::exp_table::{exp_lookup, SCALE, X_MIN_SCALED};

/// Compute softmax over a slice of Q8.24 fixed-point values
///
/// # Arguments
/// * `inputs` - Slice of i32 values in Q8.24 format
///
/// # Returns
/// * Vector of softmax outputs in Q8.24 format (sum to SCALE)
pub fn softmax(inputs: &[i32]) -> Vec<u32> {
    if inputs.is_empty() {
        return vec![];
    }

    // Step 1: Find max for numerical stability
    let max_val = *inputs.iter().max().unwrap();

    // Step 2: Compute exp(x_i - max) for each input
    let mut exp_vals: Vec<u32> = Vec::with_capacity(inputs.len());
    let mut sum: u64 = 0;

    for &x in inputs {
        // x - max (in Q8.24)
        let shifted = x - max_val;

        // Clamp to table range (should already be in range due to max subtraction)
        let clamped = shifted.max(X_MIN_SCALED).min(0);

        // Lookup exp
        let exp_val = exp_lookup(clamped);
        exp_vals.push(exp_val);
        sum += exp_val as u64;
    }

    // Step 3: Normalize (divide by sum)
    // result_i = exp_i * SCALE / sum
    let result: Vec<u32> = exp_vals
        .iter()
        .map(|&e| {
            // Multiply by SCALE first to maintain precision
            let numerator = (e as u64) * (SCALE as u64);
            (numerator / sum) as u32
        })
        .collect();

    result
}

/// Softmax for attention scores (2D: [seq_len, seq_len])
/// Applies softmax row-wise (each query attends to all keys)
///
/// # Arguments
/// * `scores` - Flattened attention scores [seq_len * seq_len] in Q8.24
/// * `seq_len` - Sequence length
///
/// # Returns
/// * Attention weights [seq_len * seq_len] in Q8.24
pub fn softmax_2d(scores: &[i32], seq_len: usize) -> Vec<u32> {
    let mut result = Vec::with_capacity(scores.len());

    for row_idx in 0..seq_len {
        let start = row_idx * seq_len;
        let end = start + seq_len;
        let row = &scores[start..end];

        let row_softmax = softmax(row);
        result.extend(row_softmax);
    }

    result
}

/// Compute softmax with masking for causal attention
/// Masked positions get attention weight 0
///
/// # Arguments
/// * `scores` - Attention scores [seq_len * seq_len] in Q8.24
/// * `seq_len` - Sequence length
/// * `causal` - If true, apply causal mask (can only attend to past)
///
/// # Returns
/// * Masked attention weights [seq_len * seq_len] in Q8.24
pub fn softmax_masked(scores: &[i32], seq_len: usize, causal: bool) -> Vec<u32> {
    if !causal {
        return softmax_2d(scores, seq_len);
    }

    let mut result = Vec::with_capacity(scores.len());

    for row_idx in 0..seq_len {
        let start = row_idx * seq_len;

        // For causal: only attend to positions 0..=row_idx
        // This is the "can only see past tokens" constraint
        let valid_len = row_idx + 1;
        let row = &scores[start..start + valid_len];

        // Softmax over valid positions only
        let row_softmax = softmax(row);

        // Pad with zeros for masked positions
        result.extend(row_softmax);
        for _ in valid_len..seq_len {
            result.push(0);
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_softmax_uniform() {
        // Equal inputs -> uniform distribution
        let inputs = vec![0i32; 4];  // [0, 0, 0, 0] in Q8.24
        let result = softmax(&inputs);

        // Each should be SCALE / 4 = 4194304
        let expected = SCALE / 4;
        for &r in &result {
            let error = (r as i64 - expected as i64).abs();
            assert!(error < 100, "Uniform softmax error: {}", error);
        }
    }

    #[test]
    fn test_softmax_dominant() {
        // One large value should dominate
        let scale = SCALE as i32;
        // Use -10 to make exp(-10) very small
        let inputs = vec![0, -10 * scale, -10 * scale, -10 * scale];
        let result = softmax(&inputs);

        // First should be close to SCALE (1.0)
        // exp(0) / (exp(0) + 3*exp(-10)) ≈ 1 / (1 + 3*0.0000454) ≈ 0.99986
        assert!(result[0] > (SCALE * 99 / 100), "Dominant value should be ~1.0, got {}", result[0]);

        // Others should be near 0
        for &r in &result[1..] {
            assert!(r < (SCALE / 100), "Non-dominant should be ~0, got {}", r);
        }
    }

    #[test]
    fn test_softmax_sums_to_one() {
        let scale = SCALE as i32;
        let inputs = vec![0, -scale, -2 * scale, -3 * scale];
        let result = softmax(&inputs);

        let sum: u64 = result.iter().map(|&x| x as u64).sum();
        let error = (sum as i64 - SCALE as i64).abs();
        assert!(error < 1000, "Softmax should sum to SCALE, error: {}", error);
    }

    #[test]
    fn test_softmax_2d() {
        // 2x2 attention
        let scale = SCALE as i32;
        let scores = vec![0, -scale, -scale, 0];  // 2x2 matrix
        let result = softmax_2d(&scores, 2);

        // Each row should sum to ~SCALE
        let row0_sum: u64 = result[0..2].iter().map(|&x| x as u64).sum();
        let row1_sum: u64 = result[2..4].iter().map(|&x| x as u64).sum();

        assert!((row0_sum as i64 - SCALE as i64).abs() < 1000);
        assert!((row1_sum as i64 - SCALE as i64).abs() < 1000);
    }

    #[test]
    fn test_causal_mask() {
        // 3x3 causal attention
        let scores = vec![0i32; 9];  // 3x3 zeros
        let result = softmax_masked(&scores, 3, true);

        // Row 0: only position 0 visible -> [1.0, 0, 0]
        assert!(result[0] > SCALE - 100);
        assert_eq!(result[1], 0);
        assert_eq!(result[2], 0);

        // Row 1: positions 0,1 visible -> [0.5, 0.5, 0]
        let half = SCALE / 2;
        assert!((result[3] as i64 - half as i64).abs() < 100);
        assert!((result[4] as i64 - half as i64).abs() < 100);
        assert_eq!(result[5], 0);

        // Row 2: all visible -> [0.33, 0.33, 0.33]
        let third = SCALE / 3;
        for &r in &result[6..9] {
            assert!((r as i64 - third as i64).abs() < 1000);
        }
    }
}
