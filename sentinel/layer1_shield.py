#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   LAYER 1: THE SHIELD                                           ║
║   Project Zero-Leak Defense System                              ║
║                                                                  ║
║   Author: Patrick Schell (@Patrickschell609)                    ║
║   Type: Git Pre-Commit Hook                                     ║
║   Mission: Kill secrets before they enter git history           ║
║                                                                  ║
║   "I watch every commit. Nothing escapes."                      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

INSTALLATION:
    cp layer1_shield.py /path/to/repo/.git/hooks/pre-commit
    chmod +x /path/to/repo/.git/hooks/pre-commit

Or use the install script:
    ./install.sh /path/to/repo
"""

import sys
import math
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

# ════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════

# Entropy threshold - strings above this are suspicious
MAX_ENTROPY = 5.5

# Minimum line length to scan (skip short lines)
MIN_LINE_LENGTH = 20

# Files to always skip
SKIP_FILES = {
    '.env',           # Local env (not committed anyway)
    '.env.local',
    'package-lock.json',
    'yarn.lock',
    'poetry.lock',
    'Cargo.lock',
    'go.sum',
}

# Extensions to skip (binary, generated, etc.)
SKIP_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg',
    '.woff', '.woff2', '.ttf', '.eot',
    '.pdf', '.zip', '.tar', '.gz',
    '.pyc', '.pyo', '.so', '.dylib',
    '.min.js', '.min.css',
}

# Known secret patterns
SECRET_PATTERNS = [
    # Generic
    (r'(?i)(private[_-]?key|secret[_-]?key)\s*[=:]\s*["\']?([a-zA-Z0-9+/=_-]{20,})', "Private/Secret Key"),
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?([a-zA-Z0-9+/=_-]{20,})', "API Key"),
    (r'(?i)(access[_-]?token|auth[_-]?token)\s*[=:]\s*["\']?([a-zA-Z0-9+/=_-]{20,})', "Access Token"),
    (r'(?i)password\s*[=:]\s*["\']?([^\s"\']{8,})', "Password"),

    # Ethereum / Crypto
    (r'0x[a-fA-F0-9]{64}', "ETH Private Key (64 hex)"),
    (r'xprv[a-zA-Z0-9]{107,112}', "BIP32 Extended Private Key"),
    (r'5[HJK][1-9A-HJ-NP-Za-km-z]{49}', "Bitcoin WIF (uncompressed)"),
    (r'[KL][1-9A-HJ-NP-Za-km-z]{51}', "Bitcoin WIF (compressed)"),

    # AWS
    (r'AKIA[0-9A-Z]{16}', "AWS Access Key ID"),
    (r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[=:]\s*["\']?([a-zA-Z0-9+/]{40})', "AWS Secret Key"),

    # GitHub
    (r'ghp_[a-zA-Z0-9]{36}', "GitHub Personal Access Token"),
    (r'gho_[a-zA-Z0-9]{36}', "GitHub OAuth Token"),
    (r'ghu_[a-zA-Z0-9]{36}', "GitHub User Token"),
    (r'ghs_[a-zA-Z0-9]{36}', "GitHub Server Token"),
    (r'ghr_[a-zA-Z0-9]{36}', "GitHub Refresh Token"),

    # Stripe
    (r'sk_live_[a-zA-Z0-9]{24,}', "Stripe Live Secret Key"),
    (r'rk_live_[a-zA-Z0-9]{24,}', "Stripe Live Restricted Key"),

    # Google
    (r'AIza[0-9A-Za-z_-]{35}', "Google API Key"),

    # Slack
    (r'xox[baprs]-[0-9a-zA-Z]{10,48}', "Slack Token"),

    # Discord
    (r'[MN][A-Za-z\d]{23,}\.[\w-]{6}\.[\w-]{27}', "Discord Bot Token"),

    # Generic high-entropy hex (likely keys)
    (r'["\'][a-fA-F0-9]{64}["\']', "64-char Hex String (possible key)"),
]

# ════════════════════════════════════════════════════════════════
# COLORS
# ════════════════════════════════════════════════════════════════

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

# ════════════════════════════════════════════════════════════════
# ANALYSIS FUNCTIONS
# ════════════════════════════════════════════════════════════════

def calculate_entropy(data: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not data:
        return 0.0

    length = len(data)
    freq = {}

    for char in data:
        freq[char] = freq.get(char, 0) + 1

    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)

    return entropy


def extract_high_entropy_segments(line: str) -> List[Tuple[str, float]]:
    """Extract segments that look like secrets (high entropy)."""
    segments = []

    # Split on common delimiters
    tokens = re.split(r'[\s=:"\',\[\]{}()]+', line)

    for token in tokens:
        if len(token) >= MIN_LINE_LENGTH:
            entropy = calculate_entropy(token)
            if entropy > MAX_ENTROPY:
                segments.append((token[:40] + "..." if len(token) > 40 else token, entropy))

    return segments


def scan_line(line: str, line_num: int) -> Optional[Tuple[int, str, str]]:
    """Scan a single line for secrets. Returns (line_num, finding, detail) or None."""

    # Skip comments (basic heuristic)
    stripped = line.strip()
    if stripped.startswith('#') or stripped.startswith('//') or stripped.startswith('*'):
        # But still check for actual key patterns in comments
        pass

    # Check known patterns
    for pattern, name in SECRET_PATTERNS:
        if re.search(pattern, line):
            match = re.search(pattern, line)
            snippet = match.group(0)[:30] + "..." if len(match.group(0)) > 30 else match.group(0)
            return (line_num, f"Pattern: {name}", snippet)

    # Check entropy
    segments = extract_high_entropy_segments(line)
    if segments:
        token, entropy = segments[0]
        return (line_num, f"High Entropy ({entropy:.2f})", token)

    return None


def scan_file(file_path: Path) -> List[Tuple[int, str, str]]:
    """Scan a file for secrets. Returns list of findings."""

    # Skip by extension
    if file_path.suffix.lower() in SKIP_EXTENSIONS:
        return []

    # Skip by name
    if file_path.name in SKIP_FILES:
        return []

    # Skip if file is too large (likely generated)
    try:
        if file_path.stat().st_size > 1_000_000:  # 1MB
            return []
    except:
        return []

    findings = []

    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []

    for i, line in enumerate(content.splitlines(), 1):
        if len(line.strip()) < MIN_LINE_LENGTH:
            continue

        result = scan_line(line, i)
        if result:
            findings.append(result)

    return findings


def get_staged_files() -> List[Path]:
    """Get list of files staged for commit."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
            capture_output=True,
            text=True,
            check=True
        )
        files = []
        for f in result.stdout.splitlines():
            if f:
                p = Path(f)
                if p.exists():
                    files.append(p)
        return files
    except subprocess.CalledProcessError:
        return []

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print(f"\n{Colors.CYAN}[SENTINEL]{Colors.END} Scanning staged files...")

    staged = get_staged_files()

    if not staged:
        print(f"{Colors.GREEN}[SENTINEL]{Colors.END} No files staged. Commit allowed.\n")
        sys.exit(0)

    print(f"{Colors.WHITE}           Checking {len(staged)} file(s)...{Colors.END}")

    all_findings = {}

    for file_path in staged:
        findings = scan_file(file_path)
        if findings:
            all_findings[file_path] = findings

    if not all_findings:
        print(f"\n{Colors.GREEN}[SENTINEL]{Colors.END} {Colors.GREEN}✓ Clean. Commit allowed.{Colors.END}\n")
        sys.exit(0)

    # BLOCKED
    print(f"\n{Colors.RED}{'═' * 60}")
    print(f"  {Colors.BOLD}⛔ COMMIT BLOCKED — SECRETS DETECTED ⛔{Colors.END}")
    print(f"{Colors.RED}{'═' * 60}{Colors.END}\n")

    for file_path, findings in all_findings.items():
        print(f"{Colors.YELLOW}File: {file_path}{Colors.END}")
        for line_num, finding, detail in findings:
            print(f"  {Colors.RED}Line {line_num}:{Colors.END} {finding}")
            print(f"           {Colors.WHITE}{detail}{Colors.END}")
        print()

    print(f"{Colors.RED}{'─' * 60}{Colors.END}")
    print(f"{Colors.WHITE}Remove or rotate the secret(s) before committing.")
    print(f"If this is a false positive, add to SKIP_FILES in the hook.{Colors.END}")
    print(f"{Colors.RED}{'─' * 60}{Colors.END}\n")

    print(f"{Colors.CYAN}[SENTINEL]{Colors.END} {Colors.RED}I will not let it pass.{Colors.END}\n")

    sys.exit(1)


if __name__ == "__main__":
    main()
