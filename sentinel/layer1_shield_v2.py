#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   LAYER 1: THE SHIELD v2.0                                       ║
║   Context-Aware Secret Detection                                 ║
║                                                                  ║
║   Author: Patrick Schell (@Patrickschell609)                     ║
║                                                                  ║
║   UPGRADE: No more false positives.                              ║
║   - Understands TX hashes vs private keys                        ║
║   - Knows contract addresses vs secrets                          ║
║   - Context-aware: "private_key =" is bad, "TX:" is fine         ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import re
import subprocess
import secrets
from pathlib import Path
from typing import List, Tuple, Set
from dataclasses import dataclass

# ════════════════════════════════════════════════════════════════
# SAFE CONTEXT PATTERNS - These prefixes mean it's NOT a secret
# ════════════════════════════════════════════════════════════════

SAFE_PREFIXES = {
    # Transaction hashes
    'tx:', 'tx hash:', 'txhash:', 'transaction:', 'hash:',
    'tx=', 'txhash=', 'transaction=',

    # Contract/wallet addresses (public, not secret)
    'address:', 'contract:', 'deployed:', 'deployed at:',
    'address=', 'contract=', 'clearinghouse:', 'treasury:',
    'from:', 'to:', 'sender:', 'receiver:', 'owner:',

    # Verification keys (public)
    'vkey:', 'vkey=', 'programvkey:', 'verification key:',
    'verifier:', 'sp1verifier:',

    # Hashes (not secrets)
    'model hash:', 'data hash:', 'commit:', 'sha256:',
    'keccak:', 'hash=', 'blockhash:',

    # URLs and references
    'basescan:', 'etherscan:', 'https://', 'http://',

    # Code comments indicating safe
    '// deployed', '// address', '// tx', '# tx', '# address',
    '// example', '// test', '# example', '# test',
}

SAFE_SUFFIXES = {
    '(public)', '(address)', '(tx)', '(hash)', '(deployed)',
    '# address', '# tx', '# hash', '# public', '# safe',
    '// address', '// tx', '// hash', '// public', '// safe',
}

# ════════════════════════════════════════════════════════════════
# DANGEROUS CONTEXT PATTERNS - These mean it IS a secret
# ════════════════════════════════════════════════════════════════

DANGEROUS_PREFIXES = {
    # Private key assignments
    'private_key', 'privatekey', 'priv_key', 'privkey',
    'secret_key', 'secretkey', 'secret=', 'secret:',
    'pk=', 'pk:', 'sk=', 'sk:',

    # API keys
    'api_key', 'apikey', 'api_secret', 'apisecret',
    'access_key', 'accesskey', 'access_token',

    # Mnemonics
    'mnemonic', 'seed_phrase', 'seedphrase', 'seed=',

    # Generic secrets
    'password', 'passwd', 'pwd=', 'token=',
    'auth_token', 'bearer', 'credential',
}

# ════════════════════════════════════════════════════════════════
# SECRET FORMATS - Generate real examples to match against
# ════════════════════════════════════════════════════════════════

@dataclass
class SecretFormat:
    name: str
    pattern: re.Pattern
    generate: callable  # Function to generate example
    min_length: int
    is_hex: bool = False

def gen_eth_key():
    return '0x' + secrets.token_hex(32)

def gen_btc_wif():
    # WIF starts with 5, K, or L
    chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    return '5' + ''.join(secrets.choice(chars) for _ in range(50))

def gen_aws_key():
    return 'AKIA' + ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567') for _ in range(16))

def gen_github_token():
    chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return 'ghp_' + ''.join(secrets.choice(chars) for _ in range(36))

SECRET_FORMATS = [
    SecretFormat(
        name="ETH Private Key",
        pattern=re.compile(r'0x[a-fA-F0-9]{64}\b'),
        generate=gen_eth_key,
        min_length=66,
        is_hex=True
    ),
    SecretFormat(
        name="BTC WIF Key",
        pattern=re.compile(r'\b[5KL][1-9A-HJ-NP-Za-km-z]{50,51}\b'),
        generate=gen_btc_wif,
        min_length=51
    ),
    SecretFormat(
        name="AWS Access Key",
        pattern=re.compile(r'\bAKIA[A-Z2-7]{16}\b'),
        generate=gen_aws_key,
        min_length=20
    ),
    SecretFormat(
        name="GitHub Token",
        pattern=re.compile(r'\bghp_[a-zA-Z0-9]{36}\b'),
        generate=gen_github_token,
        min_length=40
    ),
    SecretFormat(
        name="Generic Hex Secret",
        pattern=re.compile(r'\b[a-fA-F0-9]{64}\b'),  # 64 hex without 0x
        generate=lambda: secrets.token_hex(32),
        min_length=64,
        is_hex=True
    ),
]

