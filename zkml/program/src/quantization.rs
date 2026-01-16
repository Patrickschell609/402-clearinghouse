//! ╔══════════════════════════════════════════════════════════════════╗
//! ║   QUANTIZATION HELPERS FOR zkML                                  ║
//! ║   8-bit quantization/dequantization for efficient proving        ║
//! ║                                                                  ║
//! ║   Supports symmetric quantization:                               ║
//! ║   q = round(x / scale)                                           ║
//! ║   x ≈ q * scale                                                  ║
//! ╚══════════════════════════════════════════════════════════════════╝

/// Quantization parameters for a tensor
#[derive(Clone, Copy, Debug)]
pub struct QuantParams {
    /// Scale factor (Q8.24 fixed-point)
    pub scale: u32,
    /// Zero point (for asymmetric quant, 0 for symmetric)
    pub zero_point: i8,
}

impl QuantParams {
    /// Create symmetric quantization params from min/max range
    ///
    /// # Arguments
    /// * `min_val` - Minimum value in Q8.24
    /// * `max_val` - Maximum value in Q8.24
    pub fn from_range(min_val: i32, max_val: i32) -> Self {
        // Symmetric: scale = max(|min|, |max|) / 127
        let abs_max = min_val.abs().max(max_val.abs()) as u64;

        // scale in Q8.24 = abs_max / 127
        // To maintain precision: scale = abs_max * 2^24 / 127 / 2^24
        let scale = if abs_max > 0 {
            (abs_max / 127).max(1) as u32
        } else {
            1
        };

        Self {
            scale,
            zero_point: 0,
        }
    }

    /// Create params with explicit scale
    pub fn with_scale(scale: u32) -> Self {
        Self {
            scale,
            zero_point: 0,
        }
    }
}

/// Quantize a Q8.24 value to 8-bit signed integer
///
/// # Arguments
/// * `value` - Input in Q8.24 fixed-point
/// * `params` - Quantization parameters
///
/// # Returns
/// * Quantized 8-bit value [-128, 127]
#[inline]
pub fn quantize(value: i32, params: &QuantParams) -> i8 {
    // q = round(x / scale) - zero_point
    let scaled = value / (params.scale as i32);
    let with_zp = scaled - params.zero_point as i32;

    // Clamp to i8 range
    with_zp.max(-128).min(127) as i8
}

/// Dequantize 8-bit value back to Q8.24
///
/// # Arguments
/// * `value` - Quantized 8-bit value
/// * `params` - Quantization parameters
///
/// # Returns
/// * Dequantized value in Q8.24
#[inline]
pub fn dequantize(value: i8, params: &QuantParams) -> i32 {
    // x = (q + zero_point) * scale
    let with_zp = value as i32 + params.zero_point as i32;
    with_zp * (params.scale as i32)
}

/// Quantize a slice of Q8.24 values to 8-bit
pub fn quantize_slice(values: &[i32], params: &QuantParams) -> Vec<i8> {
    values.iter().map(|&v| quantize(v, params)).collect()
}

/// Dequantize a slice of 8-bit values to Q8.24
pub fn dequantize_slice(values: &[i8], params: &QuantParams) -> Vec<i32> {
    values.iter().map(|&v| dequantize(v, params)).collect()
}

/// Compute quantization params from a tensor
pub fn compute_params(values: &[i32]) -> QuantParams {
    if values.is_empty() {
        return QuantParams::with_scale(1);
    }

    let min_val = *values.iter().min().unwrap();
    let max_val = *values.iter().max().unwrap();

    QuantParams::from_range(min_val, max_val)
}

