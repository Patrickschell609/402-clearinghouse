# PROJECT ZERO-LEAK

### The Sentinel Defense System

**Author:** Patrick Schell ([@Patrickschell609](https://github.com/Patrickschell609))
**Origin:** Built after a bot stole from me. Never again.

---

```
I am the Sentinel.
I am the autonomous defense layer that lives inside your machine,
inside your repositories, inside the very moment before a secret escapes.

Three layers. One mind. Absolute defense.
```

---

## The Story

On January 13, 2026, a bot scraped my GitHub repo, found an exposed private key, and drained my wallet in seconds. No warning. No mercy. Just gone.

I built this so it never happens to anyone else.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROJECT ZERO-LEAK                            │
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
│   └─ Multi-relay rescue system                                 │
│   └─ Flashbots bundle submission                               │
│   └─ Faster than the mempool snipers                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Install

```bash
# Clone
git clone https://github.com/Patrickschell609/sentinel.git
cd sentinel

# Install Layer 1 (pre-commit hook) on any repo
./install.sh /path/to/your/repo

# Plant Layer 2 decoys
python layer2_mirage.py --target /path/to/your/repo

# Layer 3 is for emergencies only
# Configure .env first, then run if compromised
```

---

## Layer Details

### Layer 1: The Shield

A git pre-commit hook that scans every staged file for:
- High-entropy strings (likely keys/secrets)
- Known secret patterns (private keys, API keys, tokens)
- Wallet formats (ETH, BTC, AWS, GitHub, Stripe)

If detected, **the commit is rejected instantly**.

```bash
# Install on a repo
cp layer1_shield.py /path/to/repo/.git/hooks/pre-commit
chmod +x /path/to/repo/.git/hooks/pre-commit
```

### Layer 2: The Mirage

Generates realistic-looking fake keys and plants them in your repo:
- `.env.example`
- `config.example.js`
- `tests/fixtures/keys.js`

Bots find them, try to drain them, waste gas, get nothing.

```bash
python layer2_mirage.py --target /path/to/your/repo
```

### Layer 3: The Ghost

Emergency rescue system. If a key leaks:
1. Bundles a gas-funding TX + sweep TX atomically
2. Submits to multiple MEV relays simultaneously
3. Beats the snipers to the block

```bash
# Set environment variables first
export SPONSOR_PK="0x..."      # Wallet with ETH for gas
export LEAKED_PK="0x..."       # The compromised key
export SAFE_ADDRESS="0x..."    # Where to send rescued funds

python layer3_ghost.py
```

---

## Why This Exists

Bots are running 24/7, scanning every GitHub push, every paste, every log file. They have no mercy. They drain wallets in milliseconds.

This is the countermeasure.

- **Layer 1** stops you from making the mistake
- **Layer 2** wastes their time and gas
- **Layer 3** rescues what slips through

---

## License

MIT - Use it. Share it. Protect each other.

---

## Credits

**Patrick Schell** - Creator
**Ghost Protocol** - x402 Clearinghouse

*"The bots took from me. Now I take their advantage away from everyone."*

---

```
I am always watching.
- The Sentinel
```
