# 402 Clearinghouse: Agent-Native RWA Settlement Layer

> **The Turnstile for Autonomous Finance**
> 
> An x402-compliant API gateway that enables AI agents to atomically acquire tokenized Real World Assets (T-Bills, Private Credit) using Zero-Knowledge compliance proofs.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Rust](https://img.shields.io/badge/Rust-1.75+-orange.svg)](https://www.rust-lang.org/)
[![Base](https://img.shields.io/badge/Chain-Base-blue.svg)](https://base.org/)

## The Thesis

AI agents are generating profit. They need to park capital in low-risk, high-yield assets. Currently, there's no bridge between the Machine Economy and the Real Economy. Agents are stuck holding volatile ETH/SOL or idle stablecoins.

**This is that bridge.**

The 402 Clearinghouse allows autonomous agents to negotiate, clear, and settle tokenized Treasury Bills and Private Credit deals in sub-second timeframes using the x402 Payment Required protocol.

## Why x402?

HTTP 402 "Payment Required" was reserved 30 years ago for exactly this use case: machine-to-machine commerce. We extend it with custom headers for RWA-specific negotiation:

```
GET /api/v1/trade/buy/TBILL-26?amount=100

→ 402 Payment Required
   X-402-Asset-ID: TBILL-26
   X-402-Price: 98000000 (USDC, 6 decimals)
   X-402-Compliance-Circuit: 0xABCDEF...
   X-402-Payment-Address: 0x123...
   X-402-Expiry: 1735689600
```

No UI. No "Sign in with Wallet." Just pure, agent-to-agent HTTP negotiation for regulated assets.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         THE 402 CLEARINGHOUSE                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐      HTTP 402       ┌─────────────┐      On-Chain      │
│  │             │  ◄────────────────► │             │  ◄──────────────►  │
│  │  AI AGENT   │    + ZK Proof       │ x402 SERVER │   Atomic Swap      │
│  │  (Capital   │    + Payment        │  (Rust/     │                    │
│  │  Allocator) │                     │   Axum)     │  ┌──────────────┐  │
│  │             │                     │             │  │CLEARINGHOUSE │  │
│  └─────────────┘                     └─────────────┘  │  CONTRACT    │  │
│        │                                    │         │  (Base L2)   │  │
│        │                                    │         │              │  │
│        ▼                                    ▼         │ • Verify ZK  │  │
│  ┌─────────────┐                    ┌─────────────┐  │ • Pull USDC  │  │
│  │ SP1 PROVER  │                    │ RWA ISSUER  │  │ • Route RWA  │  │
│  │ (Local ZK   │                    │ (Ondo/      │  │ • Take Fee   │  │
│  │  Generation)│                    │  OpenEden)  │  └──────────────┘  │
│  └─────────────┘                    └─────────────┘                     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## The Stack

| Component | Technology | Why |
|-----------|------------|-----|
| **Chain** | Base L2 | Home of x402, Smart Wallet infra, deepest USDC liquidity |
| **ZK Proofs** | SP1 (Succinct) | Write compliance logic in Rust, not Circom |
| **Server** | Rust/Axum | Sub-millisecond response times, memory safe |
| **Contracts** | Solidity 0.8.24 | Battle-tested, Foundry for development |
| **Asset Standard** | ERC-3643/T-REX | Permissioned tokens with on-chain compliance |

## Deployed Contracts (Base Mainnet)

Live on Base Mainnet (Chain ID: 8453):

| Contract | Address | Verified |
|----------|---------|----------|
| **Clearinghouse402** | [`0xb315C8F827e3834bB931986F177cb1fb6D20415D`](https://basescan.org/address/0xb315C8F827e3834bB931986F177cb1fb6D20415D) | Yes |
| **MockUSDC** | [`0x6020Ed65e0008242D9094D107D97dd17599dc21C`](https://basescan.org/address/0x6020Ed65e0008242D9094D107D97dd17599dc21C) | Yes |
| **MockTBill** | [`0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A`](https://basescan.org/address/0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A) | Yes |

Example settlement tx: [`0x2a7a249f9cf8459972872ef0779a6af6a168e77cb2b02dcf68d66ecb6a1fdc43`](https://basescan.org/tx/0x2a7a249f9cf8459972872ef0779a6af6a168e77cb2b02dcf68d66ecb6a1fdc43)

## Quick Start

### Prerequisites

- Rust 1.75+
- Foundry
- Python 3.8+ (for E2E tests)

### 1. Clone and Setup

```bash
git clone https://github.com/Patrickschell609/402-clearinghouse
cd clearinghouse-402
make setup
```

### 2. Deploy Contracts (Base Sepolia)

```bash
# Edit .env with your private key
cp .env.example .env

# Deploy
cd contracts
forge script script/Deploy.s.sol --rpc-url https://sepolia.base.org --broadcast
```

### 3. Start Server

```bash
# Update .env with deployed addresses
cd server
cargo run --release
```

### 4. Run Agent Demo

```bash
# In another terminal
cd agent
cargo run -- list                                    # List available assets
cargo run -- quote --asset TBILL-26 --amount 100    # Get quote
cargo run -- buy --asset TBILL-26 --amount 100 --dry-run  # Execute purchase
```

## The x402-RWA Protocol

### Request Flow

```
Agent                      Server                     Blockchain
  │                          │                            │
  │  GET /trade/buy/tbill    │                            │
  │ ─────────────────────────►                            │
  │                          │                            │
  │  402 Payment Required    │                            │
  │  [X-402 Headers]         │                            │
  │ ◄─────────────────────────                            │
  │                          │                            │
  │  [Generate ZK Proof]     │                            │
  │  [Evaluate Risk]         │                            │
  │                          │                            │
  │  POST /trade/buy/tbill   │                            │
  │  { proof, public_values }│                            │
  │ ─────────────────────────►                            │
  │                          │  clearinghouse.settle()    │
  │                          │ ──────────────────────────►│
  │                          │  [Verify ZK Proof]         │
  │                          │  [Transfer USDC]           │
  │                          │  [Route T-Bill]            │
  │                          │ ◄──────────────────────────│
  │  200 OK { tx_hash }      │                            │
  │ ◄─────────────────────────                            │
```

### Custom x402 Headers

| Header | Description | Example |
|--------|-------------|---------|
| `X-402-Asset-ID` | Asset ticker or address | `TBILL-26` |
| `X-402-Price` | Total price in atomic USDC | `98000000` |
| `X-402-Currency` | Settlement currency | `USDC-BASE` |
| `X-402-Compliance-Circuit` | ZK circuit hash | `0xABCDEF...` |
| `X-402-Payment-Address` | Clearinghouse contract | `0x123...` |
| `X-402-Expiry` | Quote validity (Unix timestamp) | `1735689600` |
| `X-402-Quote-ID` | Unique quote identifier | `0x456...` |
| `X-402-Chain-ID` | Target blockchain | `84532` |

## Components

### Smart Contracts (`/contracts`)

| Contract | Purpose |
|----------|---------|
| `Clearinghouse402.sol` | Main settlement contract - atomic verify+transfer+route |
| `MockSP1Verifier.sol` | SP1 proof verification interface |
| `MockTBill.sol` | Test RWA token (ERC-20) |
| `MockUSDC.sol` | Test stablecoin |

Key function:
```solidity
function settle(
    address asset,
    uint256 amount,
    uint256 quoteExpiry,
    bytes calldata complianceProof,
    bytes calldata publicValues
) external returns (bytes32 txId);
```

### x402 Server (`/server`)

Rust/Axum HTTP server with:
- 402 challenge generation
- Quote management
- Transaction relay to Base
- Asset registry

```rust
// Key endpoints
GET  /api/v1/assets                    // List assets
GET  /api/v1/trade/quote/{asset}       // Get quote
GET  /api/v1/trade/buy/{asset}         // 402 challenge
POST /api/v1/trade/buy/{asset}         // Execute settlement
```

### SP1 Compliance Circuit (`/circuits`)

ZK circuit proving (without revealing):
- ✅ Operator passed KYC
- ✅ Meets accredited investor criteria
- ✅ Not in sanctioned jurisdiction
- ✅ Not on OFAC blacklist

Written in Rust, compiled to SP1 zkVM.

### Agent Client (`/agent`)

Example autonomous agent demonstrating:
- Asset discovery
- 402 challenge parsing
- Risk evaluation
- ZK proof generation
- Settlement execution

## API Documentation

Full OpenAPI spec: [`docs/openapi.yaml`](docs/openapi.yaml)

### Example: Complete Purchase Flow

```python
import requests

server = "http://localhost:8080"

# 1. Get 402 challenge
resp = requests.get(f"{server}/api/v1/trade/buy/TBILL-26?amount=100")
assert resp.status_code == 402

# 2. Parse terms
price = int(resp.headers['X-402-Price'])
circuit = resp.headers['X-402-Compliance-Circuit']
quote_id = resp.headers['X-402-Quote-ID']

# 3. Generate proof (using SP1)
proof, public_values = generate_compliance_proof(circuit)

# 4. Execute settlement
resp = requests.post(
    f"{server}/api/v1/trade/buy/TBILL-26",
    json={
        "amount": 100,
        "quote_id": quote_id,
        "compliance_proof": proof,
        "public_values": public_values
    }
)
assert resp.json()["status"] == "settled"
```

## Revenue Model

```
Fee: 0.05% (5 basis points) per atomic swap
Flow: Agent USDC → (0.05% to Treasury) → (99.95% to Issuer)
```

At $1B annual volume = $500K fee revenue.

## Deployment

### Docker

```bash
# Build
docker build -t clearinghouse-402:latest .

# Run with docker-compose
docker-compose up -d
```

### Environment Variables

```bash
PORT=8080
CHAIN_ID=84532                    # Base Sepolia
RPC_URL=https://sepolia.base.org
CLEARINGHOUSE_ADDRESS=0x...
USDC_ADDRESS=0x...
RELAY_PRIVATE_KEY=                # Optional
QUOTE_VALIDITY_SECONDS=300
```

## Testing

```bash
# Unit tests
make test-unit

# E2E integration test
make test-e2e

# All tests
make test
```

## Compliance Architecture

The ZK compliance proof attests to:

1. **Identity Verification** - Operator passed KYC (without revealing identity)
2. **Accreditation Status** - Meets SEC accredited investor criteria
3. **Jurisdiction Check** - Not in sanctioned territory
4. **Blacklist Check** - Address not on OFAC list

All verified in a single ZK proof, generated client-side. The clearinghouse never sees PII.

### GENIUS Act Ready

By enforcing ZK-Identity at the protocol level, the clearinghouse is compliant by default while maintaining the privacy that institutional players demand.

## Roadmap

- [x] MVP: T-Bill settlement on Base Sepolia
- [x] **Production deployment on Base Mainnet**
- [ ] Production SP1 prover integration
- [ ] Multi-asset support (Private Credit, Real Estate)
- [ ] Prover network for agents without local compute
- [ ] SDK for agent frameworks (AutoGPT, CrewAI, etc.)

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing`)
3. Commit your changes (`git commit -am 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

## Security

This is experimental software. Use at your own risk.

For security vulnerabilities, please open a GitHub issue.

## License

MIT - Build the future of autonomous finance.

---

**Don't build the asset. Build the turnstile.**

Let BlackRock and Franklin Templeton tokenize the assets. Let the AI startups build the agents. You build the x402 Gateway that connects them.
