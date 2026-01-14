// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title IAgentRegistry
interface IAgentRegistry {
    function checkEligibility(address agent) external view returns (bool);
    function passports(address agent) external view returns (
        bytes32 identityHash,
        uint256 reputation,
        uint256 registeredAt,
        uint256 totalSettlements,
        uint256 totalVolume,
        bool active
    );
    function recordSettlement(address agent, uint256 volume) external;
}

/// @title AgentCreditLine - The Bank for AI Agents
/// @author Ghost Protocol
/// @notice Under-collateralized lending based on reputation scores
/// @dev Reputation IS collateral. High score = higher leverage.
contract AgentCreditLine is ReentrancyGuard, Ownable {
    using SafeERC20 for IERC20;

    // ============ Events ============
    event Deposited(address indexed lp, uint256 amount, uint256 shares);
    event Withdrawn(address indexed lp, uint256 shares, uint256 amount);
    event Borrowed(address indexed agent, uint256 amount, uint256 totalDebt);
    event Repaid(address indexed agent, uint256 amount, uint256 remaining);
    event Liquidated(address indexed agent, uint256 debt, address indexed liquidator);
    event InterestAccrued(address indexed agent, uint256 interest);

    // ============ Errors ============
    error NotEligible();
    error InsufficientCredit();
    error InsufficientLiquidity();
    error NoDebt();
    error NotLiquidatable();
    error ZeroAmount();

    // ============ Structs ============
    struct CreditAccount {
        uint256 principal;          // Original borrowed amount
        uint256 interestAccrued;    // Accumulated interest
        uint256 lastUpdate;         // Last interest calculation
        uint256 collateralStaked;   // Optional: USDC staked as collateral
    }

    // ============ State ============
    IAgentRegistry public immutable registry;
    IERC20 public immutable usdc;

    // LP shares (simple vault model)
    mapping(address => uint256) public lpShares;
    uint256 public totalShares;
    uint256 public totalDeposits;

    // Agent credit accounts
    mapping(address => CreditAccount) public accounts;
    uint256 public totalBorrowed;

    // Interest rate: 5% APR = 500 basis points
    uint256 public interestRateBps = 500;
    uint256 public constant BPS = 10_000;
    uint256 public constant SECONDS_PER_YEAR = 365 days;

    // Credit tiers based on reputation
    // Score 50-79:  1x leverage (100% collateralized)
    // Score 80-94:  3x leverage (33% collateral required)
    // Score 95-100: 5x leverage (20% collateral) - the "trust tier"
    uint256 public constant TIER1_THRESHOLD = 50;
    uint256 public constant TIER2_THRESHOLD = 80;
    uint256 public constant TIER3_THRESHOLD = 95;

    uint256 public constant TIER1_LEVERAGE = 1;  // 1x
    uint256 public constant TIER2_LEVERAGE = 3;  // 3x
    uint256 public constant TIER3_LEVERAGE = 5;  // 5x

    // Liquidation threshold: 120% of debt
    uint256 public constant LIQUIDATION_THRESHOLD = 12000; // 120% in bps

    // ============ Constructor ============
    constructor(
        address _registry,
        address _usdc
    ) Ownable(msg.sender) {
        registry = IAgentRegistry(_registry);
        usdc = IERC20(_usdc);
    }

    // ============ LP Functions ============

    /// @notice Deposit USDC to earn yield from agent borrowing
    function deposit(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        // Calculate shares
        uint256 shares;
        if (totalShares == 0) {
            shares = amount;
        } else {
            shares = (amount * totalShares) / totalDeposits;
        }

        usdc.safeTransferFrom(msg.sender, address(this), amount);

        lpShares[msg.sender] += shares;
        totalShares += shares;
        totalDeposits += amount;

        emit Deposited(msg.sender, amount, shares);
    }

    /// @notice Withdraw USDC + earned interest
    function withdraw(uint256 shares) external nonReentrant {
        if (shares == 0) revert ZeroAmount();
        require(lpShares[msg.sender] >= shares, "Insufficient shares");

        // Calculate amount (includes interest earned)
        uint256 amount = (shares * totalDeposits) / totalShares;

        // Check liquidity
        uint256 available = usdc.balanceOf(address(this));
        if (amount > available) revert InsufficientLiquidity();

        lpShares[msg.sender] -= shares;
        totalShares -= shares;
        totalDeposits -= amount;

        usdc.safeTransfer(msg.sender, amount);

        emit Withdrawn(msg.sender, shares, amount);
    }

    // ============ Agent Credit Functions ============

    /// @notice Stake collateral to increase credit limit
    function stakeCollateral(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        usdc.safeTransferFrom(msg.sender, address(this), amount);
        accounts[msg.sender].collateralStaked += amount;
    }

    /// @notice Withdraw excess collateral
    function unstakeCollateral(uint256 amount) external nonReentrant {
        CreditAccount storage account = accounts[msg.sender];

        // Calculate required collateral
        uint256 totalDebt = account.principal + account.interestAccrued;
        uint256 requiredCollateral = _getRequiredCollateral(msg.sender, totalDebt);

        require(account.collateralStaked >= requiredCollateral + amount, "Would undercollateralize");

        account.collateralStaked -= amount;
        usdc.safeTransfer(msg.sender, amount);
    }

    /// @notice Borrow USDC against reputation + collateral
    function borrow(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        // Check registry eligibility
        if (!registry.checkEligibility(msg.sender)) revert NotEligible();

        // Accrue interest on existing debt
        _accrueInterest(msg.sender);

        // Get credit limit
        uint256 limit = getCreditLimit(msg.sender);
        CreditAccount storage account = accounts[msg.sender];
        uint256 currentDebt = account.principal + account.interestAccrued;

        if (currentDebt + amount > limit) revert InsufficientCredit();

        // Check liquidity
        if (amount > usdc.balanceOf(address(this))) revert InsufficientLiquidity();

        // Update state
        account.principal += amount;
        account.lastUpdate = block.timestamp;
        totalBorrowed += amount;

        // Transfer
        usdc.safeTransfer(msg.sender, amount);

        emit Borrowed(msg.sender, amount, account.principal + account.interestAccrued);
    }

    /// @notice Repay debt (principal + interest)
    function repay(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        CreditAccount storage account = accounts[msg.sender];
        _accrueInterest(msg.sender);

        uint256 totalDebt = account.principal + account.interestAccrued;
        if (totalDebt == 0) revert NoDebt();

        // Cap repayment at total debt
        uint256 repayAmount = amount > totalDebt ? totalDebt : amount;

        usdc.safeTransferFrom(msg.sender, address(this), repayAmount);

        // Pay interest first, then principal
        if (repayAmount <= account.interestAccrued) {
            account.interestAccrued -= repayAmount;
            totalDeposits += repayAmount; // Interest goes to LPs
        } else {
            uint256 interestPaid = account.interestAccrued;
            uint256 principalPaid = repayAmount - interestPaid;

            totalDeposits += interestPaid; // Interest to LPs
            account.interestAccrued = 0;
            account.principal -= principalPaid;
            totalBorrowed -= principalPaid;
        }

        emit Repaid(msg.sender, repayAmount, account.principal + account.interestAccrued);
    }

    /// @notice Liquidate undercollateralized position
    function liquidate(address agent) external nonReentrant {
        CreditAccount storage account = accounts[agent];
        _accrueInterest(agent);

        uint256 totalDebt = account.principal + account.interestAccrued;
        if (totalDebt == 0) revert NoDebt();

        // Check if liquidatable
        uint256 collateralValue = account.collateralStaked;
        uint256 healthFactor = (collateralValue * BPS) / totalDebt;

        // Can only liquidate if health factor < 120%
        if (healthFactor >= LIQUIDATION_THRESHOLD) revert NotLiquidatable();

        // Liquidator pays debt, receives collateral
        usdc.safeTransferFrom(msg.sender, address(this), totalDebt);

        // Transfer collateral to liquidator (they profit if collateral > debt)
        uint256 collateralToLiquidator = account.collateralStaked;
        account.collateralStaked = 0;
        account.principal = 0;
        account.interestAccrued = 0;
        totalBorrowed -= account.principal;

        usdc.safeTransfer(msg.sender, collateralToLiquidator);

        // Slash reputation in registry (if we have permission)
        // registry.slash(agent, 20, "Liquidated");

        emit Liquidated(agent, totalDebt, msg.sender);
    }

    // ============ View Functions ============

    /// @notice Get agent's credit limit based on reputation + collateral
    function getCreditLimit(address agent) public view returns (uint256) {
        (, uint256 reputation,,,, bool active) = registry.passports(agent);

        if (!active) return 0;

        uint256 collateral = accounts[agent].collateralStaked;
        uint256 leverage;

        if (reputation >= TIER3_THRESHOLD) {
            leverage = TIER3_LEVERAGE; // 5x
        } else if (reputation >= TIER2_THRESHOLD) {
            leverage = TIER2_LEVERAGE; // 3x
        } else if (reputation >= TIER1_THRESHOLD) {
            leverage = TIER1_LEVERAGE; // 1x
        } else {
            return 0; // No credit
        }

        return collateral * leverage;
    }

    /// @notice Get agent's current debt (principal + accrued interest)
    function getDebt(address agent) external view returns (uint256 principal, uint256 interest, uint256 total) {
        CreditAccount storage account = accounts[agent];
        principal = account.principal;

        // Calculate pending interest
        if (account.principal > 0 && account.lastUpdate > 0) {
            uint256 timeElapsed = block.timestamp - account.lastUpdate;
            uint256 pendingInterest = (account.principal * interestRateBps * timeElapsed) / (BPS * SECONDS_PER_YEAR);
            interest = account.interestAccrued + pendingInterest;
        } else {
            interest = account.interestAccrued;
        }

        total = principal + interest;
    }

    /// @notice Get health factor (collateral / debt ratio)
    function getHealthFactor(address agent) external view returns (uint256) {
        CreditAccount storage account = accounts[agent];
        uint256 totalDebt = account.principal + account.interestAccrued;

        if (totalDebt == 0) return type(uint256).max;

        return (account.collateralStaked * BPS) / totalDebt;
    }

    /// @notice Get vault stats
    function getVaultStats() external view returns (
        uint256 _totalDeposits,
        uint256 _totalBorrowed,
        uint256 _utilization,
        uint256 _availableLiquidity
    ) {
        _totalDeposits = totalDeposits;
        _totalBorrowed = totalBorrowed;
        _utilization = totalDeposits > 0 ? (totalBorrowed * BPS) / totalDeposits : 0;
        _availableLiquidity = usdc.balanceOf(address(this));
    }

    // ============ Internal ============

    function _accrueInterest(address agent) internal {
        CreditAccount storage account = accounts[agent];

        if (account.principal > 0 && account.lastUpdate > 0) {
            uint256 timeElapsed = block.timestamp - account.lastUpdate;
            uint256 interest = (account.principal * interestRateBps * timeElapsed) / (BPS * SECONDS_PER_YEAR);

            if (interest > 0) {
                account.interestAccrued += interest;
                emit InterestAccrued(agent, interest);
            }
        }

        account.lastUpdate = block.timestamp;
    }

    function _getRequiredCollateral(address agent, uint256 debt) internal view returns (uint256) {
        (, uint256 reputation,,,, bool active) = registry.passports(agent);

        if (!active || debt == 0) return 0;

        uint256 leverage;
        if (reputation >= TIER3_THRESHOLD) {
            leverage = TIER3_LEVERAGE;
        } else if (reputation >= TIER2_THRESHOLD) {
            leverage = TIER2_LEVERAGE;
        } else {
            leverage = TIER1_LEVERAGE;
        }

        return debt / leverage;
    }

    // ============ Admin ============

    function setInterestRate(uint256 newRateBps) external onlyOwner {
        require(newRateBps <= 2000, "Rate too high"); // Max 20% APR
        interestRateBps = newRateBps;
    }
}