# ════════════════════════════════════════════════════════════════
# CONTEXT ANALYZER
# ════════════════════════════════════════════════════════════════

class ContextAnalyzer:
    """
    Analyzes the CONTEXT around a potential secret to determine
    if it's actually dangerous or just a false positive.
    """

    def __init__(self):
        # Generate sample secrets to understand formats
        self.samples = {fmt.name: fmt.generate() for fmt in SECRET_FORMATS}

    def get_context(self, line: str, match_start: int, match_end: int) -> Tuple[str, str]:
        """Get text before and after the match."""
        before = line[:match_start].lower().strip()
        after = line[match_end:].lower().strip()
        return before, after

    def is_safe_context(self, line: str, match_start: int, match_end: int) -> Tuple[bool, str]:
        """
        Check if the context indicates this is NOT a real secret.
        Returns (is_safe, reason)
        """
        before, after = self.get_context(line, match_start, match_end)
        full_line_lower = line.lower()

        # Check safe prefixes
        for prefix in SAFE_PREFIXES:
            if before.endswith(prefix.rstrip(':= ')):
                return True, f"Safe prefix: '{prefix}'"
            if prefix in before[-50:]:  # Check last 50 chars before match
                return True, f"Safe context: '{prefix}'"

        # Check safe suffixes
        for suffix in SAFE_SUFFIXES:
            if suffix in after[:50]:  # Check first 50 chars after match
                return True, f"Safe suffix: '{suffix}'"

        # Check if it's in a URL
        if 'basescan.org' in full_line_lower or 'etherscan.io' in full_line_lower:
            return True, "URL context (block explorer)"

        # Check if line is a comment describing something safe
        stripped = line.strip()
        if stripped.startswith(('#', '//', '/*', '*')):
            # It's a comment - check if it mentions safe things
            safe_words = ['address', 'tx', 'hash', 'deployed', 'contract', 'example']
            if any(word in full_line_lower for word in safe_words):
                return True, "Comment describing safe value"

        return False, ""

    def is_dangerous_context(self, line: str, match_start: int, match_end: int) -> Tuple[bool, str]:
        """
        Check if the context indicates this IS a real secret.
        Returns (is_dangerous, reason)
        """
        before, after = self.get_context(line, match_start, match_end)
        full_line_lower = line.lower()

        # Check dangerous prefixes
        for prefix in DANGEROUS_PREFIXES:
            if prefix in before:
                return True, f"Dangerous context: '{prefix}'"

        # Check for assignment patterns
        assignment_patterns = [
            r'private_key\s*=',
            r'secret\s*=',
            r'api_key\s*=',
            r'["\']\s*:\s*["\']?\s*0x',  # JSON-like: "key": "0x..."
        ]
        for pattern in assignment_patterns:
            if re.search(pattern, full_line_lower):
                return True, f"Assignment pattern detected"

        return False, ""

    def analyze(self, line: str, match: re.Match, format_name: str) -> dict:
        """
        Full analysis of a potential secret.
        Returns dict with verdict and reasoning.
        """
        match_start = match.start()
        match_end = match.end()
        matched_value = match.group()

        result = {
            'value': matched_value[:20] + '...' if len(matched_value) > 20 else matched_value,
            'format': format_name,
            'is_secret': False,
            'confidence': 'low',
            'reason': '',
        }

        # First check: Is context explicitly safe?
        is_safe, safe_reason = self.is_safe_context(line, match_start, match_end)
        if is_safe:
            result['is_secret'] = False
            result['confidence'] = 'high'
            result['reason'] = safe_reason
            return result

        # Second check: Is context explicitly dangerous?
        is_dangerous, danger_reason = self.is_dangerous_context(line, match_start, match_end)
        if is_dangerous:
            result['is_secret'] = True
            result['confidence'] = 'high'
            result['reason'] = danger_reason
            return result

        # Third check: Ambiguous - use heuristics
        # If it's a 64-char hex and no safe context, be cautious
        if format_name in ["ETH Private Key", "Generic Hex Secret"]:
            # Check if it looks like a TX hash (they're also 64 hex)
            # TX hashes are usually displayed, not assigned
            if '=' in line[:match_start] or ':' in line[match_start-5:match_start]:
                # Looks like an assignment - suspicious
                result['is_secret'] = True
                result['confidence'] = 'medium'
                result['reason'] = "Hex value in assignment context"
            else:
                # Just displayed somewhere - probably safe
                result['is_secret'] = False
                result['confidence'] = 'medium'
                result['reason'] = "Hex value without assignment (likely hash/address)"
        else:
            # Non-hex formats (AWS, GitHub tokens, etc.) are almost always secrets
            result['is_secret'] = True
            result['confidence'] = 'high'
            result['reason'] = f"Matched {format_name} pattern"

        return result


