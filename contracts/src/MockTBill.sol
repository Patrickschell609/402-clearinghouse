// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title MockTBill
/// @notice Mock tokenized Treasury Bill for testing
/// @dev Simulates an ERC-3643 compliant RWA token
contract MockTBill is ERC20, Ownable {
    
    mapping(address => bool) public verified;
    address public clearinghouse;
    
    error NotVerified();
    error NotClearinghouse();
    
    modifier onlyVerified(address account) {
        if (!verified[account] && account != clearinghouse) revert NotVerified();
        _;
    }
    
    constructor() ERC20("Mock Treasury Bill Oct 2026", "TBILL-26") Ownable(msg.sender) {
        // Mint initial supply to deployer (issuer)
        _mint(msg.sender, 1_000_000 * 1e6); // 1M units, 6 decimals like USDC
    }
    
    function decimals() public pure override returns (uint8) {
        return 6;
    }
    
    /// @notice Set the clearinghouse address
    function setClearinghouse(address _clearinghouse) external onlyOwner {
        clearinghouse = _clearinghouse;
        verified[_clearinghouse] = true;
    }
    
    /// @notice Verify an address (simulates KYC)
    function setVerified(address account, bool status) external onlyOwner {
        verified[account] = status;
    }
    
    /// @notice Check if account is verified
    function isVerified(address account) external view returns (bool) {
        return verified[account];
    }
    
    /// @notice Override transfer to enforce verification
    function transfer(address to, uint256 amount) public override onlyVerified(to) returns (bool) {
        return super.transfer(to, amount);
    }
    
    /// @notice Override transferFrom to enforce verification
    function transferFrom(address from, address to, uint256 amount) 
        public 
        override 
        onlyVerified(to) 
        returns (bool) 
    {
        return super.transferFrom(from, to, amount);
    }
    
    /// @notice Mint new tokens (issuer only)
    function mint(address to, uint256 amount) external onlyOwner onlyVerified(to) {
        _mint(to, amount);
    }
}
