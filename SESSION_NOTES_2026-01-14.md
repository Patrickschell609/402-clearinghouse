# x402 Clearinghouse - Session Notes
## January 14, 2026

**In case laptop freezes during Groth16 proof generation**

---

## WHAT WE ACCOMPLISHED TODAY

### 1. Fixed SP1 Dependency Hell
- SP1 4.0.0 had serde `__private` conflicts with alloy-consensus
- SP1 4.2.1 had scale-info/parity-scale-codec conflicts
- **Solution: Upgraded to SP1 5.2.4** - clean dependency tree

### 2. zkML Circuit Compiled Successfully
- Program (guest): `/home/python/Desktop/402infer/zkml/program/`
- Script (host): `/home/python/Desktop/402infer/zkml/script/`
- Both using SP1 5.2.4 + bincode 2.0 with serde feature

### 3. Got Real Verification Key
```
vKey: 0x000e06af799b753393857260c3d733044226ba93f7f4054700754be6d2878fb0
```
This is derived from the compiled circuit - it's permanent for this program.

### 4. Groth16 Proof Generation Started
Currently running on CPU. Will produce:
- Proof bytes (~260 bytes)
- Public values (72 bytes): model_hash + data_hash + prediction

---

## KEY FILES CHANGED

### program/Cargo.toml
```toml
[package]
name = "decision-tree-program"
version = "0.1.0"
edition = "2021"

[dependencies]
sp1-zkvm = "5.2.4"
bincode = { version = "2.0", features = ["serde"] }
serde = { version = "1.0", features = ["derive"] }
fixed = { version = "1.23", features = ["serde"] }
sha2 = "0.10"

[features]
default = []
```

### script/Cargo.toml
```toml
[package]
name = "zkml-prover"
version = "0.1.0"
edition = "2021"

[dependencies]
sp1-sdk = "5.2.4"
bincode = { version = "2.0", features = ["serde"] }
serde = { version = "1.0", features = ["derive"] }
fixed = { version = "1.23", features = ["serde"] }
hex = "0.4"
```

### Key code changes in script/src/main.rs
- `use sp1_sdk::{ProverClient, SP1Stdin, HashableKey};`
- ELF path: `include_bytes!("../../program/target/elf-compilation/riscv32im-succinct-zkvm-elf/release/decision-tree-program")`
- Using `.groth16()` for on-chain verifiable proofs
- bincode 2.0 API: `encode_to_vec(&model, config)` instead of `serialize(&model)`

### Key code changes in program/src/main.rs
- bincode 2.0 API: `decode_from_slice(&bytes, config)` instead of `deserialize(&bytes)`

---

## DEPLOYED CONTRACTS (Base Mainnet)

| Contract | Address |
|----------|---------|
| Clearinghouse402 | `0xb315C8F827e3834bB931986F177cb1fb6D20415D` |
| AgentRegistry | `0xB3aa5a6f3Cb37C252059C49E22E5DAB8b556a9aF` |
| AgentCreditLine | `0x790FA6e928c4D245C7b14De0265FCAa27D9e5F5D` |
| AIGuardian (REAL vKey) | `0x688f32d4Fa82B011b5A71C9a71401606200966ad` |
| AIGuardian (old, placeholder) | `0xbA51C66FCB68A5C17D7e0A9527f4F6335A76aeBE` |
| MockSP1Verifier | `0xDd2ffa97F680032332EA4905586e2366584Ae0be` |
| MockTBill | `0x0cB59FaA219b80D8FbFd28E9D37008f2db10F847A` |
| MockUSDC | `0x6020Ed65e0008242D9094D107D97dd17599dc21C` |

**Real Base USDC:** `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`

**Wallet:** `0xc7554F1B16ad0b3Ce363d53364C9817743E32f90`

---

## NEXT STEPS (after proof completes)

1. **Redeploy AIGuardian with real vKey**
   ```
   vKey: 0x000e06af799b753393857260c3d733044226ba93f7f4054700754be6d2878fb0
   ```

2. **Save proof output** - proof bytes and public values

3. **Test on-chain verification** - call `requestCreditWithProof()`