# ════════════════════════════════════════════════════════════════
# FILE SCANNER
# ════════════════════════════════════════════════════════════════

SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
    '.woff', '.woff2', '.ttf', '.eot',
    '.pdf', '.zip', '.tar', '.gz',
    '.pyc', '.pyo', '.so', '.dylib', '.dll',
    '.min.js', '.min.css',
    '.lock',
}

def scan_file(filepath: Path, analyzer: ContextAnalyzer) -> List[dict]:
    """Scan a file for secrets using context-aware analysis."""

    if filepath.suffix in SKIP_EXTENSIONS:
        return []

    try:
        content = filepath.read_text(errors='ignore')
    except Exception:
        return []

    findings = []
    lines = content.split('\n')

    for line_num, line in enumerate(lines, 1):
        if len(line) < 20:  # Skip short lines
            continue

        for fmt in SECRET_FORMATS:
            for match in fmt.pattern.finditer(line):
                analysis = analyzer.analyze(line, match, fmt.name)

                if analysis['is_secret'] and analysis['confidence'] in ['high', 'medium']:
                    findings.append({
                        'file': str(filepath),
                        'line': line_num,
                        'format': fmt.name,
                        'value': analysis['value'],
                        'confidence': analysis['confidence'],
                        'reason': analysis['reason'],
                    })

    return findings


def get_staged_files() -> List[Path]:
    """Get list of staged files from git."""
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []

    files = []
    for name in result.stdout.strip().split('\n'):
        if name:
            path = Path(name)
            if path.exists():
                files.append(path)
    return files


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("\033[96m[SENTINEL v2.0]\033[0m Context-aware scan...")

    files = get_staged_files()
    if not files:
        print("\033[92m[SENTINEL]\033[0m No files staged. Commit allowed.")
        sys.exit(0)

    print(f"\033[97m             Scanning {len(files)} file(s)...\033[0m")

    analyzer = ContextAnalyzer()
    all_findings = []

    for filepath in files:
        findings = scan_file(filepath, analyzer)
        all_findings.extend(findings)

    # Filter to only high-confidence findings
    critical = [f for f in all_findings if f['confidence'] == 'high']
    warnings = [f for f in all_findings if f['confidence'] == 'medium']

    if critical:
        print()
        print("\033[91m════════════════════════════════════════════════════════════")
        print("  \033[1m⛔ COMMIT BLOCKED — SECRETS DETECTED ⛔\033[0m")
        print("\033[91m════════════════════════════════════════════════════════════\033[0m")
        print()

        for f in critical:
            print(f"\033[93mFile: {f['file']}\033[0m")
            print(f"  \033[91mLine {f['line']}:\033[0m {f['format']}")
            print(f"           \033[97m{f['value']}\033[0m")
            print(f"           Reason: {f['reason']}")
            print()

        if warnings:
            print("\033[93m── Warnings (medium confidence) ──\033[0m")
            for f in warnings:
                print(f"  {f['file']}:{f['line']} - {f['format']}")

        print("\033[91m────────────────────────────────────────────────────────────\033[0m")
        print("\033[97mRemove the secret(s) before committing.\033[0m")
        print("\033[91m────────────────────────────────────────────────────────────\033[0m")
        print()
        print("\033[96m[SENTINEL]\033[0m \033[91mBlocked.\033[0m")
        sys.exit(1)

    elif warnings:
        print()
        print("\033[93m[SENTINEL] ⚠ Warnings (review recommended):\033[0m")
        for f in warnings:
            print(f"  {f['file']}:{f['line']} - {f['format']} ({f['reason']})")
        print()
        print("\033[92m[SENTINEL]\033[0m \033[92m✓ Commit allowed (no high-confidence secrets).\033[0m")
        sys.exit(0)

    else:
        print()
        print("\033[92m[SENTINEL]\033[0m \033[92m✓ Clean. No secrets detected.\033[0m")
        sys.exit(0)


if __name__ == '__main__':
    main()