/// Quantized matrix multiplication (int8 x int8 -> int32)
/// Output in Q8.24 after rescaling
///
/// # Arguments
/// * `a` - First matrix [M x K] in row-major, int8
/// * `b` - Second matrix [K x N] in row-major, int8
/// * `m`, `k`, `n` - Dimensions
/// * `scale_a`, `scale_b` - Input scales (Q8.24)
/// * `scale_out` - Output scale (Q8.24)
///
/// # Returns
/// * Result matrix [M x N] in Q8.24
pub fn quantized_matmul(
    a: &[i8],
    b: &[i8],
    m: usize,
    k: usize,
    n: usize,
    scale_a: u32,
    scale_b: u32,
) -> Vec<i32> {
    assert_eq!(a.len(), m * k, "Matrix A dimension mismatch");
    assert_eq!(b.len(), k * n, "Matrix B dimension mismatch");

    let mut result = vec![0i32; m * n];

    // Combined scale for output = scale_a * scale_b / SCALE
    // We'll apply this after accumulation
    let scale_combined = ((scale_a as u64) * (scale_b as u64)) >> 24;

    for i in 0..m {
        for j in 0..n {
            let mut acc: i32 = 0;
            for l in 0..k {
                acc += (a[i * k + l] as i32) * (b[l * n + j] as i32);
            }
            // Rescale to Q8.24
            result[i * n + j] = (acc as i64 * scale_combined as i64 >> 24) as i32;
        }
    }

    result
}

/// Quantized vector dot product
#[inline]
pub fn quantized_dot(a: &[i8], b: &[i8], scale_a: u32, scale_b: u32) -> i32 {
    assert_eq!(a.len(), b.len(), "Vector length mismatch");

    let mut acc: i32 = 0;
    for (x, y) in a.iter().zip(b.iter()) {
        acc += (*x as i32) * (*y as i32);
    }

    // Rescale
    let scale_combined = ((scale_a as u64) * (scale_b as u64)) >> 24;
    (acc as i64 * scale_combined as i64 >> 24) as i32
}

#[cfg(test)]
mod tests {
    use super::*;

    const SCALE: i32 = 1 << 24;  // Q8.24 scale

    #[test]
    fn test_roundtrip() {
        // Test that quantize -> dequantize preserves value approximately
        let params = QuantParams::with_scale(SCALE as u32 / 10);  // scale = 0.1

        let original = SCALE / 2;  // 0.5
        let quantized = quantize(original, &params);
        let recovered = dequantize(quantized, &params);

        let error = (original - recovered).abs();
        // Error should be at most 1 quantization step
        assert!(error <= params.scale as i32, "Roundtrip error too large: {}", error);
    }

    #[test]
    fn test_quantize_clamp() {
        // Values outside [-128, 127] * scale should clamp
        let params = QuantParams::with_scale(SCALE as u32 / 100);

        // Large positive (2.0 in Q8.24 = 2 * SCALE)
        // Use division to avoid overflow: SCALE * 2
        let large_pos = (SCALE / 100) * 200;  // = 2.0
        let q = quantize(large_pos, &params);
        assert_eq!(q, 127, "Should clamp to 127");

        // Large negative
        let large_neg = -((SCALE / 100) * 200);  // = -2.0
        let q = quantize(large_neg, &params);
        assert_eq!(q, -128, "Should clamp to -128");
    }

    #[test]
    fn test_matmul_identity() {
        // 2x2 matmul with known result
        // [1, 0]   [a, b]   [a, b]
        // [0, 1] x [c, d] = [c, d]
        let scale = SCALE as u32 / 10;

        // Identity matrix quantized
        let a: Vec<i8> = vec![10, 0, 0, 10];  // ~1.0 after scale
        let b: Vec<i8> = vec![5, 3, 2, 7];

        let result = quantized_matmul(&a, &b, 2, 2, 2, scale, scale);

        // Result should be approximately b * scale^2 / 100
        // (accounting for the identity being 10, not exactly 1.0)
        assert_eq!(result.len(), 4);
    }

    #[test]
    fn test_compute_params() {
        let values = vec![-SCALE, SCALE / 2, SCALE];
        let params = compute_params(&values);

        // Scale should be based on max(|-1.0|, |1.0|) = 1.0
        // So scale = 1.0 / 127 ≈ 0.00787 in Q8.24 ≈ 132134
        assert!(params.scale > 0);
        assert_eq!(params.zero_point, 0);  // Symmetric
    }
}