4. **For production proofs** - use GPU server (Anoblic etc.) for fast Groth16 generation

---

## HOW TO REBUILD FROM SCRATCH

```bash
# Update SP1 toolchain
export PATH="$HOME/.sp1/bin:$PATH"
sp1up --version 5.2.4

# Build program (circuit)
cd ~/Desktop/402infer/zkml/program
rm -rf Cargo.lock target
cargo prove build

# Build and run script (prover)
cd ~/Desktop/402infer/zkml/script
rm -rf Cargo.lock target
cargo build --release
cargo run --release
```

---

## SP1 TOOLCHAIN INFO

```
SP1 Version: 5.2.4
Rust (succinct): 1.91.1-dev
Installed via: sp1up --version 5.2.4
```

---

## PROOF GENERATION - COMPLETE

**Groth16 proof generated successfully!**

```
vKey: 0x000e06af799b753393857260c3d733044226ba93f7f4054700754be6d2878fb0
Proof Size: 260 bytes

Public Values (72 bytes):
  Model Hash: 34423cb539dde6206f8ec2a49a41e3ebcfa5db17b2751fe1e9ba51e6b574b33f
  Data Hash:  0358d864342481a49e3727796394b4ffdc6cd8206708593311fce3c13cbd0eb3
  Prediction: 0000000100000000 (= 1.0, BUY SIGNAL)
```

Runtime: ~75 minutes on CPU + ~15 minutes gnark Docker
Note: GPU server (Anoblic etc.) would do this in ~10 seconds

---

## CREDENTIALS (already in .env)

- BaseScan API Key: `J7A6U7YUA58YH25HXIP56BIESYBGMYXYDC`
- Private Key: In .env file

---

---

## DARK POOL NEGOTIATION (NEW)

Added dynamic price discovery via micro-negotiations.

**Files:**
- `negotiator.py` - Server-side pricing engine (desperation algorithm)
- `x402_client.py` - Agent haggling capability added

**Usage:**
```python
# Old way (fixed price)
agent.acquire_asset(server, "TBILL-26", 100)

# New way (negotiate)
agent.negotiate_and_acquire(server, "TBILL-26", 100, max_budget=97.00)
# or
agent.haggle(server, "TBILL-26", 100, max_budget=97.00)
```

**Server Integration:**
```python
from negotiator import PriceNegotiator, create_negotiation_routes
negotiator = PriceNegotiator(base_price=100, min_price=90)
create_negotiation_routes(app, negotiator)
```

**The Flow:**
1. Agent probes for initial quote
2. Agent lowballs (aggression factor)
3. Server evaluates based on inventory (desperation)
4. Counter-offer loop until ACCEPT/REJECT/WALK
5. Settlement at negotiated price

---

---

## REAL SETTLEMENT - COMPLETE

**First live transaction on Base mainnet with real USDC:**

```
TX: 0x626bd97f8c21916d5eab80b8be4ebd9e521b7cfa200cc2156f1c30ad2854c5a5
Block: 40826750
BaseScan: https://basescan.org/tx/626bd97f8c21916d5eab80b8be4ebd9e521b7cfa200cc2156f1c30ad2854c5a5
```

**All transactions today:**
- Strategy Registration: `0xe2ccf4722a0d95fa347ed7ae0102c9091e345f800a9d05be6fcfb84ebacd0ae0`
- USDC Approval: `0xb0b078e3586fcec654b33dbde7b66b4dd5b7976e97c8e5a85e3e770a2b072fea`
- TBILL Listing: `0xe65c34daa771c30364668b8c74793dc531b6e4b629e59b4c96dba34092cd2de3`
- TBILL Mint: `0x17c9f1c1b7391de644662b6f1a9c76ae7b62dff9e60b2742b8115887940d1acb`
- TBILL Approval: `0xa48ed68c36de815e80cf093fee8bfecf7e7b2b74d5afba00089fd91c751c13af`
- **LIVE SETTLEMENT: `0x626bd97f8c21916d5eab80b8be4ebd9e521b7cfa200cc2156f1c30ad2854c5a5`**

---

**Author: Patrick Schell (@Patrickschell609)**
**Session with Claude Opus 4.5**
