// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║                                                                  ║
 * ║   AI GUARDIAN — Proof of Intelligence Verifier                  ║
 * ║   x402 Clearinghouse zkML Layer                                 ║
 * ║                                                                  ║
 * ║   Author: Patrick Schell (@Patrickschell609)                    ║
 * ║   Verifies: ZK proofs that an AI strategy made a decision       ║
 * ║                                                                  ║
 * ╚══════════════════════════════════════════════════════════════════╝
 *
 * This contract verifies that an agent:
 * 1. Ran an approved AI model (strategy binding)
 * 2. On valid market data (data integrity)
 * 3. Produced a specific decision (computation proof)
 *
 * All without revealing the model weights or input data.
 */

/// @notice Interface for SP1 proof verification
interface ISP1Verifier {
    function verifyProof(
        bytes32 programVKey,
        bytes calldata publicValues,
        bytes calldata proofBytes
    ) external view;
}

/// @notice Interface for AgentRegistry (Sandwich Model support)
interface IAgentRegistry {
    function isMpcWallet(address wallet) external view returns (bool);
    function agentTeePublicKey(address wallet) external view returns (bytes32);
    function usedNonces(bytes32 nonce) external view returns (bool);
    function markNonceUsed(bytes32 nonce) external;
    function isVerified(address agent) external view returns (bool);
}

/// @notice Interface for Clearinghouse execution
interface IClearinghouse {
    function execute(bytes calldata actionPayload) external;
}

