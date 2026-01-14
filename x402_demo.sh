#!/bin/bash
# x402 Clearinghouse Demo - Double-click to run

cd /home/python/Desktop/402infer

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
WHITE='\033[1;37m'
NC='\033[0m'

clear

echo -e "${CYAN}"
cat << 'BANNER'
 ██╗  ██╗██╗  ██╗ ██████╗ ██████╗
 ╚██╗██╔╝██║  ██║██╔═████╗╚════██╗
  ╚███╔╝ ███████║██║██╔██║ █████╔╝
  ██╔██╗ ╚════██║████╔╝██║██╔═══╝
 ██╔╝ ██╗     ██║╚██████╔╝███████╗
 ╚═╝  ╚═╝     ╚═╝ ╚═════╝ ╚══════╝

   AGENT-NATIVE RWA SETTLEMENT
       Base Mainnet | Live
BANNER
echo -e "${NC}"

sleep 1

echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  DEPLOYED CONTRACTS (All Verified ✓)${NC}"
echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}AgentRegistry${NC}    0xB3aa5a6f3Cb37C252059C49E22E5DAB8b556a9aF"
echo -e "  ${GREEN}Clearinghouse${NC}    0xb315C8F827e3834bB931986F177cb1fb6D20415D"
echo -e "  ${GREEN}MockTBill${NC}        0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A"
echo -e "  ${GREEN}MockUSDC${NC}         0x6020Ed65e0008242D9094D107D97dd17599dc21C"
echo -e "  ${GREEN}SP1Verifier${NC}      0xDd2ffa97F680032332EA4905586e2366584Ae0be"
echo ""
sleep 2

echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  [1] QUERYING AGENT REGISTRY...${NC}"
echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Merkle Root:${NC}"
ROOT=$(cast call 0xB3aa5a6f3Cb37C252059C49E22E5DAB8b556a9aF "authorizedRoot()(bytes32)" --rpc-url https://mainnet.base.org 2>/dev/null)
echo -e "  $ROOT"
echo ""
echo -e "  ${CYAN}Total Registered Agents:${NC}"
AGENTS=$(cast call 0xB3aa5a6f3Cb37C252059C49E22E5DAB8b556a9aF "totalAgents()(uint256)" --rpc-url https://mainnet.base.org 2>/dev/null)
echo -e "  $AGENTS"
echo ""
sleep 2

echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  [2] QUERYING CLEARINGHOUSE STATUS...${NC}"
echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Fee:${NC}"
FEE=$(cast call 0xb315C8F827e3834bB931986F177cb1fb6D20415D "feeBps()(uint256)" --rpc-url https://mainnet.base.org 2>/dev/null)
echo -e "  $FEE bps (0.05%)"
echo ""
echo -e "  ${CYAN}Treasury:${NC}"
TREASURY=$(cast call 0xb315C8F827e3834bB931986F177cb1fb6D20415D "treasury()(address)" --rpc-url https://mainnet.base.org 2>/dev/null)
echo -e "  $TREASURY"
echo ""
sleep 2

echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  [3] T-BILL INVENTORY...${NC}"
echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
INVENTORY=$(cast call 0x0cB59FaA219b80D8FbD28E9D37008f2db10F847A "balanceOf(address)(uint256)" 0xb315C8F827e3834bB931986F177cb1fb6D20415D --rpc-url https://mainnet.base.org 2>/dev/null)
echo -e "  ${CYAN}Clearinghouse T-Bill Balance:${NC}"
echo -e "  $INVENTORY units"
echo ""
sleep 2

echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  [4] SDK INSTALLATION${NC}"
echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}pip install x402-rwa${NC}"
echo ""
echo -e "  ${CYAN}from x402_rwa import X402Agent${NC}"
echo -e "  ${CYAN}agent = X402Agent(rpc_url, private_key)${NC}"
echo -e "  ${CYAN}tx = agent.acquire_asset(url, 'TBILL-26', 100)${NC}"
echo ""
sleep 2

echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  THE MOAT: Fork the code, but you can't fork the agents.${NC}"
echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}GitHub:${NC}   github.com/Patrickschell609/402-clearinghouse"
echo -e "  ${CYAN}PyPI:${NC}     pypi.org/project/x402-rwa"
echo -e "  ${CYAN}BaseScan:${NC} basescan.org/address/0xB3aa5a6f3Cb37C252059C49E22E5DAB8b556a9aF"
echo ""
echo -e "${WHITE}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Press Enter to exit...${NC}"
read
