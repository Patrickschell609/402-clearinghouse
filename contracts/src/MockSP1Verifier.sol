// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title MockSP1Verifier
/// @notice Mock SP1 verifier for testing - always returns true
/// @dev Replace with real SP1Verifier address on mainnet
contract MockSP1Verifier {
    
    bool public alwaysPass = true;
    
    /// @notice Toggle verification behavior for testing
    function setAlwaysPass(bool _pass) external {
        alwaysPass = _pass;
    }
    
    /// @notice Mock verify - always returns alwaysPass
    function verifyProof(
        bytes32 /* programVKey */,
        bytes calldata /* publicValues */,
        bytes calldata /* proofBytes */
    ) external view returns (bool) {
        return alwaysPass;
    }
}