contract AIGuardian {
    // ═══════════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════════

    ISP1Verifier public immutable verifier;
    bytes32 public immutable programVKey;

    /// @notice AgentRegistry for Sandwich Model verification
    IAgentRegistry public registry;

    /// @notice Clearinghouse for action execution
    IClearinghouse public clearinghouse;

    /// @notice Mapping of agent address to their approved model hash
    mapping(address => bytes32) public agentStrategies;

    /// @notice Mapping of agent address to their intelligence score
    mapping(address => uint256) public intelligenceScores;

    /// @notice Total verified inferences per agent
    mapping(address => uint256) public verifiedInferences;

    // ═══════════════════════════════════════════════════════════════
    // EVENTS
    // ═══════════════════════════════════════════════════════════════

    event StrategyRegistered(address indexed agent, bytes32 modelHash);
    event InferenceVerified(
        address indexed agent,
        bytes32 modelHash,
        bytes32 dataHash,
        int64 prediction
    );
    event CreditIssued(address indexed agent, uint256 amount);
    event SandwichActionExecuted(
        address indexed agent,
        bytes32 payloadHash,
        bytes32 nonce
    );
    event RegistryUpdated(address indexed newRegistry);
    event ClearinghouseUpdated(address indexed newClearinghouse);

    // ═══════════════════════════════════════════════════════════════
    // CONSTRUCTOR
    // ═══════════════════════════════════════════════════════════════

    constructor(address _verifier, bytes32 _programVKey) {
        verifier = ISP1Verifier(_verifier);
        programVKey = _programVKey;
    }

    // ═══════════════════════════════════════════════════════════════
    // STRATEGY REGISTRATION
    // ═══════════════════════════════════════════════════════════════

    /**
     * @notice Register an AI strategy (model hash) for an agent
     * @param modelHash The SHA256 hash of the serialized model
     */
    function registerStrategy(bytes32 modelHash) external {
        agentStrategies[msg.sender] = modelHash;
        emit StrategyRegistered(msg.sender, modelHash);
    }

    // ═══════════════════════════════════════════════════════════════
    // PROOF VERIFICATION
    // ═══════════════════════════════════════════════════════════════

    /**
     * @notice Request credit by proving AI decision-making
     * @param proof The SP1 ZK proof
     * @param publicValues The public outputs: [modelHash, dataHash, prediction]
     *
     * Public values layout (72 bytes):
     *   - bytes 0-31:  Model hash (bytes32)
     *   - bytes 32-63: Data hash (bytes32)
     *   - bytes 64-71: Prediction (int64, big-endian)
     */
    function requestCreditWithProof(
        bytes calldata proof,
        bytes calldata publicValues
    ) external {
        // 1. Verify the ZK proof (computation integrity)
        verifier.verifyProof(programVKey, publicValues, proof);

        // 2. Extract public values
        bytes32 provedModelHash;
        bytes32 provedDataHash;
        uint64 predictionBits;

        assembly {
            provedModelHash := calldataload(publicValues.offset)
            provedDataHash := calldataload(add(publicValues.offset, 0x20))
            // Extract big-endian u64 from bytes 64-71
            let temp := calldataload(add(publicValues.offset, 0x40))
            predictionBits := shr(192, temp)
        }

        // 3. Verify strategy binding (is this the agent's registered model?)
        require(
            provedModelHash == agentStrategies[msg.sender],
            "AIGuardian: unapproved model"
        );

        // 4. Verify the decision (did the model output a buy signal?)
        int64 predictionSigned;
        assembly {
            predictionSigned := predictionBits
        }
        require(predictionSigned > 0, "AIGuardian: no buy signal");

        // 5. Update agent stats
        verifiedInferences[msg.sender]++;
        intelligenceScores[msg.sender] += 10; // Reward for valid inference

        // 6. Emit verification event
        emit InferenceVerified(
            msg.sender,
            provedModelHash,
            provedDataHash,
            predictionSigned
        );

        // 7. Issue credit
        _issueCredit(msg.sender);
    }

    /**
     * @notice Verify inference without requesting credit
     * @dev Useful for building reputation without taking loans
     */
    function verifyInferenceOnly(
        bytes calldata proof,
        bytes calldata publicValues
    ) external returns (bool) {
        verifier.verifyProof(programVKey, publicValues, proof);

        bytes32 provedModelHash;
        assembly {
            provedModelHash := calldataload(publicValues.offset)
        }

        require(
            provedModelHash == agentStrategies[msg.sender],
            "AIGuardian: unapproved model"
        );

        verifiedInferences[msg.sender]++;
        intelligenceScores[msg.sender] += 5;

        return true;
    }

    // ═══════════════════════════════════════════════════════════════
    // INTERNAL
    // ═══════════════════════════════════════════════════════════════

    function _issueCredit(address agent) internal {
        // Calculate credit based on intelligence score
        uint256 baseCredit = 1000 * 1e6; // 1000 USDC base
        uint256 multiplier = 1 + (intelligenceScores[agent] / 100);
        uint256 creditAmount = baseCredit * multiplier;

        emit CreditIssued(agent, creditAmount);

        // In production, this would call AgentCreditLine.drawCredit()
    }

    // ═══════════════════════════════════════════════════════════════
    // VIEW FUNCTIONS
    // ═══════════════════════════════════════════════════════════════

    function getAgentStats(address agent) external view returns (
        bytes32 strategyHash,
        uint256 inferenceCount,
        uint256 intelligenceScore
    ) {
        return (
            agentStrategies[agent],
            verifiedInferences[agent],
            intelligenceScores[agent]
        );
    }

    // ═══════════════════════════════════════════════════════════════
    // SANDWICH MODEL (TEE + MPC Self-Custody)
    // ═══════════════════════════════════════════════════════════════

    /**
     * @notice Set the AgentRegistry address
     * @param _registry The AgentRegistry contract address
     */
    function setRegistry(address _registry) external {
        // In production: add onlyOwner modifier
        registry = IAgentRegistry(_registry);
        emit RegistryUpdated(_registry);
    }

    /**
     * @notice Set the Clearinghouse address
     * @param _clearinghouse The Clearinghouse contract address
     */
    function setClearinghouse(address _clearinghouse) external {
        // In production: add onlyOwner modifier
        clearinghouse = IClearinghouse(_clearinghouse);
        emit ClearinghouseUpdated(_clearinghouse);
    }

    /**
     * @notice Execute a secured action with TEE attestation + zkML proof
     * @param actionPayload The action to execute (e.g., trade parameters)
     * @param teeSignature ECDSA signature from TEE enclave (65 bytes: r, s, v)
     * @param nonce Unique nonce to prevent replay attacks
     * @param zkProof SP1 zkML proof of model inference
     * @param publicValues Public values from zkML proof
     *
     * Security Model (The Sandwich):
     *   1. TEE layer: Proves the action was computed in a secure enclave
     *   2. zkML layer: Proves the AI model produced this decision
     *   3. MPC layer: msg.sender is the MPC-derived wallet (distributed custody)
     *
     * No single point holds all keys. True self-custody.
     */
    function executeSecuredAction(
        bytes calldata actionPayload,
        bytes calldata teeSignature,
        bytes32 nonce,
        bytes calldata zkProof,
        bytes calldata publicValues
    ) external {
        // ═══════════════════════════════════════════════════════════
        // LAYER 1: MPC Wallet Verification
        // ═══════════════════════════════════════════════════════════
        require(
            address(registry) != address(0),
            "AIGuardian: registry not set"
        );
        require(
            registry.isMpcWallet(msg.sender),
            "AIGuardian: not a valid MPC agent"
        );

        // ═══════════════════════════════════════════════════════════
        // LAYER 2: Replay Protection
        // ═══════════════════════════════════════════════════════════
        require(
            !registry.usedNonces(nonce),
            "AIGuardian: nonce already used"
        );

        // ═══════════════════════════════════════════════════════════
        // LAYER 3: TEE Attestation Verification
        // ═══════════════════════════════════════════════════════════
        bytes32 expectedTeeKey = registry.agentTeePublicKey(msg.sender);
        require(
            expectedTeeKey != bytes32(0),
            "AIGuardian: no TEE key registered"
        );

        // Construct the message that TEE signed: keccak256(payload || nonce)
        bytes32 messageHash = keccak256(abi.encodePacked(actionPayload, nonce));
        bytes32 ethSignedHash = _toEthSignedMessageHash(messageHash);

        // Verify TEE signature (ECDSA with secp256k1)
        address recoveredSigner = _recoverSigner(ethSignedHash, teeSignature);
        require(
            bytes32(uint256(uint160(recoveredSigner))) == expectedTeeKey,
            "AIGuardian: TEE attestation failed"
        );

        // ═══════════════════════════════════════════════════════════
        // LAYER 4: zkML Proof Verification
        // ═══════════════════════════════════════════════════════════
        verifier.verifyProof(programVKey, publicValues, zkProof);

        // Extract and verify model hash from public values
        bytes32 provedModelHash;
        assembly {
            provedModelHash := calldataload(publicValues.offset)
        }
        require(
            provedModelHash == agentStrategies[msg.sender],
            "AIGuardian: unapproved model"
        );

        // ═══════════════════════════════════════════════════════════
        // EXECUTION: All 3 layers verified
        // ═══════════════════════════════════════════════════════════

        // Mark nonce as used (prevent replay)
        registry.markNonceUsed(nonce);

        // Update agent stats
        verifiedInferences[msg.sender]++;
        intelligenceScores[msg.sender] += 15; // Higher reward for full sandwich

        // Execute action via Clearinghouse
        if (address(clearinghouse) != address(0)) {
            clearinghouse.execute(actionPayload);
        }

        emit SandwichActionExecuted(
            msg.sender,
            keccak256(actionPayload),
            nonce
        );
    }

    // ═══════════════════════════════════════════════════════════════
    // ECDSA HELPERS (for TEE signature verification)
    // ═══════════════════════════════════════════════════════════════

    /**
     * @notice Convert to Ethereum signed message hash
     * @param messageHash The original message hash
     */
    function _toEthSignedMessageHash(bytes32 messageHash) internal pure returns (bytes32) {
        return keccak256(
            abi.encodePacked("\x19Ethereum Signed Message:\n32", messageHash)
        );
    }

    /**
     * @notice Recover signer from ECDSA signature
     * @param digest The signed message digest
     * @param signature The signature (65 bytes: r[32] || s[32] || v[1])
     */
    function _recoverSigner(
        bytes32 digest,
        bytes calldata signature
    ) internal pure returns (address) {
        require(signature.length == 65, "AIGuardian: invalid signature length");

        bytes32 r;
        bytes32 s;
        uint8 v;

        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 0x20))
            v := byte(0, calldataload(add(signature.offset, 0x40)))
        }

        // EIP-2 conformance: s must be in lower half
        require(
            uint256(s) <= 0x7FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF5D576E7357A4501DDFE92F46681B20A0,
            "AIGuardian: invalid signature 's' value"
        );

        // v must be 27 or 28
        if (v < 27) v += 27;
        require(v == 27 || v == 28, "AIGuardian: invalid signature 'v' value");

        address recovered = ecrecover(digest, v, r, s);
        require(recovered != address(0), "AIGuardian: invalid signature");

        return recovered;
    }
}
