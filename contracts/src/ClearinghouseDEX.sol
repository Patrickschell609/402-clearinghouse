// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title ISP1Verifier
interface ISP1Verifier {
    function verifyProof(
        bytes32 programVKey,
        bytes calldata publicValues,
        bytes calldata proofBytes
    ) external view returns (bool);
}

/// @title IAerodromeRouter
/// @notice Aerodrome DEX router interface
interface IAerodromeRouter {
    struct Route {
        address from;
        address to;
        bool stable;
        address factory;
    }

    function swapExactTokensForTokens(
        uint256 amountIn,
        uint256 amountOutMin,
        Route[] calldata routes,
        address to,
        uint256 deadline
    ) external returns (uint256[] memory amounts);

    function getAmountsOut(
        uint256 amountIn,
        Route[] calldata routes
    ) external view returns (uint256[] memory amounts);
}

/// @title ClearinghouseDEX
/// @author Ghost Protocol
/// @notice Non-custodial RWA settlement via DEX routing
/// @dev Routes USDC → any asset through Aerodrome. Never holds funds.
contract ClearinghouseDEX is ReentrancyGuard, Ownable {
    using SafeERC20 for IERC20;

    // ============ Errors ============
    error InvalidProof();
    error QuoteExpired();
    error SlippageExceeded();
    error ZeroAddress();
    error ZeroAmount();
    error AssetNotWhitelisted();

    // ============ Events ============
    event Settlement(
        address indexed agent,
        address indexed assetOut,
        uint256 amountIn,
        uint256 amountOut,
        uint256 fee,
        bytes32 indexed txId
    );

    event AssetWhitelisted(address indexed asset, bool stable);
    event AssetRemoved(address indexed asset);
    event FeeUpdated(uint256 oldFee, uint256 newFee);

    // ============ State ============
    ISP1Verifier public immutable sp1Verifier;
    IAerodromeRouter public immutable router;
    IERC20 public immutable usdc;
    address public immutable aerodromeFactory;

    address public treasury;
    uint256 public feeBps = 5; // 0.05%
    uint256 public constant MAX_FEE_BPS = 100; // 1% max
    uint256 public constant BPS_DENOMINATOR = 10_000;

    // Compliance circuit for all trades (single KYC requirement)
    bytes32 public complianceCircuit;

    // Whitelisted output assets (prevent routing to malicious tokens)
    mapping(address => bool) public whitelistedAssets;
    mapping(address => bool) public isStablePool; // USDC/USDT = stable, USDC/BTC = volatile

    // Agent verification cache
    mapping(address => uint256) public agentVerifiedUntil;

    // ============ Constructor ============
    constructor(
        address _sp1Verifier,
        address _router,
        address _usdc,
        address _aerodromeFactory,
        address _treasury,
        bytes32 _complianceCircuit
    ) Ownable(msg.sender) {
        if (_sp1Verifier == address(0) || _router == address(0) ||
            _usdc == address(0) || _treasury == address(0)) {
            revert ZeroAddress();
        }

        sp1Verifier = ISP1Verifier(_sp1Verifier);
        router = IAerodromeRouter(_router);
        usdc = IERC20(_usdc);
        aerodromeFactory = _aerodromeFactory;
        treasury = _treasury;
        complianceCircuit = _complianceCircuit;

        // Pre-approve router for USDC (gas optimization)
        IERC20(_usdc).approve(_router, type(uint256).max);
    }

    // ============ Core Settlement ============

    /// @notice Atomic settlement: USDC → any whitelisted asset via DEX
    /// @param assetOut The token to receive
    /// @param amountIn USDC amount to spend (6 decimals)
    /// @param minAmountOut Minimum output (slippage protection)
    /// @param complianceProof SP1 ZK proof
    /// @param publicValues Public inputs to proof
    /// @return txId Unique transaction ID
    /// @return amountOut Actual tokens received
    function settle(
        address assetOut,
        uint256 amountIn,
        uint256 minAmountOut,
        bytes calldata complianceProof,
        bytes calldata publicValues
    ) external nonReentrant returns (bytes32 txId, uint256 amountOut) {
        // 1. Validate
        if (amountIn == 0) revert ZeroAmount();
        if (!whitelistedAssets[assetOut]) revert AssetNotWhitelisted();

        // 2. Verify ZK compliance
        if (!_verifyCompliance(complianceProof, publicValues, msg.sender)) {
            revert InvalidProof();
        }

        // 3. Calculate fee
        uint256 fee = (amountIn * feeBps) / BPS_DENOMINATOR;
        uint256 swapAmount = amountIn - fee;

        // 4. Pull USDC from agent
        usdc.safeTransferFrom(msg.sender, address(this), amountIn);

        // 5. Send fee to treasury
        usdc.safeTransfer(treasury, fee);

        // 6. Build route and swap
        IAerodromeRouter.Route[] memory routes = new IAerodromeRouter.Route[](1);
        routes[0] = IAerodromeRouter.Route({
            from: address(usdc),
            to: assetOut,
            stable: isStablePool[assetOut],
            factory: aerodromeFactory
        });

        uint256[] memory amounts = router.swapExactTokensForTokens(
            swapAmount,
            minAmountOut,
            routes,
            msg.sender, // Send directly to agent
            block.timestamp + 300 // 5 min deadline
        );

        amountOut = amounts[amounts.length - 1];

        // 7. Verify slippage
        if (amountOut < minAmountOut) revert SlippageExceeded();

        // 8. Generate tx ID
        txId = keccak256(abi.encodePacked(
            msg.sender,
            assetOut,
            amountIn,
            amountOut,
            block.timestamp,
            block.number
        ));

        // 9. Update verification cache
        agentVerifiedUntil[msg.sender] = block.timestamp + 30 days;

        emit Settlement(msg.sender, assetOut, amountIn, amountOut, fee, txId);
    }

    // ============ View Functions ============

    /// @notice Get quote for a swap
    /// @param assetOut Token to receive
    /// @param amountIn USDC to spend
    /// @return amountOut Expected output
    /// @return fee Protocol fee
    function getQuote(
        address assetOut,
        uint256 amountIn
    ) external view returns (uint256 amountOut, uint256 fee) {
        if (!whitelistedAssets[assetOut]) revert AssetNotWhitelisted();

        fee = (amountIn * feeBps) / BPS_DENOMINATOR;
        uint256 swapAmount = amountIn - fee;

        IAerodromeRouter.Route[] memory routes = new IAerodromeRouter.Route[](1);
        routes[0] = IAerodromeRouter.Route({
            from: address(usdc),
            to: assetOut,
            stable: isStablePool[assetOut],
            factory: aerodromeFactory
        });

        uint256[] memory amounts = router.getAmountsOut(swapAmount, routes);
        amountOut = amounts[amounts.length - 1];
    }

    /// @notice Check agent verification status
    function isAgentVerified(address agent) external view returns (bool) {
        return agentVerifiedUntil[agent] > block.timestamp;
    }

    // ============ Admin Functions ============

    /// @notice Whitelist an asset for trading
    /// @param asset Token address
    /// @param stable True if USDC/asset pool is stable (stablecoins)
    function whitelistAsset(address asset, bool stable) external onlyOwner {
        if (asset == address(0)) revert ZeroAddress();
        whitelistedAssets[asset] = true;
        isStablePool[asset] = stable;
        emit AssetWhitelisted(asset, stable);
    }

    /// @notice Remove asset from whitelist
    function removeAsset(address asset) external onlyOwner {
        whitelistedAssets[asset] = false;
        emit AssetRemoved(asset);
    }

    /// @notice Update protocol fee
    function setFee(uint256 newFeeBps) external onlyOwner {
        require(newFeeBps <= MAX_FEE_BPS, "Fee too high");
        emit FeeUpdated(feeBps, newFeeBps);
        feeBps = newFeeBps;
    }

    /// @notice Update treasury
    function setTreasury(address newTreasury) external onlyOwner {
        if (newTreasury == address(0)) revert ZeroAddress();
        treasury = newTreasury;
    }

    /// @notice Update compliance circuit
    function setComplianceCircuit(bytes32 newCircuit) external onlyOwner {
        complianceCircuit = newCircuit;
    }

    // ============ Internal ============

    function _verifyCompliance(
        bytes calldata proof,
        bytes calldata publicValues,
        address agent
    ) internal view returns (bool) {
        // Decode public values
        (address provenAgent, uint256 validUntil, ) =
            abi.decode(publicValues, (address, uint256, bytes32));

        // Agent must match
        if (provenAgent != agent) return false;

        // Must not be expired
        if (validUntil < block.timestamp) return false;

        // Verify ZK proof
        return sp1Verifier.verifyProof(complianceCircuit, publicValues, proof);
    }

    /// @notice Emergency: recover stuck tokens (not USDC)
    function rescueTokens(address token, uint256 amount) external onlyOwner {
        require(token != address(usdc), "Cannot rescue USDC");
        IERC20(token).safeTransfer(owner(), amount);
    }
}
