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

contract AIGuardian {
    // ═══════════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════════

    ISP1Verifier public immutable verifier;
    bytes32 public immutable programVKey;

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
}
