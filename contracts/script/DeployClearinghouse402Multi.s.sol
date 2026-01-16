// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {Script, console} from "forge-std/Script.sol";
import {Clearinghouse402Multi} from "../src/Clearinghouse402Multi.sol";

contract DeployClearinghouse402Multi is Script {
    // Base mainnet stablecoins
    address constant USDC = 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913;
    address constant USDT = 0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2;
    address constant DAI  = 0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb;
    address constant PYUSD = 0xCfA3Ef56d303AE4fAabA0592388F19d7C3399FB4;

    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);

        console.log("Deploying Clearinghouse402Multi...");
        console.log("Deployer:", deployer);
        console.log("Treasury:", deployer); // Using deployer as treasury

        vm.startBroadcast(deployerPrivateKey);

        // Deploy with deployer as treasury
        Clearinghouse402Multi clearinghouse = new Clearinghouse402Multi(deployer);
        console.log("Clearinghouse402Multi deployed:", address(clearinghouse));

        // Whitelist major Base stablecoins
        clearinghouse.whitelistToken(USDC, true);
        console.log("Whitelisted USDC:", USDC);

        clearinghouse.whitelistToken(USDT, true);
        console.log("Whitelisted USDT:", USDT);

        clearinghouse.whitelistToken(DAI, true);
        console.log("Whitelisted DAI:", DAI);

        clearinghouse.whitelistToken(PYUSD, true);
        console.log("Whitelisted PYUSD:", PYUSD);

        vm.stopBroadcast();

        console.log("");
        console.log("=== Deployment Complete ===");
        console.log("Clearinghouse402Multi:", address(clearinghouse));
        console.log("Owner:", clearinghouse.owner());
        console.log("Treasury:", clearinghouse.treasury());
        console.log("Fee:", clearinghouse.FEE_BPS(), "bps (0.5%)");
        console.log("Withdrawal limit:", clearinghouse.MAX_WITHDRAWAL_BPS(), "bps (50%) per 24h");
    }
}
