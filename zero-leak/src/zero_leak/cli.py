#!/usr/bin/env python3
"""
Zero-Leak CLI - Command line interface for the Sentinel Defense System

Author: Patrick Schell (@Patrickschell609)
"""

import sys
import argparse
from pathlib import Path

from zero_leak import __version__


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


BANNER = f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ZERO-LEAK v{__version__}                                             ║
║   The Sentinel Defense System                                    ║
║                                                                  ║
║   Author: Patrick Schell (@Patrickschell609)                    ║
║   "Built after a bot stole from me. Never again."               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Colors.END}
"""


def cmd_shield(args):
    """Install the pre-commit hook (Layer 1)."""
    from zero_leak.shield import install_hook

    target = Path(args.target).resolve()

    if not target.exists():
        print(f"{Colors.RED}[ERROR]{Colors.END} Directory does not exist: {target}")
        sys.exit(1)

    if not (target / ".git").exists():
        print(f"{Colors.RED}[ERROR]{Colors.END} Not a git repository: {target}")
        print(f"{Colors.DIM}        Run 'git init' first.{Colors.END}")
        sys.exit(1)

    install_hook(target)
    print(f"\n{Colors.GREEN}[SHIELD]{Colors.END} Pre-commit hook installed.")
    print(f"{Colors.DIM}         Every commit will be scanned for secrets.{Colors.END}\n")


def cmd_mirage(args):
    """Plant honeypot files (Layer 2)."""
    from zero_leak.mirage import plant_decoys

    target = Path(args.target).resolve()

    if not target.exists():
        print(f"{Colors.RED}[ERROR]{Colors.END} Directory does not exist: {target}")
        sys.exit(1)

    plant_decoys(target, args.count)


def cmd_ghost(args):
    """Run emergency rescue (Layer 3)."""
    from zero_leak.ghost import run_rescue

    run_rescue(
        rpc_url=args.rpc,
        sponsor_pk=args.sponsor,
        leaked_pk=args.leaked,
        safe_address=args.safe
    )


def cmd_protect(args):
    """Full protection: shield + mirage."""
    print(BANNER)
    print(f"{Colors.YELLOW}[PROTECT]{Colors.END} Installing full protection...\n")

    # Install shield
    args_shield = argparse.Namespace(target=args.target)
    cmd_shield(args_shield)

    # Plant mirage
    args_mirage = argparse.Namespace(target=args.target, count=args.count)
    cmd_mirage(args_mirage)

    print(f"\n{Colors.GREEN}{'═' * 60}")
    print(f"  ZERO-LEAK PROTECTION ACTIVE")
    print(f"{'═' * 60}{Colors.END}")
    print(f"\n{Colors.WHITE}Layer 1 (Shield):{Colors.END} Commits are protected")
    print(f"{Colors.WHITE}Layer 2 (Mirage):{Colors.END} Honeypots deployed")
    print(f"{Colors.WHITE}Layer 3 (Ghost):{Colors.END}  Ready if needed\n")
    print(f"{Colors.CYAN}\"I am watching. Nothing escapes.\" — The Sentinel{Colors.END}\n")


def cmd_scan(args):
    """Scan a file or directory for secrets."""
    from zero_leak.shield import scan_file, scan_directory

    target = Path(args.target).resolve()

    if not target.exists():
        print(f"{Colors.RED}[ERROR]{Colors.END} Path does not exist: {target}")
        sys.exit(1)

    print(f"\n{Colors.CYAN}[SCAN]{Colors.END} Scanning {target}...\n")

    if target.is_file():
        findings = scan_file(target)
        if findings:
            print(f"{Colors.YELLOW}File: {target}{Colors.END}")
            for line_num, finding, detail in findings:
                print(f"  {Colors.RED}Line {line_num}:{Colors.END} {finding}")
                print(f"           {Colors.WHITE}{detail}{Colors.END}")
        else:
            print(f"{Colors.GREEN}[CLEAN]{Colors.END} No secrets detected.\n")
    else:
        all_findings = scan_directory(target)
        if all_findings:
            for file_path, findings in all_findings.items():
                print(f"{Colors.YELLOW}File: {file_path}{Colors.END}")
                for line_num, finding, detail in findings:
                    print(f"  {Colors.RED}Line {line_num}:{Colors.END} {finding}")
                    print(f"           {Colors.WHITE}{detail}{Colors.END}")
                print()
            print(f"{Colors.RED}[WARNING]{Colors.END} Secrets detected in {len(all_findings)} file(s).\n")
            sys.exit(1)
        else:
            print(f"{Colors.GREEN}[CLEAN]{Colors.END} No secrets detected.\n")


def main():
    parser = argparse.ArgumentParser(
        prog="zero-leak",
        description="The Sentinel Defense System - Protect your secrets from bots",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  zero-leak shield /path/to/repo     Install pre-commit hook
  zero-leak mirage /path/to/repo     Plant honeypot keys
  zero-leak protect /path/to/repo    Full protection (shield + mirage)
  zero-leak scan /path/to/file       Scan for secrets
  zero-leak ghost --help             Emergency rescue options

Author: Patrick Schell (@Patrickschell609)
        """
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"zero-leak {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Shield command
    shield_parser = subparsers.add_parser(
        "shield",
        help="Install pre-commit hook (Layer 1)"
    )
    shield_parser.add_argument(
        "target",
        type=str,
        help="Path to git repository"
    )
    shield_parser.set_defaults(func=cmd_shield)

    # Mirage command
    mirage_parser = subparsers.add_parser(
        "mirage",
        help="Plant honeypot files (Layer 2)"
    )
    mirage_parser.add_argument(
        "target",
        type=str,
        help="Path to repository"
    )
    mirage_parser.add_argument(
        "-c", "--count",
        type=int,
        default=5,
        help="Number of fake keys per file (default: 5)"
    )
    mirage_parser.set_defaults(func=cmd_mirage)

    # Ghost command
    ghost_parser = subparsers.add_parser(
        "ghost",
        help="Emergency rescue via MEV bundles (Layer 3)"
    )
    ghost_parser.add_argument(
        "--rpc",
        type=str,
        help="RPC URL (or set RPC_URL env var)"
    )
    ghost_parser.add_argument(
        "--sponsor",
        type=str,
        help="Sponsor private key (or set SPONSOR_PK env var)"
    )
    ghost_parser.add_argument(
        "--leaked",
        type=str,
        help="Leaked private key (or set LEAKED_PK env var)"
    )
    ghost_parser.add_argument(
        "--safe",
        type=str,
        help="Safe destination address (or set SAFE_ADDRESS env var)"
    )
    ghost_parser.set_defaults(func=cmd_ghost)

    # Protect command
    protect_parser = subparsers.add_parser(
        "protect",
        help="Full protection: shield + mirage"
    )
    protect_parser.add_argument(
        "target",
        type=str,
        help="Path to git repository"
    )
    protect_parser.add_argument(
        "-c", "--count",
        type=int,
        default=5,
        help="Number of fake keys per file (default: 5)"
    )
    protect_parser.set_defaults(func=cmd_protect)

    # Scan command
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan file or directory for secrets"
    )
    scan_parser.add_argument(
        "target",
        type=str,
        help="File or directory to scan"
    )
    scan_parser.set_defaults(func=cmd_scan)

    # Parse and execute
    args = parser.parse_args()

    if args.command is None:
        print(BANNER)
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
