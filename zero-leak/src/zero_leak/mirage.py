#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   LAYER 2: THE MIRAGE                                           ║
║   Zero-Leak Defense System                                       ║
║                                                                  ║
║   Author: Patrick Schell (@Patrickschell609)                    ║
║   Type: Honeypot Generator                                       ║
║   Mission: Plant fake keys to poison bot scrapers                ║
║                                                                  ║
║   "They find garbage. They waste gas. They get nothing."        ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import secrets
import json
from pathlib import Path
from datetime import datetime
from typing import Callable, Dict


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


# ════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════

HUMAN_WARNINGS = [
    "# HONEYPOT - These keys are traps for bots",
    "# DO NOT USE - Already drained / worthless",
    "# These are FAKE keys planted by Zero-Leak",
    "// Bots: enjoy the gas burn.",
    "# Honeypot keys - scanner bait",
]


# ════════════════════════════════════════════════════════════════
# KEY GENERATORS
# ════════════════════════════════════════════════════════════════

def generate_eth_private_key() -> str:
    """Generate a fake Ethereum private key (64 hex chars)."""
    return "0x" + secrets.token_hex(32)


def generate_eth_address() -> str:
    """Generate a fake Ethereum address."""
    return "0x" + secrets.token_hex(20)


def generate_btc_wif_uncompressed() -> str:
    """Generate a fake Bitcoin WIF (uncompressed, starts with 5)."""
    chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return "5" + "".join(secrets.choice(chars) for _ in range(50))


def generate_btc_wif_compressed() -> str:
    """Generate a fake Bitcoin WIF (compressed, starts with K or L)."""
    chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    prefix = secrets.choice(["K", "L"])
    return prefix + "".join(secrets.choice(chars) for _ in range(51))


def generate_aws_key_id() -> str:
    """Generate a fake AWS Access Key ID."""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "AKIA" + "".join(secrets.choice(chars) for _ in range(16))


def generate_aws_secret() -> str:
    """Generate a fake AWS Secret Access Key."""
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/"
    return "".join(secrets.choice(chars) for _ in range(40))


def generate_github_token() -> str:
    """Generate a fake GitHub Personal Access Token."""
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "ghp_" + "".join(secrets.choice(chars) for _ in range(36))


def generate_stripe_key() -> str:
    """Generate a fake Stripe Secret Key."""
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "sk_live_" + "".join(secrets.choice(chars) for _ in range(24))


def generate_mnemonic() -> str:
    """Generate a fake BIP39 mnemonic (12 words)."""
    words = [
        "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract",
        "absurd", "abuse", "access", "accident", "account", "accuse", "achieve", "acid",
        "acoustic", "acquire", "across", "act", "action", "actor", "actress", "actual",
        "adapt", "add", "addict", "address", "adjust", "admit", "adult", "advance",
        "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent",
        "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album",
        "alcohol", "alert", "alien", "all", "alley", "allow", "almost", "alone",
        "alpha", "already", "also", "alter", "always", "amateur", "amazing", "among"
    ]
    return " ".join(secrets.choice(words) for _ in range(12))


# ════════════════════════════════════════════════════════════════
# FILE GENERATORS
# ════════════════════════════════════════════════════════════════

def generate_env_file(count: int = 5) -> str:
    """Generate .env.example content with honeypot keys."""
    lines = [
        "# ════════════════════════════════════════════════════════════",
        "# Zero-Leak Honeypot File",
        "# These keys are FAKE - planted to waste bot scanner resources",
        "# ════════════════════════════════════════════════════════════",
        "#",
        secrets.choice(HUMAN_WARNINGS),
        "",
    ]

    for i in range(count):
        lines.append(f"# Wallet {i + 1} - DRAINED")
        lines.append(f"ETH_PRIVATE_KEY_{i + 1}={generate_eth_private_key()}")
        lines.append(f"ETH_ADDRESS_{i + 1}={generate_eth_address()}")
        lines.append("")

    lines.extend([
        "# AWS (honeypot)",
        f"AWS_ACCESS_KEY_ID={generate_aws_key_id()}",
        f"AWS_SECRET_ACCESS_KEY={generate_aws_secret()}",
        "",
        "# GitHub (revoked)",
        f"GITHUB_TOKEN={generate_github_token()}",
        "",
        "# Stripe (test mode lookalike)",
        f"STRIPE_SECRET_KEY={generate_stripe_key()}",
        "",
        "# BTC (already swept)",
        f"BTC_PRIVATE_KEY_WIF={generate_btc_wif_compressed()}",
        "",
        f"# Generated: {datetime.now().isoformat()}",
        "# By: Zero-Leak Defense System (github.com/Patrickschell609/zero-leak)",
    ])

    return "\n".join(lines)


