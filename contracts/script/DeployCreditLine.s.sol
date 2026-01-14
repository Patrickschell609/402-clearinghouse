// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {AgentCreditLine} from "../src/AgentCreditLine.sol";

/// @notice Deploy AgentCreditLine - The Bank for AI Agents
contract DeployCreditLine is Script {
    // Your deployed contracts
    address constant REGISTRY = 0xB3aa5a6f3Cb37C252059C49E22E5DAB8b556a9aF;
    address constant USDC = 0x6020Ed65e0008242D9094D107D97dd17599dc21C; // MockUSDC

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerPrivateKey);

        AgentCreditLine creditLine = new AgentCreditLine(REGISTRY, USDC);
        console.log("AgentCreditLine deployed:", address(creditLine));

        vm.stopBroadcast();

        console.log("\n=== CREDIT LINE DEPLOYED ===");
        console.log("Address:", address(creditLine));
        console.log("Registry:", REGISTRY);
        console.log("USDC:", USDC);
        console.log("\nCredit Tiers:");
        console.log("  Score 50-79:  1x leverage");
        console.log("  Score 80-94:  3x leverage");
        console.log("  Score 95-100: 5x leverage");
        console.log("\nNext: Whitelist in Registry for reputation updates");
    }
}
