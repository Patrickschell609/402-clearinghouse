# First Public Transformer Attention zkML Verifier on Base

**Author:** Patrick Schell ([@Patrickschell609](https://github.com/Patrickschell609))
**Date:** January 15, 2026
**Contract:** [0xB1c0c4A25e037684Fdd5de7a41Cf556521032864](https://basescan.org/address/0xB1c0c4A25e037684Fdd5de7a41Cf556521032864)

---

## TL;DR

I deployed a smart contract that can verify zero-knowledge proofs of transformer attention computation—the same architecture that powers GPT-4, Claude, and every modern large language model. The proof is 260 bytes, costs $0.007 to verify on-chain, and reveals nothing about the model weights or input data.

This enables a new primitive: **Proof of Intelligence**—cryptographic verification that an AI agent ran a specific model on specific data and got a specific result, without revealing any of the private information.

---

## Why This Matters

### The Problem

AI agents are coming to DeFi. They'll trade, provide liquidity, manage portfolios, and make autonomous decisions with real money. But there's a fundamental trust problem:

**How do you verify an AI agent actually ran the model it claims to run?**

Without verification, an agent could:
- Claim to run a sophisticated trading model while actually front-running users
- Lie about its decision-making process
- Use a different (worse) model than advertised

### The Solution

Zero-knowledge proofs let us verify computation without revealing the inputs. If we can prove AI inference in ZK, we get:

1. **Strategy Binding**: Prove the agent used a specific model (identified by hash)
2. **Data Integrity**: Prove the model ran on valid input data
3. **Computation Proof**: Prove the model produced a specific output

All without revealing the model weights (proprietary) or input data (potentially sensitive).

---

## The Technical Challenge

Most zkML work focuses on simple models:
- Linear regression ✓ Easy
- Decision trees ✓ Manageable
- MLPs (feedforward networks) ✓ Done by several teams

But transformer attention is **hard**. The core formula:

```
Attention(Q,K,V) = softmax(QK^T / √d_k) × V
```

The killer is `softmax`, which requires computing `exp(x)` for each element:

```
softmax(x_i) = exp(x_i) / Σ exp(x_j)
```

Exponential functions are brutal in ZK circuits. They require either:
- Approximations (lose precision, security concerns)
- Massive constraint counts (impractical proving times)
- Lookup tables (the approach I took)

---

## The Implementation

### 1. Exp Lookup Table

Instead of computing `exp(x)` in the circuit, I precomputed 2^14 = 16,384 values:

```rust
// Domain: x ∈ [-10, 0] (after max subtraction, all values are ≤ 0)
// Resolution: 16384 entries
// Format: Q8.24 fixed-point

pub static EXP_TABLE: [u32; TABLE_SIZE] = [
    16777216,  // exp(0) = 1.0
    16776197,  // exp(-0.000610...)
    ...
    762,       // exp(-9.999...)
];
```

Linear interpolation between entries gives sufficient precision for attention weights.

### 2. Stable Softmax

Numerical stability via max subtraction:

```rust
pub fn softmax(inputs: &[i32]) -> Vec<u32> {
    // Find max for stability (prevents overflow)
    let max_val = *inputs.iter().max().unwrap();

    // exp(x - max) for each input
    let exp_vals: Vec<u32> = inputs.iter()
        .map(|&x| exp_lookup(x - max_val))
        .collect();

    // Normalize
    let sum: u64 = exp_vals.iter().sum();
    exp_vals.iter().map(|&e| e * SCALE / sum).collect()
}
```

### 3. Multi-Head Attention

Full transformer attention with:
- Q, K, V linear projections
- Split into multiple heads
- Scaled dot-product attention per head
- Causal masking (for autoregressive models)
- Concatenation and output projection

```rust
pub fn multi_head_attention(
    input: &[i32],           // [seq_len, d_model]
    weights: &AttentionWeights,
    config: &AttentionConfig,
) -> Vec<i32> {
    // Project to Q, K, V
    let q = linear(input, &weights.w_q, ...);
    let k = linear(input, &weights.w_k, ...);
    let v = linear(input, &weights.w_v, ...);

    // Attention per head
    for h in 0..n_heads {
        let head_out = single_head_attention(
            &q_head, &k_head, &v_head, config
        );
        // ...
    }

    // Output projection
    linear(&concat, &weights.w_o, ...)
}
```

### 4. Fixed-Point Arithmetic

Everything uses Q8.24 fixed-point (24 fractional bits):
- 1.0 = 16,777,216
- Precision: ~0.00000006
- Range: [-128, 128)

This avoids floating-point entirely, which is critical for deterministic ZK circuits.

### 5. The Circuit

The SP1 zkVM program:
1. Reads config, weights, and input as private inputs
2. Hashes weights → `model_hash` (proves which model)
3. Hashes input → `input_hash` (proves data integrity)
4. Runs attention → output
5. Hashes output → `output_hash` (proves computation)
6. Commits all hashes as public values

```rust
#![no_main]
use sp1_zkvm::entrypoint;

entrypoint!(main);

pub fn main() {
    // Read private inputs
    let config = read_config();
    let weights = read_weights();
    let input = read_input();

    // Hash model (strategy binding)
    let model_hash = sha256(&weights);

    // Hash input (data integrity)
    let input_hash = sha256(&input);

    // THE PROOF OF INTELLIGENCE
    let output = multi_head_attention(&input, &weights, &config);

    // Hash output (computation proof)
    let output_hash = sha256(&output);

    // Commit public values (96 bytes)
    commit(model_hash);
    commit(input_hash);
    commit(output_hash);
}
```

### 6. Groth16 Proof

SP1 compiles to RISC-V, executes the circuit, and generates a Groth16 proof:
- **Proof size**: 260 bytes (constant, regardless of circuit size)
- **Verification**: Single pairing check on-chain
- **Gas cost**: ~250,000 gas (~$0.007 on Base)

---

## Results

| Metric | Value |
|--------|-------|
| Proof Size | 260 bytes |
| Proving Time (CPU) | 37 minutes |
| Proving Time (GPU) | ~10 seconds (estimated) |
| Verification Cost | $0.007 |
| Circuit Parameters | d_model=16, n_heads=2, seq_len=4 |

The verification key:
```
0x007c7f386f0ccc16d2a18c3ef536e4c91b0839a2b91b5935ced528715ec581f6
```

This is permanently bound to the circuit. Any proof verified against this key guarantees the prover ran *this exact* transformer attention implementation.

---

## The Smart Contract

```solidity
contract AIGuardian {
    ISP1Verifier public immutable verifier;
    bytes32 public immutable programVKey;

    mapping(address => bytes32) public agentStrategies;

    function requestCreditWithProof(
        bytes calldata proof,
        bytes calldata publicValues
    ) external {
        // 1. Verify ZK proof
        verifier.verifyProof(programVKey, publicValues, proof);

        // 2. Extract public values
        bytes32 provedModelHash = ...;
        bytes32 provedDataHash = ...;
        int64 prediction = ...;

        // 3. Check strategy binding
        require(provedModelHash == agentStrategies[msg.sender]);

        // 4. Act on verified inference
        _issueCredit(msg.sender);
    }
}
```

---

## What's Next

### Scaling Up

The current implementation uses small dimensions (d_model=16) for tractable CPU proving. Production models use d_model=4096+. Scaling strategies:

1. **GPU Proving**: 100-1000x speedup over CPU
2. **Proof Aggregation**: Prove chunks, aggregate proofs
3. **Folding Schemes**: Nova/SuperNova for incremental proving
4. **Custom Circuits**: Move from general zkVM to optimized arithmetic circuits

### Applications

1. **Undercollateralized DeFi Lending**: Agents prove strategy quality for credit
2. **Verifiable AI Agents**: Prove an agent ran the advertised model
3. **Model Marketplaces**: Sell model access while keeping weights private
4. **Regulatory Compliance**: Prove AI decisions follow rules without revealing logic

---

## Code

All code is open source:

- **Circuit**: Multi-head attention in Rust, compiled to SP1 zkVM
- **Prover**: Host-side proof generation with Groth16 output
- **Contract**: Solidity verifier on Base mainnet

Repository: [github.com/Patrickschell609/x402-clearinghouse](https://github.com/Patrickschell609/x402-clearinghouse)

---

## Acknowledgments

Built with:
- [SP1](https://github.com/succinctlabs/sp1) - zkVM by Succinct Labs
- [Foundry](https://github.com/foundry-rs/foundry) - Ethereum development toolkit
- [Base](https://base.org) - L2 by Coinbase

---

## Contact

- Twitter: [@Patrickschell609](https://twitter.com/Patrickschell609)
- GitHub: [Patrickschell609](https://github.com/Patrickschell609)

---

*"The same architecture behind GPT and Claude—now provable on-chain without revealing weights or inputs."*
