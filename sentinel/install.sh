#!/bin/bash
# ════════════════════════════════════════════════════════════════════
#
#   PROJECT ZERO-LEAK — Installation Script
#
#   Author: Patrick Schell (@Patrickschell609)
#
#   "One command. Full protection."
#
# ════════════════════════════════════════════════════════════════════

set -e

# Colors
RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
CYAN='\033[96m'
WHITE='\033[97m'
BOLD='\033[1m'
DIM='\033[2m'
END='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${END}"
echo -e "${CYAN}  PROJECT ZERO-LEAK — The Sentinel Defense System${END}"
echo -e "${CYAN}════════════════════════════════════════════════════════════${END}"
echo ""

# Check if target directory is provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage:${END} $0 /path/to/your/repo [options]"
    echo ""
    echo "Options:"
    echo "  --layer1    Install pre-commit hook only"
    echo "  --layer2    Plant honeypots only"
    echo "  --all       Install everything (default)"
    echo ""
    exit 1
fi

TARGET_DIR="$1"
INSTALL_MODE="${2:---all}"

# Validate target directory
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${RED}[ERROR]${END} Directory does not exist: $TARGET_DIR"
    exit 1
fi

# Check if it's a git repo
if [ ! -d "$TARGET_DIR/.git" ]; then
    echo -e "${RED}[ERROR]${END} Not a git repository: $TARGET_DIR"
    echo -e "${DIM}        Run 'git init' first.${END}"
    exit 1
fi

echo -e "${WHITE}[*] Target: ${TARGET_DIR}${END}"
echo ""

# ════════════════════════════════════════════════════════════════════
# LAYER 1: THE SHIELD
# ════════════════════════════════════════════════════════════════════

install_layer1() {
    echo -e "${YELLOW}[1] Installing Layer 1: The Shield${END}"

    HOOK_DIR="$TARGET_DIR/.git/hooks"
    HOOK_FILE="$HOOK_DIR/pre-commit"

    # Backup existing hook if present
    if [ -f "$HOOK_FILE" ]; then
        echo -e "    ${DIM}Backing up existing pre-commit hook...${END}"
        mv "$HOOK_FILE" "$HOOK_FILE.backup.$(date +%s)"
    fi

    # Copy the shield
    cp "$SCRIPT_DIR/layer1_shield.py" "$HOOK_FILE"
    chmod +x "$HOOK_FILE"

    echo -e "    ${GREEN}✓${END} Pre-commit hook installed"
    echo -e "    ${DIM}Every commit will be scanned for secrets.${END}"
    echo ""
}

# ════════════════════════════════════════════════════════════════════
# LAYER 2: THE MIRAGE
# ════════════════════════════════════════════════════════════════════

install_layer2() {
    echo -e "${YELLOW}[2] Installing Layer 2: The Mirage${END}"

    # Check for Python
    if ! command -v python3 &> /dev/null; then
        echo -e "    ${RED}✗${END} Python3 not found. Skipping Layer 2."
        return
    fi

    # Plant honeypots
    python3 "$SCRIPT_DIR/layer2_mirage.py" --target "$TARGET_DIR" --count 5

    echo -e "    ${GREEN}✓${END} Honeypot files planted"
    echo ""
}

# ════════════════════════════════════════════════════════════════════
# EXECUTE
# ════════════════════════════════════════════════════════════════════

case "$INSTALL_MODE" in
    --layer1)
        install_layer1
        ;;
    --layer2)
        install_layer2
        ;;
    --all|*)
        install_layer1
        install_layer2
        ;;
esac

# ════════════════════════════════════════════════════════════════════
# DONE
# ════════════════════════════════════════════════════════════════════

echo -e "${GREEN}════════════════════════════════════════════════════════════${END}"
echo -e "${GREEN}  ✓ SENTINEL INSTALLED${END}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${END}"
echo ""
echo -e "${WHITE}Layer 1 (Shield):${END} Active — commits are protected"
echo -e "${WHITE}Layer 2 (Mirage):${END} Active — honeypots deployed"
echo -e "${WHITE}Layer 3 (Ghost):${END}  Standby — run manually if compromised"
echo ""
echo -e "${DIM}To use Layer 3 (emergency rescue):${END}"
echo -e "${DIM}  export SPONSOR_PK=\"0x...\"${END}"
echo -e "${DIM}  export LEAKED_PK=\"0x...\"${END}"
echo -e "${DIM}  export SAFE_ADDRESS=\"0x...\"${END}"
echo -e "${DIM}  python3 $SCRIPT_DIR/layer3_ghost.py${END}"
echo ""
echo -e "${CYAN}\"I am watching. Nothing escapes.\" — The Sentinel${END}"
echo ""
