// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";

/// @title MockUSDC
/// @notice Mock USDC for testing on Base Sepolia
contract MockUSDC is ERC20 {
    
    constructor() ERC20("Mock USDC", "USDC") {
        // Mint 10M to deployer for testing
        _mint(msg.sender, 10_000_000 * 1e6);
    }
    
    function decimals() public pure override returns (uint8) {
        return 6;
    }
    
    /// @notice Faucet for testing - anyone can mint
    function faucet(address to, uint256 amount) external {
        require(amount <= 10_000 * 1e6, "Max 10k per faucet call");
        _mint(to, amount);
    }
}
