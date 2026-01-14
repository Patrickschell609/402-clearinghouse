// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {ClearinghouseDEX} from "../src/ClearinghouseDEX.sol";

/// @notice Deploy ClearinghouseDEX to Base Mainnet
contract DeployDEX is Script {
    // Base Mainnet addresses
    address constant AERODROME_ROUTER = 0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43;
    address constant AERODROME_FACTORY = 0x420DD381b31aEf6683db6B902084cB0FFECe40Da;
    address constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913; // Real USDC on Base

    // Your contracts (for SP1 verifier - reuse existing)
    address constant SP1_VERIFIER = 0xDd2ffa97F680032332EA4905586e2366584Ae0be;
    address constant TREASURY = 0xc7554F1B16ad0b3Ce363d53364C9817743E32f90;

    // Assets to whitelist
    address constant CBBTC = 0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf;
    address constant CBXRP = 0xcb585250f852C6c6bf90434AB21A00f02833a4af;
    address constant WETH = 0x4200000000000000000000000000000000000006;

    // Compliance circuit (your Merkle root based circuit)
    bytes32 constant COMPLIANCE_CIRCUIT = 0x263f639b87bbf5e98a3099282ffed1eca3bd946818592b0bda8fe546426afc2b;

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");

        vm.startBroadcast(deployerPrivateKey);

        // Deploy ClearinghouseDEX
        ClearinghouseDEX dex = new ClearinghouseDEX(
            SP1_VERIFIER,
            AERODROME_ROUTER,
            USDC,
            AERODROME_FACTORY,
            TREASURY,
            COMPLIANCE_CIRCUIT
        );

        console.log("ClearinghouseDEX deployed:", address(dex));

        // Whitelist assets
        dex.whitelistAsset(CBBTC, false);  // volatile pool
        dex.whitelistAsset(CBXRP, false);  // volatile pool
        dex.whitelistAsset(WETH, false);   // volatile pool

        console.log("Whitelisted: cbBTC, cbXRP, WETH");

        vm.stopBroadcast();

        // Summary
        console.log("\n=== DEPLOYMENT COMPLETE ===");
        console.log("ClearinghouseDEX:", address(dex));
        console.log("Router:", AERODROME_ROUTER);
        console.log("USDC:", USDC);
        console.log("Fee: 5 bps (0.05%)");
        console.log("\nWhitelisted assets:");
        console.log("  cbBTC:", CBBTC);
        console.log("  cbXRP:", CBXRP);
        console.log("  WETH:", WETH);
    }
}
