// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {Clearinghouse402} from "../src/Clearinghouse402.sol";
import {MockTBill} from "../src/MockTBill.sol";
import {MockUSDC} from "../src/MockUSDC.sol";
import {MockSP1Verifier} from "../src/MockSP1Verifier.sol";

contract DeployScript is Script {
    
    function run() public {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);
        
        console.log("Deployer:", deployer);
        console.log("Balance:", deployer.balance);
        
        vm.startBroadcast(deployerPrivateKey);
        
        // 1. Deploy mock SP1 verifier
        MockSP1Verifier verifier = new MockSP1Verifier();
        console.log("SP1Verifier deployed:", address(verifier));
        
        // 2. Deploy mock USDC
        MockUSDC usdc = new MockUSDC();
        console.log("MockUSDC deployed:", address(usdc));
        
        // 3. Deploy mock T-Bill
        MockTBill tbill = new MockTBill();
        console.log("MockTBill deployed:", address(tbill));
        
        // 4. Deploy Clearinghouse
        Clearinghouse402 clearinghouse = new Clearinghouse402(
            address(verifier),
            address(usdc),
            deployer  // Treasury = deployer for testing
        );
        console.log("Clearinghouse deployed:", address(clearinghouse));
        
        // 5. Configure T-Bill
        tbill.setClearinghouse(address(clearinghouse));
        tbill.approve(address(clearinghouse), type(uint256).max);
        
        // 6. List T-Bill asset
        bytes32 complianceCircuit = keccak256("ACCREDITED_INVESTOR_V1");
        uint256 pricePerUnit = 98 * 1e4; // $0.98 per unit (discount to par)
        
        clearinghouse.listAsset(
            address(tbill),
            deployer,  // Issuer = deployer for testing
            complianceCircuit,
            pricePerUnit
        );
        console.log("T-Bill listed at price:", pricePerUnit);
        
        vm.stopBroadcast();
        
        // Output deployment addresses for server config
        console.log("\n=== DEPLOYMENT COMPLETE ===");
        console.log("Export these to your .env:");
        console.log("SP1_VERIFIER=", address(verifier));
        console.log("USDC_ADDRESS=", address(usdc));
        console.log("TBILL_ADDRESS=", address(tbill));
        console.log("CLEARINGHOUSE=", address(clearinghouse));
    }
}
