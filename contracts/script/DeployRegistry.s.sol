// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {AgentRegistry} from "../src/AgentRegistry.sol";

/// @notice Deploy AgentRegistry - The Identity Layer
contract DeployRegistry is Script {
    // Your existing Merkle root from merkle_tree.py
    bytes32 constant MERKLE_ROOT = 0x263f639b87bbf5e98a3099282ffed1eca3bd946818592b0bda8fe546426afc2b;

    // Existing clearinghouse to whitelist
    address constant CLEARINGHOUSE = 0xb315C8F827e3834bB931986F177cb1fb6D20415D;

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerPrivateKey);

        // Deploy Registry
        AgentRegistry registry = new AgentRegistry();
        console.log("AgentRegistry deployed:", address(registry));

        // Set the Merkle root (migrate existing agents)
        registry.updateRoot(MERKLE_ROOT);
        console.log("Merkle root set:", vm.toString(MERKLE_ROOT));

        // Whitelist existing clearinghouse
        registry.whitelistProtocol(CLEARINGHOUSE);
        console.log("Whitelisted protocol:", CLEARINGHOUSE);

        vm.stopBroadcast();

        console.log("\n=== REGISTRY DEPLOYED ===");
        console.log("Address:", address(registry));
        console.log("Root:", vm.toString(MERKLE_ROOT));
        console.log("\nNext steps:");
        console.log("1. Verify on BaseScan");
        console.log("2. Update Clearinghouse to use registry.checkEligibility()");
        console.log("3. Agents can now self-register with Merkle proofs");
    }
}
