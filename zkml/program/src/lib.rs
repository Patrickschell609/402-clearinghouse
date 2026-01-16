//! ╔══════════════════════════════════════════════════════════════════╗
//! ║   zkML Library — Transformer Components for SP1 zkVM            ║
//! ║                                                                  ║
//! ║   Modules:                                                       ║
//! ║   - exp_table: Lookup table for exp function                    ║
//! ║   - softmax: Stable softmax implementation                       ║
//! ║   - quantization: 8-bit quant/dequant helpers                   ║
//! ║   - attention: Multi-head attention layer                       ║
//! ║   - transformer: Full circuit integration                        ║
//! ╚══════════════════════════════════════════════════════════════════╝

pub mod exp_table;
pub mod softmax;
pub mod quantization;
pub mod attention;
pub mod transformer;

// Re-export commonly used items
pub use exp_table::{exp_lookup, SCALE, SCALE_BITS};
pub use softmax::{softmax, softmax_2d, softmax_masked};
pub use quantization::{quantize, dequantize, QuantParams};
pub use attention::{multi_head_attention, self_attention_simple, AttentionConfig, AttentionWeights};
pub use transformer::{TransformerConfig, TransformerWeights, TransformerInput, TransformerProof, run_transformer};
