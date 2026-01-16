// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {MultiStableSettlement} from "./MultiStableSettlement.sol";
import {SafeTransferLib} from "solady/utils/SafeTransferLib.sol";

/// @title Clearinghouse402Multi
/// @notice Multi-stablecoin clearinghouse with rate-limited withdrawals, whitelist, and batch operations
/// @dev Inherits unified settlement from MultiStableSettlement
contract Clearinghouse402Multi is MultiStableSettlement {
    using SafeTransferLib for address;

    /*//////////////////////////////////////////////////////////////
                                 ERRORS
    //////////////////////////////////////////////////////////////*/

    error ZeroAmount();
    error InsufficientBalance();
    error RateLimitExceeded();
    error TimelockActive();
    error TokenNotWhitelisted();
    error Paused();
    error NotOwner();
    error ZeroAddress();

    /*//////////////////////////////////////////////////////////////
                                 EVENTS
    //////////////////////////////////////////////////////////////*/

    event Deposit(address indexed user, address indexed token, uint256 amount, uint8 method);
    event Withdrawal(address indexed user, address indexed token, uint256 amount);
    event FeeCollected(address indexed token, uint256 amount);
    event TokenWhitelisted(address indexed token, bool allowed);
    event PauseToggled(bool paused);
    event TreasuryUpdated(address indexed newTreasury);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    /*//////////////////////////////////////////////////////////////
                                 CONSTANTS
    //////////////////////////////////////////////////////////////*/

    uint256 public constant WITHDRAWAL_WINDOW = 1 days;
    uint256 public constant MAX_WITHDRAWAL_BPS = 5000; // 50% of balance per window
    uint256 public constant FEE_BPS = 50; // 0.5% fee

    /*//////////////////////////////////////////////////////////////
                                 STORAGE
    //////////////////////////////////////////////////////////////*/

    address public owner;
    address public treasury;
    bool public paused;

    /// @notice User token balances: user => token => balance
    mapping(address => mapping(address => uint256)) public balances;

    /// @notice Deposit timestamps for timelock: user => token => timestamp
    mapping(address => mapping(address => uint256)) public depositTimestamps;

    /// @notice Whitelisted tokens
    mapping(address => bool) public whitelistedTokens;

    /// @notice Withdrawal rate limit tracking
    struct WithdrawalWindow {
        uint256 windowStart;
        uint256 withdrawnInWindow;
    }
    mapping(address => mapping(address => WithdrawalWindow)) private withdrawalWindows;

    /*//////////////////////////////////////////////////////////////
                                 MODIFIERS
    //////////////////////////////////////////////////////////////*/

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    modifier whenNotPaused() {
        if (paused) revert Paused();
        _;
    }

    modifier validToken(address token) {
        if (!whitelistedTokens[token]) revert TokenNotWhitelisted();
        _;
    }

    /*//////////////////////////////////////////////////////////////
                               CONSTRUCTOR
    //////////////////////////////////////////////////////////////*/

    constructor(address _treasury) {
        if (_treasury == address(0)) revert ZeroAddress();
        owner = msg.sender;
        treasury = _treasury;
    }

    /*//////////////////////////////////////////////////////////////
                            ADMIN FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert ZeroAddress();
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function setTreasury(address newTreasury) external onlyOwner {
        if (newTreasury == address(0)) revert ZeroAddress();
        treasury = newTreasury;
        emit TreasuryUpdated(newTreasury);
    }

    function setPaused(bool _paused) external onlyOwner {
        paused = _paused;
        emit PauseToggled(_paused);
    }

    function whitelistToken(address token, bool allowed) external onlyOwner {
        whitelistedTokens[token] = allowed;
        emit TokenWhitelisted(token, allowed);
    }

    /// @notice Batch whitelist tokens
    function whitelistTokens(address[] calldata tokens, bool allowed) external onlyOwner {
        uint256 len = tokens.length;
        for (uint256 i; i < len; ++i) {
            whitelistedTokens[tokens[i]] = allowed;
            emit TokenWhitelisted(tokens[i], allowed);
        }
    }

    /*//////////////////////////////////////////////////////////////
                            DEPOSIT FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Deposit tokens using any supported auth method
    /// @param token The stablecoin to deposit
    /// @param amount The amount to deposit
    /// @param authData Encoded authorization (method byte + payload)
    function deposit(
        address token,
        uint256 amount,
        bytes calldata authData
    ) external whenNotPaused validToken(token) {
        if (amount == 0) revert ZeroAmount();

        // Pull tokens via MultiStableSettlement
        _settle(token, msg.sender, amount, authData);

        // Calculate fee
        uint256 fee = (amount * FEE_BPS) / 10000;
        uint256 netAmount = amount - fee;

        // Credit balances
        balances[msg.sender][token] += netAmount;
        balances[treasury][token] += fee;

        // Update deposit timestamp (for timelock)
        depositTimestamps[msg.sender][token] = block.timestamp;

        emit Deposit(msg.sender, token, netAmount, uint8(authData[0]));
        if (fee > 0) emit FeeCollected(token, fee);
    }

    /// @notice Batch deposit multiple tokens in one transaction
    /// @param deposits Array of deposit instructions
    function batchDeposit(BatchDepositParams[] calldata deposits) external whenNotPaused {
        uint256 len = deposits.length;
        for (uint256 i; i < len; ++i) {
            BatchDepositParams calldata d = deposits[i];

            if (!whitelistedTokens[d.token]) revert TokenNotWhitelisted();
            if (d.amount == 0) revert ZeroAmount();

            // Pull tokens
            _settle(d.token, msg.sender, d.amount, d.authData);

            // Calculate fee
            uint256 fee = (d.amount * FEE_BPS) / 10000;
            uint256 netAmount = d.amount - fee;

            // Credit balances
            balances[msg.sender][d.token] += netAmount;
            balances[treasury][d.token] += fee;

            // Update deposit timestamp
            depositTimestamps[msg.sender][d.token] = block.timestamp;

            emit Deposit(msg.sender, d.token, netAmount, d.authData.length > 0 ? uint8(d.authData[0]) : 0);
            if (fee > 0) emit FeeCollected(d.token, fee);
        }
    }

    struct BatchDepositParams {
        address token;
        uint256 amount;
        bytes authData;
    }

    /*//////////////////////////////////////////////////////////////
                           WITHDRAWAL FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Withdraw tokens with rate limiting and timelock
    /// @param token The token to withdraw
    /// @param amount The amount to withdraw
    function withdraw(address token, uint256 amount) external whenNotPaused {
        if (amount == 0) revert ZeroAmount();

        uint256 balance = balances[msg.sender][token];
        if (amount > balance) revert InsufficientBalance();

        // Check timelock (24h after deposit)
        uint256 depositTime = depositTimestamps[msg.sender][token];
        if (depositTime > 0 && block.timestamp < depositTime + WITHDRAWAL_WINDOW) {
            revert TimelockActive();
        }

        // Check rate limit
        WithdrawalWindow storage window = withdrawalWindows[msg.sender][token];

        // Reset window if expired
        if (block.timestamp >= window.windowStart + WITHDRAWAL_WINDOW) {
            window.windowStart = block.timestamp;
            window.withdrawnInWindow = 0;
        }

        // Max withdrawal = 50% of current balance per window
        uint256 maxAllowed = (balance * MAX_WITHDRAWAL_BPS) / 10000;
        if (window.withdrawnInWindow + amount > maxAllowed) {
            revert RateLimitExceeded();
        }

        // Update state
        window.withdrawnInWindow += amount;
        balances[msg.sender][token] -= amount;

        // Transfer tokens
        token.safeTransfer(msg.sender, amount);

        emit Withdrawal(msg.sender, token, amount);
    }

    /// @notice Get withdrawal info for a user/token pair
    /// @return balance Current balance
    /// @return availableNow Amount available to withdraw now (considering rate limit)
    /// @return timelockEnds Timestamp when timelock ends (0 if no timelock)
    /// @return windowResets Timestamp when rate limit window resets
    function getWithdrawalInfo(
        address user,
        address token
    ) external view returns (
        uint256 balance,
        uint256 availableNow,
        uint256 timelockEnds,
        uint256 windowResets
    ) {
        balance = balances[user][token];

        // Timelock check
        uint256 depositTime = depositTimestamps[user][token];
        if (depositTime > 0 && block.timestamp < depositTime + WITHDRAWAL_WINDOW) {
            timelockEnds = depositTime + WITHDRAWAL_WINDOW;
            availableNow = 0;
            return (balance, availableNow, timelockEnds, 0);
        }

        // Rate limit check
        WithdrawalWindow storage window = withdrawalWindows[user][token];

        if (block.timestamp >= window.windowStart + WITHDRAWAL_WINDOW) {
            // Window expired, full 50% available
            availableNow = (balance * MAX_WITHDRAWAL_BPS) / 10000;
            windowResets = 0; // No active window
        } else {
            // Within window
            uint256 maxAllowed = (balance * MAX_WITHDRAWAL_BPS) / 10000;
            availableNow = maxAllowed > window.withdrawnInWindow
                ? maxAllowed - window.withdrawnInWindow
                : 0;
            windowResets = window.windowStart + WITHDRAWAL_WINDOW;
        }
    }

    /*//////////////////////////////////////////////////////////////
                            VIEW FUNCTIONS
    //////////////////////////////////////////////////////////////*/

    /// @notice Get user balance for a token
    function balanceOf(address user, address token) external view returns (uint256) {
        return balances[user][token];
    }

    /// @notice Get treasury balance for a token (accumulated fees)
    function treasuryBalance(address token) external view returns (uint256) {
        return balances[treasury][token];
    }

    /*//////////////////////////////////////////////////////////////
                         TREASURY WITHDRAWAL
    //////////////////////////////////////////////////////////////*/

    /// @notice Treasury can withdraw accumulated fees (no rate limit)
    /// @param token Token to withdraw
    /// @param amount Amount to withdraw
    /// @param recipient Where to send the tokens
    function treasuryWithdraw(
        address token,
        uint256 amount,
        address recipient
    ) external onlyOwner {
        if (recipient == address(0)) revert ZeroAddress();
        if (amount == 0) revert ZeroAmount();

        uint256 treasuryBal = balances[treasury][token];
        if (amount > treasuryBal) revert InsufficientBalance();

        balances[treasury][token] -= amount;
        token.safeTransfer(recipient, amount);

        emit Withdrawal(treasury, token, amount);
    }
}
