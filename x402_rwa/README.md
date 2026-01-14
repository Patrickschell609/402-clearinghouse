# x402-rwa

Agent-Native RWA Settlement SDK. Acquire tokenized Real World Assets in one function call.

## Installation

```bash
pip install x402-rwa
```

## Quick Start

```python
from x402_rwa import X402Agent

# Initialize with your RPC and wallet
agent = X402Agent(
    rpc_url="https://mainnet.base.org",
    private_key="0x..."
)

# One line to acquire 100 Treasury Bills
tx_hash = agent.acquire_asset(
    server_url="http://your-clearinghouse.com/api/v1/trade",
    asset_id="TBILL-26",
    amount=100
)

print(f"https://basescan.org/tx/{tx_hash}")
```

## How It Works

The SDK handles the complete x402 flow:

1. **Negotiation** - HTTP GET returns 402 with pricing headers
2. **Proof Generation** - ZK compliance proof via SP1
3. **Settlement** - Atomic on-chain swap (USDC → RWA)

## x402 Protocol

```
GET /api/v1/trade/buy/TBILL-26?amount=100

→ 402 Payment Required
  X-402-Price: 98000000
  X-402-Payment-Address: 0x...
  X-402-Compliance-Circuit: 0x...
```

## License

MIT