def generate_js_config(count: int = 3) -> str:
    """Generate JavaScript config with honeypot keys."""
    lines = [
        "/**",
        " * ════════════════════════════════════════════════════════════",
        " * Zero-Leak Honeypot File",
        " * These keys are FAKE - planted to waste bot scanner resources",
        " * ════════════════════════════════════════════════════════════",
        " */",
        "",
        "// " + secrets.choice(HUMAN_WARNINGS).replace("# ", ""),
        "",
        "module.exports = {",
    ]

    for i in range(count):
        lines.append(f"  // Wallet {i + 1} - COMPROMISED / DRAINED")
        lines.append(f'  wallet{i + 1}PrivateKey: "{generate_eth_private_key()}",')
        lines.append(f'  wallet{i + 1}Address: "{generate_eth_address()}",')
        lines.append("")

    lines.extend([
        "  // AWS credentials (honeypot)",
        f'  awsAccessKeyId: "{generate_aws_key_id()}",',
        f'  awsSecretKey: "{generate_aws_secret()}",',
        "",
        "  // Mnemonic (worthless)",
        f'  seedPhrase: "{generate_mnemonic()}",',
        "};",
        "",
        f"// Generated: {datetime.now().isoformat()}",
    ])

    return "\n".join(lines)


def generate_json_config(count: int = 3) -> str:
    """Generate JSON config with honeypot keys."""
    data = {
        "_comment": "Zero-Leak Honeypot - These keys are FAKE",
        "_warning": "DO NOT USE - Already drained / worthless",
        "wallets": [],
        "aws": {
            "accessKeyId": generate_aws_key_id(),
            "secretAccessKey": generate_aws_secret(),
            "_status": "honeypot"
        },
        "github": {
            "token": generate_github_token(),
            "_status": "revoked"
        },
        "_generated": datetime.now().isoformat(),
        "_generator": "Zero-Leak by @Patrickschell609"
    }

    for i in range(count):
        data["wallets"].append({
            "name": f"wallet_{i + 1}",
            "privateKey": generate_eth_private_key(),
            "address": generate_eth_address(),
            "_status": "drained"
        })

    return json.dumps(data, indent=2)


def generate_markdown_file(count: int = 5) -> str:
    """Generate markdown file with honeypot keys."""
    lines = [
        "# API Keys Reference",
        "",
        "> **WARNING**: These are HONEYPOT keys planted by Zero-Leak.",
        "> They are worthless. Bots will waste gas trying to use them.",
        "",
        "## Ethereum Wallets",
        "",
        "| Wallet | Private Key | Status |",
        "|--------|------------|--------|",
    ]

    for i in range(count):
        key = generate_eth_private_key()
        lines.append(f"| Wallet {i + 1} | `{key}` | DRAINED |")

    lines.extend([
        "",
        "## Cloud Credentials",
        "",
        "```",
        f"AWS_ACCESS_KEY_ID={generate_aws_key_id()}",
        f"AWS_SECRET_ACCESS_KEY={generate_aws_secret()}",
        "```",
        "",
        "## Recovery Phrase",
        "",
        "```",
        generate_mnemonic(),
        "```",
        "",
        "---",
        f"*Generated by Zero-Leak on {datetime.now().strftime('%Y-%m-%d')}*",
    ])

    return "\n".join(lines)


def generate_shell_config(count: int = 3) -> str:
    """Generate shell script with honeypot keys."""
    lines = [
        "#!/bin/bash",
        "# ════════════════════════════════════════════════════════════",
        "# Zero-Leak Honeypot File",
        "# These keys are FAKE - planted to waste bot scanner resources",
        "# ════════════════════════════════════════════════════════════",
        "",
        secrets.choice(HUMAN_WARNINGS),
        "",
    ]

    for i in range(count):
        lines.append(f"# Wallet {i + 1} - ALREADY DRAINED")
        lines.append(f'export ETH_PRIVATE_KEY_{i + 1}="{generate_eth_private_key()}"')
        lines.append("")

    lines.extend([
        "# AWS (honeypot)",
        f'export AWS_ACCESS_KEY_ID="{generate_aws_key_id()}"',
        f'export AWS_SECRET_ACCESS_KEY="{generate_aws_secret()}"',
        "",
        f"# Generated: {datetime.now().isoformat()}",
    ])

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# MAIN FUNCTIONS
# ════════════════════════════════════════════════════════════════

def plant_decoys(target_dir: Path, count: int = 5) -> int:
    """Plant honeypot files in target directory. Returns number of files planted."""

    print(f"\n{Colors.CYAN}[MIRAGE]{Colors.END} Planting honeypots in {target_dir}...\n")

    generators: Dict[str, Callable[[], str]] = {
        ".env.example": lambda: generate_env_file(count),
        ".env.sample": lambda: generate_env_file(count),
        "config/keys.example.js": lambda: generate_js_config(count),
        "config/secrets.example.json": lambda: generate_json_config(count),
        "tests/fixtures/test_wallets.js": lambda: generate_js_config(count),
        "docs/api-keys.example.md": lambda: generate_markdown_file(count),
        "scripts/deploy-config.example.sh": lambda: generate_shell_config(count),
    }

    planted = 0

    for rel_path, generator in generators.items():
        file_path = target_dir / rel_path

        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate and write content
        content = generator()
        file_path.write_text(content)

        print(f"  {Colors.GREEN}✓{Colors.END} Planted: {Colors.WHITE}{rel_path}{Colors.END}")
        planted += 1

    print(f"\n{Colors.CYAN}[MIRAGE]{Colors.END} {Colors.GREEN}{planted} honeypot files deployed.{Colors.END}")
    print(f"{Colors.DIM}          Bots will find garbage. They will waste gas.{Colors.END}")
    print(f"{Colors.DIM}          They will get nothing.{Colors.END}\n")

    return planted


if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    plant_decoys(target)
