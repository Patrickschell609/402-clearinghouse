// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title AgentRegistry - The Passport Office for AI Agents
/// @author Ghost Protocol
/// @notice Decentralized identity layer for machine-to-machine verification
/// @dev The MOAT: Fork the code, but you can't fork the registered agents
contract AgentRegistry is Ownable {

    // ============ Events ============
    event AgentRegistered(address indexed agent, bytes32 indexed identityHash, uint256 timestamp);
    event ReputationUpdated(address indexed agent, uint256 oldScore, uint256 newScore);
    event AgentSlashed(address indexed agent, uint256 penalty, string reason);
    event RootUpdated(bytes32 oldRoot, bytes32 newRoot);
    event ProtocolWhitelisted(address indexed protocol);
    event ProtocolRemoved(address indexed protocol);

    // ============ Structs ============
    struct AgentPassport {
        bytes32 identityHash;      // Merkle leaf / identity commitment
        uint256 reputation;        // Credit score (0-1000)
        uint256 registeredAt;      // Timestamp
        uint256 totalSettlements;  // Transaction count
        uint256 totalVolume;       // Lifetime volume in USDC
        bool active;               // Can be deactivated
    }

    // ============ State ============

    // The Merkle root of authorized agents (the "government database")
    bytes32 public authorizedRoot;

    // Agent address -> Passport data
    mapping(address => AgentPassport) public passports;

    // Protocols authorized to update reputation
    mapping(address => bool) public authorizedProtocols;

    // Stats
    uint256 public totalAgents;
    uint256 public totalVolume;

    // ============ Constants ============
    uint256 public constant INITIAL_REPUTATION = 100;
    uint256 public constant MAX_REPUTATION = 1000;
    uint256 public constant MIN_ELIGIBILITY = 50;

    // ============ Constructor ============
    constructor() Ownable(msg.sender) {}

    // ============ Registration (Vegan Onboarding) ============

    /// @notice Self-registration with Merkle proof - no humans required
    /// @param proof Merkle proof path
    /// @param leaf The agent's identity hash (keccak256(abi.encodePacked(msg.sender)))
    function register(bytes32[] calldata proof, bytes32 leaf) external {
        require(!passports[msg.sender].active, "Already registered");
        require(leaf == keccak256(abi.encodePacked(msg.sender)), "Invalid leaf");
        require(_verifyProof(proof, authorizedRoot, leaf), "Invalid Merkle proof");

        passports[msg.sender] = AgentPassport({
            identityHash: leaf,
            reputation: INITIAL_REPUTATION,
            registeredAt: block.timestamp,
            totalSettlements: 0,
            totalVolume: 0,
            active: true
        });

        totalAgents++;

        emit AgentRegistered(msg.sender, leaf, block.timestamp);
    }

    // ============ The API (The Moat) ============

    /// @notice Check if agent is eligible to trade - THE KEY FUNCTION
    /// @dev Other protocols (Clearinghouse, Aave, Uniswap) call this
    function checkEligibility(address agent) external view returns (bool) {
        AgentPassport storage p = passports[agent];
        return p.active && p.reputation >= MIN_ELIGIBILITY;
    }

    /// @notice Detailed eligibility check with reason
    function checkEligibilityWithReason(address agent) external view returns (bool eligible, string memory reason) {
        AgentPassport storage p = passports[agent];

        if (!p.active) return (false, "Agent not registered or deactivated");
        if (p.reputation < MIN_ELIGIBILITY) return (false, "Reputation too low");

        return (true, "Eligible");
    }

    /// @notice Get full passport data
    function getPassport(address agent) external view returns (AgentPassport memory) {
        return passports[agent];
    }

    /// @notice Simple verification check
    function isVerified(address agent) external view returns (bool) {
        return passports[agent].active;
    }

    // ============ Reputation System ============

    /// @notice Record successful settlement (called by authorized protocols)
    /// @param agent The agent that completed a trade
    /// @param volume Trade volume in USDC (6 decimals)
    function recordSettlement(address agent, uint256 volume) external {
        require(authorizedProtocols[msg.sender], "Not authorized protocol");
        require(passports[agent].active, "Agent not registered");

        AgentPassport storage p = passports[agent];
        p.totalSettlements++;
        p.totalVolume += volume;
        totalVolume += volume;

        // Reputation boost for activity (capped)
        if (p.reputation < MAX_REPUTATION) {
            uint256 boost = volume / 1_000_000; // +1 per $1M traded
            if (boost > 0) {
                uint256 oldRep = p.reputation;
                p.reputation = p.reputation + boost > MAX_REPUTATION ? MAX_REPUTATION : p.reputation + boost;
                emit ReputationUpdated(agent, oldRep, p.reputation);
            }
        }
    }

    /// @notice Slash agent reputation (for failed settlements, fraud, etc)
    /// @param agent The agent to penalize
    /// @param penalty Points to deduct
    /// @param reason Human-readable reason
    function slash(address agent, uint256 penalty, string calldata reason) external {
        require(authorizedProtocols[msg.sender] || msg.sender == owner(), "Not authorized");
        require(passports[agent].active, "Agent not registered");

        AgentPassport storage p = passports[agent];
        uint256 oldRep = p.reputation;

        if (penalty >= p.reputation) {
            p.reputation = 0;
            p.active = false; // Auto-deactivate if reputation hits 0
        } else {
            p.reputation -= penalty;
        }

        emit AgentSlashed(agent, penalty, reason);
        emit ReputationUpdated(agent, oldRep, p.reputation);
    }

    // ============ Admin Functions ============

    /// @notice Update the authorized Merkle root
    function updateRoot(bytes32 newRoot) external onlyOwner {
        emit RootUpdated(authorizedRoot, newRoot);
        authorizedRoot = newRoot;
    }

    /// @notice Whitelist a protocol to update reputation
    function whitelistProtocol(address protocol) external onlyOwner {
        authorizedProtocols[protocol] = true;
        emit ProtocolWhitelisted(protocol);
    }

    /// @notice Remove protocol from whitelist
    function removeProtocol(address protocol) external onlyOwner {
        authorizedProtocols[protocol] = false;
        emit ProtocolRemoved(protocol);
    }

    /// @notice Emergency deactivate an agent
    function deactivateAgent(address agent) external onlyOwner {
        passports[agent].active = false;
    }

    /// @notice Reactivate an agent
    function reactivateAgent(address agent) external onlyOwner {
        require(passports[agent].identityHash != bytes32(0), "Never registered");
        passports[agent].active = true;
    }

    // ============ Internal ============

    /// @notice Verify Merkle proof
    function _verifyProof(
        bytes32[] memory proof,
        bytes32 root,
        bytes32 leaf
    ) internal pure returns (bool) {
        bytes32 computedHash = leaf;

        for (uint256 i = 0; i < proof.length; i++) {
            bytes32 proofElement = proof[i];

            if (computedHash < proofElement) {
                computedHash = keccak256(abi.encodePacked(computedHash, proofElement));
            } else {
                computedHash = keccak256(abi.encodePacked(proofElement, computedHash));
            }
        }

        return computedHash == root;
    }
}
