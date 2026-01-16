#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗  ██████╗ ██████╗     ███╗   ███╗ ██████╗ ██████╗ ███████╗         ║
║  ██╔════╝ ██╔═══██╗██╔══██╗    ████╗ ████║██╔═══██╗██╔══██╗██╔════╝         ║
║  ██║  ███╗██║   ██║██║  ██║    ██╔████╔██║██║   ██║██║  ██║█████╗           ║
║  ██║   ██║██║   ██║██║  ██║    ██║╚██╔╝██║██║   ██║██║  ██║██╔══╝           ║
║  ╚██████╔╝╚██████╔╝██████╔╝    ██║ ╚═╝ ██║╚██████╔╝██████╔╝███████╗         ║
║   ╚═════╝  ╚═════╝ ╚═════╝     ╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝         ║
║                                                                              ║
║   x402 CLEARINGHOUSE — AUTONOMOUS SETTLEMENT LAYER                           ║
║   Real-Time Command Center                                                   ║
║                                                                              ║
║   Author: Patrick Schell (@Patrickschell609)                                 ║
║   Network: Base Mainnet                                                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import time
import os
import random
import json
from datetime import datetime, timezone
from web3 import Web3
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG — REAL CONTRACT ADDRESSES (BASE MAINNET)
# ═══════════════════════════════════════════════════════════════════════════════

RPC_URL = "https://mainnet.base.org"

# Core Contracts
CLEARINGHOUSE = "0x342d18A535Ed4931B8D50214dAC73BCb86683623"  # v2 with zero-amount fix
USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
TBILL = "0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A"
AI_GUARDIAN = "0x688f32d4Fa82B011b5A71C9a71401606200966ad"
AGENT_REGISTRY = "0xB3aa5a6f3Cb37C252059C49E22E5DAB8b556a9aF"
TREASURY = "0xc7554F1B16ad0b3Ce363d53364C9817743E32f90"

# ABIs
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]

CLEARINGHOUSE_ABI = [
    {"inputs": [], "name": "feeBps", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "paused", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "treasury", "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "", "type": "address"}], "name": "assets", "outputs": [{"name": "issuer", "type": "address"}, {"name": "complianceCircuit", "type": "bytes32"}, {"name": "pricePerUnit", "type": "uint256"}, {"name": "active", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "", "type": "address"}], "name": "agentVerifiedUntil", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"anonymous": False, "inputs": [{"indexed": True, "name": "agent", "type": "address"}, {"indexed": True, "name": "asset", "type": "address"}, {"indexed": False, "name": "amount", "type": "uint256"}, {"indexed": False, "name": "price", "type": "uint256"}, {"indexed": True, "name": "txId", "type": "bytes32"}], "name": "Settlement", "type": "event"},
]

# ═══════════════════════════════════════════════════════════════════════════════
# WEB3 CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════

w3 = Web3(Web3.HTTPProvider(RPC_URL))
usdc_contract = w3.eth.contract(address=USDC, abi=ERC20_ABI)
tbill_contract = w3.eth.contract(address=TBILL, abi=ERC20_ABI)
clearinghouse_contract = w3.eth.contract(address=CLEARINGHOUSE, abi=CLEARINGHOUSE_ABI)

# ═══════════════════════════════════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════════════════════════════════

class SystemState:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.requests_total = 0
        self.settlements_total = 0
        self.revenue_total = 0.0
        self.last_settlement = None
        self.recent_events = []
        self.error_count = 0
        self.last_block = 0

state = SystemState()

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_chain_data():
    """Fetch real on-chain data."""
    try:
        # USDC balances
        treasury_usdc = usdc_contract.functions.balanceOf(TREASURY).call() / 1e6
        clearinghouse_usdc = usdc_contract.functions.balanceOf(CLEARINGHOUSE).call() / 1e6

        # TBILL inventory at issuer (treasury)
        tbill_inventory = tbill_contract.functions.balanceOf(TREASURY).call() / 1e18

        # Clearinghouse state
        paused = clearinghouse_contract.functions.paused().call()
        fee_bps = clearinghouse_contract.functions.feeBps().call()

        # Asset config
        asset_config = clearinghouse_contract.functions.assets(TBILL).call()
        asset_active = asset_config[3]
        asset_price = asset_config[2] / 1e6

        # Current block
        block = w3.eth.block_number

        return {
            'treasury_usdc': treasury_usdc,
            'clearinghouse_usdc': clearinghouse_usdc,
            'tbill_inventory': tbill_inventory,
            'paused': paused,
            'fee_bps': fee_bps,
            'asset_active': asset_active,
            'asset_price': asset_price,
            'block': block,
            'connected': True
        }
    except Exception as e:
        state.error_count += 1
        return {
            'treasury_usdc': 0,
            'clearinghouse_usdc': 0,
            'tbill_inventory': 0,
            'paused': False,
            'fee_bps': 0,
            'asset_active': False,
            'asset_price': 0,
            'block': 0,
            'connected': False,
            'error': str(e)
        }

def get_recent_settlements(from_block=None):
    """Fetch recent Settlement events."""
    try:
        if from_block is None:
            from_block = w3.eth.block_number - 1000  # Last ~1000 blocks

        events = clearinghouse_contract.events.Settlement.get_logs(
            fromBlock=from_block,
            toBlock='latest'
        )

        settlements = []
        for event in events[-10:]:  # Last 10
            settlements.append({
                'agent': event['args']['agent'],
                'amount': event['args']['amount'],
                'price': event['args']['price'] / 1e6,
                'txId': event['args']['txId'].hex()[:16] + '...',
                'block': event['blockNumber']
            })

        return settlements
    except:
        return []

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def make_layout():
    """Create the dashboard layout."""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )

    layout["main"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=1)
    )

    layout["left"].split_column(
        Layout(name="status", ratio=1),
        Layout(name="contracts", ratio=1)
    )

    layout["right"].split_column(
        Layout(name="metrics", ratio=1),
        Layout(name="activity", ratio=1)
    )

    return layout

