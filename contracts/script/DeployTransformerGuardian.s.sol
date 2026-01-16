// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Script, console} from "forge-std/Script.sol";
import {AIGuardian} from "../src/AIGuardian.sol";

contract DeployTransformerGuardian is Script {
    // Transformer attention circuit vKey (from proof generation)
    bytes32 constant TRANSFORMER_VKEY = 0x007c7f386f0ccc16d2a18c3ef536e4c91b0839a2b91b5935ced528715ec581f6;

    // Existing MockSP1Verifier on Base mainnet
    address constant SP1_VERIFIER = 0xDd2ffa97F680032332EA4905586e2366584Ae0be;

    function run() public {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("=== TRANSFORMER GUARDIAN DEPLOYMENT ===");
        console.log("Deployer:", deployer);
        console.log("Balance:", deployer.balance);
        console.log("vKey:", vm.toString(TRANSFORMER_VKEY));

        vm.startBroadcast(deployerPrivateKey);

        // Deploy TransformerGuardian (AIGuardian with transformer vKey)
        AIGuardian guardian = new AIGuardian(SP1_VERIFIER, TRANSFORMER_VKEY);

        vm.stopBroadcast();

        console.log("");
        console.log("=== DEPLOYMENT COMPLETE ===");
        console.log("TransformerGuardian:", address(guardian));
        console.log("");
        console.log("This is the FIRST transformer attention zkML verifier on Base.");
    }
}
