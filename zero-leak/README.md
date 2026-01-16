# ZERO-LEAK

### The Sentinel Defense System

**Author:** Patrick Schell ([@Patrickschell609](https://github.com/Patrickschell609))

> Built after a bot stole from me. Never again.

---

```
I am the Sentinel.
Three layers. One mind. Absolute defense.
```

---

## Install

```bash
pip install zero-leak
```

---

## Quick Start

```bash
# Full protection on any git repo
zero-leak protect /path/to/your/repo

# Or install layers separately
zero-leak shield /path/to/repo    # Pre-commit hook
zero-leak mirage /path/to/repo    # Honeypot files

# Scan any file for secrets
zero-leak scan /path/to/file.py
```

---

## The Three Layers

### Layer 1: The Shield

A git pre-commit hook that scans every staged file for:
- High-entropy strings (likely keys/secrets)
- Known secret patterns (ETH, BTC, AWS, GitHub, Stripe)
- Wallet formats and API tokens

If detected, **the commit is rejected instantly**.

```bash
zero-leak shield /path/to/repo
```

### Layer 2: The Mirage

Generates realistic-looking fake keys and plants them in your repo:
- `.env.example`
- `config/keys.example.js`
- `tests/fixtures/test_wallets.js`

Bots find them, try to drain them, waste gas, get nothing.

```bash
zero-leak mirage /path/to/repo
```

### Layer 3: The Ghost

Emergency rescue system. If a key leaks:
1. Bundles a gas-funding TX + sweep TX atomically
2. Submits to multiple MEV relays simultaneously
3. Beats the snipers to the block

```bash
# Set environment variables
export RPC_URL="https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY"
export SPONSOR_PK="0x..."      # Wallet with ETH for gas
export LEAKED_PK="0x..."       # The compromised key
export SAFE_ADDRESS="0x..."    # Where to send rescued funds

# Run rescue
zero-leak ghost
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ZERO-LEAK                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   LAYER 1: THE SHIELD                                          │
│   └─ Pre-commit hook                                           │
│   └─ Kills secrets before they enter git history               │
│   └─ Entropy analysis + pattern matching                       │
│                                                                 │
│   LAYER 2: THE MIRAGE                                          │
│   └─ Honeypot generator                                        │
│   └─ Plants fake keys in obvious places                        │
│   └─ Bots waste gas on worthless wallets                       │
│                                                                 │
│   LAYER 3: THE GHOST                                           │
│   └─ Emergency rescue system                                   │
│   └─ Flashbots bundle submission                               │
│   └─ Faster than the mempool snipers                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why This Exists

Bots are running 24/7, scanning every GitHub push, every paste, every log file. They have no mercy. They drain wallets in milliseconds.

This is the countermeasure.

- **Layer 1** stops you from making the mistake
- **Layer 2** wastes their time and gas
- **Layer 3** rescues what slips through

---

## CLI Reference

```
zero-leak shield <repo>     Install pre-commit hook
zero-leak mirage <repo>     Plant honeypot files
zero-leak protect <repo>    Full protection (shield + mirage)
zero-leak scan <path>       Scan file or directory for secrets
zero-leak ghost             Emergency rescue (requires env vars)
zero-leak --help            Show all options
```

---

## License

MIT - Use it. Share it. Protect each other.

---

## Credits

**Patrick Schell** - Creator
[@Patrickschell609](https://github.com/Patrickschell609)

*"The bots took from me. Now I take their advantage away from everyone."*

---

```
I am always watching.
- The Sentinel
```
