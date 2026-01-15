// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title ISP1Verifier
/// @notice Interface for Succinct SP1 proof verification
interface ISP1Verifier {
    function verifyProof(
        bytes32 programVKey,
        bytes calldata publicValues,
        bytes calldata proofBytes
    ) external view returns (bool);
}

/// @title IRWA
/// @notice Interface for RWA tokens (ERC-3643 compatible subset)
interface IRWA is IERC20 {
    function mint(address to, uint256 amount) external;
    function isVerified(address account) external view returns (bool);
}

/// @title Clearinghouse402
/// @author Ghost Protocol
/// @notice Agent-native RWA settlement layer using x402 protocol
/// @dev Non-custodial router - never holds assets beyond atomic transaction
contract Clearinghouse402 is ReentrancyGuard, Ownable, Pausable {
    using SafeERC20 for IERC20;

    // ============ Errors ============
    error InvalidProof();
    error InvalidAsset();
    error QuoteExpired();
    error InsufficientBalance();
    error TransferFailed();
    error AgentNotVerified();
    error ZeroAddress();
    error AssetAlreadyListed();
    error AssetNotListed();

    // ============ Events ============
    event Settlement(
        address indexed agent,
        address indexed asset,
        uint256 amount,
        uint256 price,
        bytes32 indexed txId
    );
    
    event AssetListed(
        address indexed asset,
        address indexed issuer,
        bytes32 complianceCircuit
    );
    
    event AssetDelisted(address indexed asset);
    event FeeUpdated(uint256 oldFee, uint256 newFee);
    event TreasuryUpdated(address oldTreasury, address newTreasury);

    // ============ Structs ============
    struct AssetConfig {
        address issuer;           // Where USDC goes
        bytes32 complianceCircuit; // SP1 program vkey
        uint256 pricePerUnit;     // Current price in USDC (6 decimals)
        bool active;
    }

    struct Quote {
        address asset;
        uint256 amount;
        uint256 totalPrice;
        uint256 expiry;
        bytes32 quoteId;
    }

    // ============ State ============
    ISP1Verifier public immutable sp1Verifier;
    IERC20 public immutable usdc;
    
    address public treasury;
    uint256 public feeBps = 5; // 0.05% = 5 basis points
    uint256 public constant MAX_FEE_BPS = 100; // 1% max
    uint256 public constant BPS_DENOMINATOR = 10_000;
    
    mapping(address => AssetConfig) public assets;
    mapping(bytes32 => bool) public usedQuotes;
    
    // Agent verification cache (from ZK proofs)
    mapping(address => uint256) public agentVerifiedUntil;

    // ============ Constructor ============
    constructor(
        address _sp1Verifier,
        address _usdc,
        address _treasury
    ) Ownable(msg.sender) {
        if (_sp1Verifier == address(0) || _usdc == address(0) || _treasury == address(0)) {
            revert ZeroAddress();
        }
        sp1Verifier = ISP1Verifier(_sp1Verifier);
        usdc = IERC20(_usdc);
        treasury = _treasury;
    }

    // ============ Core Settlement ============
    
    /// @notice Atomic settlement: verify compliance + transfer USDC + deliver RWA
    /// @param asset The RWA token address
    /// @param amount Units of RWA to purchase
    /// @param quoteExpiry Timestamp when quote expires
    /// @param complianceProof SP1 proof of investor accreditation
    /// @param publicValues Public inputs to the ZK proof
    /// @return txId Unique transaction identifier
    function settle(
        address asset,
        uint256 amount,
        uint256 quoteExpiry,
        bytes calldata complianceProof,
        bytes calldata publicValues
    ) external nonReentrant whenNotPaused returns (bytes32 txId) {
        // 1. Validate asset
        AssetConfig storage config = assets[asset];
        if (!config.active) revert InvalidAsset();
        
        // 2. Check quote expiry
        if (block.timestamp > quoteExpiry) revert QuoteExpired();
        
        // 3. Verify ZK compliance proof
        if (!_verifyCompliance(config.complianceCircuit, complianceProof, publicValues, msg.sender)) {
            revert InvalidProof();
        }
        
        // 4. Calculate costs
        uint256 totalPrice = amount * config.pricePerUnit;
        uint256 fee = (totalPrice * feeBps) / BPS_DENOMINATOR;
        uint256 issuerAmount = totalPrice - fee;
        
        // 5. Generate unique tx ID
        txId = keccak256(abi.encodePacked(
            msg.sender,
            asset,
            amount,
            block.timestamp,
            block.number
        ));
        
        // 6. Atomic transfers
        // Pull USDC from agent
        usdc.safeTransferFrom(msg.sender, address(this), totalPrice);
        
        // Route to issuer (less fee)
        usdc.safeTransfer(config.issuer, issuerAmount);
        
        // Fee to treasury
        usdc.safeTransfer(treasury, fee);
        
        // 7. Deliver RWA to agent
        // Note: In production, this would call the issuer's transfer mechanism
        // For MVP, we assume the issuer has pre-approved this contract
        IERC20(asset).safeTransferFrom(config.issuer, msg.sender, amount);
        
        // 8. Update agent verification cache
        agentVerifiedUntil[msg.sender] = block.timestamp + 30 days;
        
        emit Settlement(msg.sender, asset, amount, totalPrice, txId);
    }

    /// @notice Settle with pre-signed permit (gasless for agent)
    function settleWithPermit(
        address asset,
        uint256 amount,
        uint256 quoteExpiry,
        bytes calldata complianceProof,
        bytes calldata publicValues,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external nonReentrant whenNotPaused returns (bytes32 txId) {
        // Execute permit
        // Note: Would use IERC20Permit in production
        // IERC20Permit(address(usdc)).permit(msg.sender, address(this), type(uint256).max, deadline, v, r, s);
        
        // Then settle
        return this.settle(asset, amount, quoteExpiry, complianceProof, publicValues);
    }

    // ============ View Functions ============
    
    /// @notice Generate a quote for an agent
    /// @param asset The RWA token address
    /// @param amount Units to purchase
    /// @return quote The quote details
    function getQuote(address asset, uint256 amount) external view returns (Quote memory quote) {
        AssetConfig storage config = assets[asset];
        if (!config.active) revert InvalidAsset();
        
        uint256 totalPrice = amount * config.pricePerUnit;
        uint256 fee = (totalPrice * feeBps) / BPS_DENOMINATOR;
        
        quote = Quote({
            asset: asset,
            amount: amount,
            totalPrice: totalPrice + fee,
            expiry: block.timestamp + 5 minutes, // Short-lived quotes
            quoteId: keccak256(abi.encodePacked(asset, amount, block.timestamp))
        });
    }

    /// @notice Check if agent is currently verified
    function isAgentVerified(address agent) external view returns (bool) {
        return agentVerifiedUntil[agent] > block.timestamp;
    }

    /// @notice Get compliance circuit for an asset
    function getComplianceCircuit(address asset) external view returns (bytes32) {
        return assets[asset].complianceCircuit;
    }

    // ============ Admin Functions ============
    
    /// @notice List a new RWA asset
    function listAsset(
        address asset,
        address issuer,
        bytes32 complianceCircuit,
        uint256 pricePerUnit
    ) external onlyOwner {
        if (assets[asset].active) revert AssetAlreadyListed();
        if (asset == address(0) || issuer == address(0)) revert ZeroAddress();
        
        assets[asset] = AssetConfig({
            issuer: issuer,
            complianceCircuit: complianceCircuit,
            pricePerUnit: pricePerUnit,
            active: true
        });
        
        emit AssetListed(asset, issuer, complianceCircuit);
    }

    /// @notice Update asset price
    function updateAssetPrice(address asset, uint256 newPrice) external onlyOwner {
        if (!assets[asset].active) revert AssetNotListed();
        assets[asset].pricePerUnit = newPrice;
    }

    /// @notice Delist an asset
    function delistAsset(address asset) external onlyOwner {
        if (!assets[asset].active) revert AssetNotListed();
        assets[asset].active = false;
        emit AssetDelisted(asset);
    }

    /// @notice Update fee (max 1%)
    function setFee(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= MAX_FEE_BPS, "Fee too high");
        emit FeeUpdated(feeBps, newFeeBps);
        feeBps = newFeeBps;
    }

    /// @notice Update treasury address
    function setTreasury(address newTreasury) external onlyOwner {
        if (newTreasury == address(0)) revert ZeroAddress();
        emit TreasuryUpdated(treasury, newTreasury);
        treasury = newTreasury;
    }

    /// @notice Emergency pause - stops all settlements
    function pause() external onlyOwner {
        _pause();
    }

    /// @notice Resume operations
    function unpause() external onlyOwner {
        _unpause();
    }

    // ============ Internal Functions ============
    
    /// @notice Verify SP1 compliance proof
    function _verifyCompliance(
        bytes32 programVKey,
        bytes calldata proof,
        bytes calldata publicValues,
        address agent
    ) internal view returns (bool) {
        // Decode public values to verify agent address is committed
        (address provenAgent, uint256 accreditedUntil, bytes32 jurisdictionHash) = 
            abi.decode(publicValues, (address, uint256, bytes32));
        
        // Agent in proof must match caller
        if (provenAgent != agent) return false;
        
        // Accreditation must not be expired
        if (accreditedUntil < block.timestamp) return false;
        
        // Verify the ZK proof
        return sp1Verifier.verifyProof(programVKey, publicValues, proof);
    }
}
