// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console} from "forge-std/Test.sol";
import {AgentRegistry} from "../src/AgentRegistry.sol";
import {AIGuardian} from "../src/AIGuardian.sol";

/// @title SandwichSecurityTest
/// @notice Security test suite for the Sandwich Model (TEE + MPC self-custody)
/// @dev Tests 4 critical attack vectors
contract SandwichSecurityTest is Test {
    AgentRegistry public registry;
    AIGuardian public guardian;
    MockSP1Verifier public verifier;

    // Test wallets
    address public owner;
    uint256 public teePk;
    address public teeSigner;
    address public mpcWallet;
    uint256 public mpcPk;

    // Test data
    bytes32 public modelHash = keccak256("test_model_v1");
    bytes32 public programVKey = keccak256("test_program_vkey");

    function setUp() public {
        owner = address(this);

        // Create TEE keypair (simulates Phala enclave)
        teePk = 0xABCDEF123456789ABCDEF123456789ABCDEF123456789ABCDEF123456789ABCD;
        teeSigner = vm.addr(teePk);

        // Create MPC wallet (simulates NEAR MPC-derived address)
        mpcPk = 0x1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF1234567890ABCDEF;
        mpcWallet = vm.addr(mpcPk);

        // Deploy mock SP1 verifier (always passes)
        verifier = new MockSP1Verifier();

        // Deploy contracts
        registry = new AgentRegistry();
        guardian = new AIGuardian(address(verifier), programVKey);

        // Configure
        guardian.setRegistry(address(registry));
        registry.whitelistProtocol(address(guardian));

        // Register Sandwich agent
        bytes32 teeKeyAsBytes32 = bytes32(uint256(uint160(teeSigner)));
        registry.registerSandwichAgent(mpcWallet, teeKeyAsBytes32);

        // Register strategy for the MPC wallet
        vm.prank(mpcWallet);
        guardian.registerStrategy(modelHash);
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TEST 1: Man-in-the-Middle Attack
    // ═══════════════════════════════════════════════════════════════════════
    /// @notice Attacker intercepts valid signature but tries to modify payload
    /// @dev MUST REVERT - signature won't match modified payload
    function test_MITM_Attack_Reverts() public {
        console.log("TEST 1: Man-in-the-Middle Attack");

        // Original payload that TEE signed
        bytes memory originalPayload = abi.encode("SELL_ETH_0.1");
        bytes32 nonce = keccak256("unique_nonce_1");

        // TEE signs the original payload
        bytes32 messageHash = keccak256(abi.encodePacked(originalPayload, nonce));
        bytes32 ethSignedHash = _toEthSignedMessageHash(messageHash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(teePk, ethSignedHash);
        bytes memory validSignature = abi.encodePacked(r, s, v);

        // Attacker modifies payload (trying to drain funds)
        bytes memory maliciousPayload = abi.encode("DRAIN_FUNDS");

        // Build valid-looking zkML proof (mock verifier accepts anything)
        bytes memory zkProof = hex"1234";
        bytes memory publicValues = abi.encodePacked(modelHash, bytes32(0), uint64(1));

        // Attack: Submit modified payload with valid signature
        vm.prank(mpcWallet);
        vm.expectRevert("AIGuardian: TEE attestation failed");
        guardian.executeSecuredAction(
            maliciousPayload,  // Modified payload!
            validSignature,
            nonce,
            zkProof,
            publicValues
        );

        console.log("  PASSED: MITM attack correctly reverted");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TEST 2: Replay Attack
    // ═══════════════════════════════════════════════════════════════════════
    /// @notice Attacker tries to replay a valid transaction
    /// @dev MUST REVERT - nonce already used
    function test_Replay_Attack_Reverts() public {
        console.log("TEST 2: Replay Attack");

        bytes memory payload = abi.encode("BUY_ETH_1.0");
        bytes32 nonce = keccak256("unique_nonce_2");

        // Create valid signature
        bytes32 messageHash = keccak256(abi.encodePacked(payload, nonce));
        bytes32 ethSignedHash = _toEthSignedMessageHash(messageHash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(teePk, ethSignedHash);
        bytes memory signature = abi.encodePacked(r, s, v);

        bytes memory zkProof = hex"1234";
        bytes memory publicValues = abi.encodePacked(modelHash, bytes32(0), uint64(1));

        // First execution: Should succeed
        vm.prank(mpcWallet);
        guardian.executeSecuredAction(payload, signature, nonce, zkProof, publicValues);
        console.log("  First execution succeeded");

        // Replay attack: Same transaction again
        vm.prank(mpcWallet);
        vm.expectRevert("AIGuardian: nonce already used");
        guardian.executeSecuredAction(payload, signature, nonce, zkProof, publicValues);

        console.log("  PASSED: Replay attack correctly reverted");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TEST 3: Fake TEE Attack
    // ═══════════════════════════════════════════════════════════════════════
    /// @notice Attacker creates a fake TEE and tries to sign transactions
    /// @dev MUST REVERT - signature from wrong key
    function test_Fake_TEE_Attack_Reverts() public {
        console.log("TEST 3: Fake TEE Attack");

        bytes memory payload = abi.encode("TRANSFER_ALL");
        bytes32 nonce = keccak256("unique_nonce_3");

        // Attacker generates their own "TEE" keypair
        uint256 fakeTeeKey = 0xDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF;

        // Attacker signs with fake TEE
        bytes32 messageHash = keccak256(abi.encodePacked(payload, nonce));
        bytes32 ethSignedHash = _toEthSignedMessageHash(messageHash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(fakeTeeKey, ethSignedHash);
        bytes memory fakeSignature = abi.encodePacked(r, s, v);

        bytes memory zkProof = hex"1234";
        bytes memory publicValues = abi.encodePacked(modelHash, bytes32(0), uint64(1));

        // Attack: Submit with fake TEE signature
        vm.prank(mpcWallet);
        vm.expectRevert("AIGuardian: TEE attestation failed");
        guardian.executeSecuredAction(payload, fakeSignature, nonce, zkProof, publicValues);

        console.log("  PASSED: Fake TEE attack correctly reverted");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TEST 4: Invalid MPC Sender
    // ═══════════════════════════════════════════════════════════════════════
    /// @notice Random address (not registered MPC wallet) tries to execute
    /// @dev MUST REVERT - sender not in MPC whitelist
    function test_Invalid_MPC_Sender_Reverts() public {
        console.log("TEST 4: Invalid MPC Sender Attack");

        bytes memory payload = abi.encode("STEAL_FUNDS");
        bytes32 nonce = keccak256("unique_nonce_4");

        // Attacker has no MPC wallet registered
        address attacker = address(0xBAD);

        // Even with valid-looking signature (won't matter)
        bytes32 messageHash = keccak256(abi.encodePacked(payload, nonce));
        bytes32 ethSignedHash = _toEthSignedMessageHash(messageHash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(teePk, ethSignedHash);
        bytes memory signature = abi.encodePacked(r, s, v);

        bytes memory zkProof = hex"1234";
        bytes memory publicValues = abi.encodePacked(modelHash, bytes32(0), uint64(1));

        // Attack: Call from non-registered address
        vm.prank(attacker);
        vm.expectRevert("AIGuardian: not a valid MPC agent");
        guardian.executeSecuredAction(payload, signature, nonce, zkProof, publicValues);

        console.log("  PASSED: Invalid MPC sender correctly reverted");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // TEST 5: Valid Sandwich Flow (Sanity Check)
    // ═══════════════════════════════════════════════════════════════════════
    /// @notice Verify that a properly constructed request succeeds
    function test_Valid_Sandwich_Flow_Succeeds() public {
        console.log("TEST 5: Valid Sandwich Flow (Sanity Check)");

        bytes memory payload = abi.encode("BUY_TBILL_1000");
        bytes32 nonce = keccak256("unique_nonce_5");

        // TEE signs the payload
        bytes32 messageHash = keccak256(abi.encodePacked(payload, nonce));
        bytes32 ethSignedHash = _toEthSignedMessageHash(messageHash);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(teePk, ethSignedHash);
        bytes memory signature = abi.encodePacked(r, s, v);

        bytes memory zkProof = hex"1234";
        bytes memory publicValues = abi.encodePacked(modelHash, bytes32(0), uint64(1));

        // Execute from valid MPC wallet
        vm.prank(mpcWallet);
        guardian.executeSecuredAction(payload, signature, nonce, zkProof, publicValues);

        // Verify stats updated
        (,uint256 inferenceCount, uint256 score) = guardian.getAgentStats(mpcWallet);
        assertEq(inferenceCount, 1, "Inference count should be 1");
        assertEq(score, 15, "Intelligence score should be 15");

        console.log("  PASSED: Valid flow executed successfully");
    }

    // ═══════════════════════════════════════════════════════════════════════
    // HELPERS
    // ═══════════════════════════════════════════════════════════════════════

    function _toEthSignedMessageHash(bytes32 messageHash) internal pure returns (bytes32) {
        return keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", messageHash)
        );
    }
}

/// @notice Mock SP1 Verifier that accepts any proof (for testing)
contract MockSP1Verifier {
    function verifyProof(
        bytes32,
        bytes calldata,
        bytes calldata
    ) external pure {
        // Always passes
    }
}