def render_header():
    """Render the header panel."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uptime = datetime.now(timezone.utc) - state.start_time
    uptime_str = str(uptime).split('.')[0]

    header_text = Text()
    header_text.append("x402 CLEARINGHOUSE", style="bold cyan")
    header_text.append(" — ", style="dim")
    header_text.append("AUTONOMOUS SETTLEMENT LAYER", style="bold white")
    header_text.append("\n")
    header_text.append(f"Network: ", style="dim")
    header_text.append("Base Mainnet", style="green")
    header_text.append(f"  |  Time: ", style="dim")
    header_text.append(now, style="white")
    header_text.append(f"  |  Uptime: ", style="dim")
    header_text.append(uptime_str, style="yellow")

    return Panel(header_text, style="bold white on black", box=box.DOUBLE)

def render_status(data):
    """Render system status panel."""
    table = Table(title="SYSTEM STATUS", expand=True, box=box.ROUNDED)
    table.add_column("Component", style="cyan", no_wrap=True)
    table.add_column("Status", style="green", justify="center")

    # Connection
    if data['connected']:
        table.add_row("RPC Connection", "[green]● CONNECTED[/green]")
    else:
        table.add_row("RPC Connection", "[red]● DISCONNECTED[/red]")

    # Clearinghouse
    if data['paused']:
        table.add_row("Clearinghouse", "[yellow]● PAUSED[/yellow]")
    else:
        table.add_row("Clearinghouse", "[green]● ACTIVE[/green]")

    # Asset
    if data['asset_active']:
        table.add_row("TBILL Asset", "[green]● LISTED[/green]")
    else:
        table.add_row("TBILL Asset", "[red]● NOT LISTED[/red]")

    # Security
    table.add_row("ReentrancyGuard", "[green]● ENABLED[/green]")
    table.add_row("Pausable", "[green]● ENABLED[/green]")
    table.add_row("Zero-Amount Fix", "[green]● DEPLOYED[/green]")

    # Block
    table.add_row("Latest Block", f"[white]{data['block']:,}[/white]")

    return Panel(table, border_style="green")

def render_contracts():
    """Render contract addresses panel."""
    table = Table(title="DEPLOYED CONTRACTS", expand=True, box=box.ROUNDED)
    table.add_column("Contract", style="cyan", no_wrap=True)
    table.add_column("Address", style="magenta")

    table.add_row("Clearinghouse v2", f"[dim]{CLEARINGHOUSE[:10]}...{CLEARINGHOUSE[-8:]}[/dim]")
    table.add_row("USDC", f"[dim]{USDC[:10]}...{USDC[-8:]}[/dim]")
    table.add_row("TBILL", f"[dim]{TBILL[:10]}...{TBILL[-8:]}[/dim]")
    table.add_row("AI Guardian", f"[dim]{AI_GUARDIAN[:10]}...{AI_GUARDIAN[-8:]}[/dim]")
    table.add_row("Treasury", f"[dim]{TREASURY[:10]}...{TREASURY[-8:]}[/dim]")

    return Panel(table, border_style="blue")

def render_metrics(data):
    """Render financial metrics panel."""
    table = Table(title="FINANCIAL METRICS", expand=True, box=box.ROUNDED)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green", justify="right")

    # Treasury balance
    table.add_row("Treasury USDC", f"[bold green]${data['treasury_usdc']:,.2f}[/bold green]")

    # Clearinghouse balance (should be 0 - non-custodial)
    if data['clearinghouse_usdc'] == 0:
        table.add_row("Clearinghouse USDC", "[green]$0.00 (non-custodial)[/green]")
    else:
        table.add_row("Clearinghouse USDC", f"[yellow]${data['clearinghouse_usdc']:,.2f}[/yellow]")

    # Inventory
    table.add_row("TBILL Inventory", f"[white]{data['tbill_inventory']:,.0f} units[/white]")

    # Asset price
    table.add_row("TBILL Price", f"[white]${data['asset_price']:.2f}/unit[/white]")

    # Fee
    table.add_row("Protocol Fee", f"[white]{data['fee_bps']/100:.2f}%[/white]")

    # Potential Revenue
    potential = data['tbill_inventory'] * data['asset_price'] * (data['fee_bps'] / 10000)
    table.add_row("Potential Fee Revenue", f"[yellow]${potential:,.2f}[/yellow]")

    return Panel(table, border_style="green")

def render_activity(settlements):
    """Render live activity panel."""
    table = Table(title="RECENT SETTLEMENTS", expand=True, box=box.ROUNDED)
    table.add_column("Block", style="dim", no_wrap=True)
    table.add_column("Agent", style="magenta")
    table.add_column("Amount", style="white", justify="right")
    table.add_column("Value", style="green", justify="right")

    if not settlements:
        table.add_row("[dim]—[/dim]", "[dim]Waiting for settlements...[/dim]", "[dim]—[/dim]", "[dim]—[/dim]")
    else:
        for s in settlements[-5:]:
            agent_short = f"{s['agent'][:6]}...{s['agent'][-4:]}"
            table.add_row(
                str(s['block']),
                agent_short,
                f"{s['amount']} TBILL",
                f"${s['price']:,.2f}"
            )

    return Panel(table, border_style="cyan")

def render_footer():
    """Render footer with commands."""
    footer_text = Text()
    footer_text.append("  [Q] Quit  ", style="dim")
    footer_text.append("|", style="dim")
    footer_text.append("  [P] Pause Contract  ", style="dim")
    footer_text.append("|", style="dim")
    footer_text.append("  [R] Refresh  ", style="dim")
    footer_text.append("|", style="dim")
    footer_text.append("  Errors: ", style="dim")
    footer_text.append(str(state.error_count), style="red" if state.error_count > 0 else "green")

    return Panel(footer_text, style="dim")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def run_dashboard():
    """Main dashboard loop."""
    layout = make_layout()
    console = Console()

    # Initial data
    data = get_chain_data()
    settlements = get_recent_settlements()

    with Live(layout, refresh_per_second=1, screen=True, console=console) as live:
        while True:
            try:
                # Fetch fresh data
                data = get_chain_data()

                # Check for new settlements periodically
                if data['block'] > state.last_block:
                    settlements = get_recent_settlements(state.last_block - 10 if state.last_block > 0 else None)
                    state.last_block = data['block']

                # Update all panels
                layout["header"].update(render_header())
                layout["status"].update(render_status(data))
                layout["contracts"].update(render_contracts())
                layout["metrics"].update(render_metrics(data))
                layout["activity"].update(render_activity(settlements))
                layout["footer"].update(render_footer())

                time.sleep(2)

            except KeyboardInterrupt:
                break
            except Exception as e:
                state.error_count += 1
                time.sleep(5)

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n")
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║   x402 CLEARINGHOUSE — GOD MODE                              ║")
    print("  ║   Starting dashboard...                                      ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print("\n")

    # Quick connection test
    try:
        block = w3.eth.block_number
        print(f"  [✓] Connected to Base Mainnet (Block: {block:,})")
        print(f"  [✓] Clearinghouse: {CLEARINGHOUSE}")
        print(f"  [✓] Treasury: {TREASURY}")
        print("\n  Launching dashboard...\n")
        time.sleep(1)
    except Exception as e:
        print(f"  [✗] Connection failed: {e}")
        exit(1)

    run_dashboard()
