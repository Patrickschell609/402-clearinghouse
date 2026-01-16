"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ZERO-LEAK: The Sentinel Defense System                        ║
║                                                                  ║
║   Author: Patrick Schell (@Patrickschell609)                    ║
║   Origin: Built after a bot stole from me. Never again.         ║
║                                                                  ║
║   Three layers. One mind. Absolute defense.                     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

LAYER 1 - THE SHIELD: Pre-commit hook that kills secrets before git
LAYER 2 - THE MIRAGE: Honeypot generator that wastes bot resources
LAYER 3 - THE GHOST:  MEV rescue system faster than mempool snipers

Install:
    pip install zero-leak

Usage:
    zero-leak shield /path/to/repo    # Install pre-commit hook
    zero-leak mirage /path/to/repo    # Plant honeypot keys
    zero-leak ghost                   # Emergency rescue (set env vars first)
    zero-leak protect /path/to/repo   # Full protection (shield + mirage)
"""

__version__ = "1.0.0"
__author__ = "Patrick Schell"
__email__ = "patrickschell609@gmail.com"
__github__ = "https://github.com/Patrickschell609"

from zero_leak.shield import scan_file, scan_line, calculate_entropy
from zero_leak.mirage import plant_decoys
from zero_leak.ghost import build_rescue_bundle, submit_bundle_to_all_relays

__all__ = [
    "scan_file",
    "scan_line",
    "calculate_entropy",
    "plant_decoys",
    "build_rescue_bundle",
    "submit_bundle_to_all_relays",
]
