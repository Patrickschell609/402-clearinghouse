// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {SafeTransferLib} from "solady/utils/SafeTransferLib.sol";

/// @notice Interface for Uniswap Permit2 (canonical signature transfer)
interface IPermit2 {
    struct TokenPermissions {
        address token;
        uint256 amount;
    }

    struct PermitTransferFrom {
        TokenPermissions permitted;
        uint256 nonce;
        uint256 deadline;
    }

    struct SignatureTransferDetails {
        address to;
        uint256 requestedAmount;
    }

    function permitTransferFrom(
        PermitTransferFrom memory permit,
        SignatureTransferDetails calldata transferDetails,
        address owner,
        bytes calldata signature
    ) external;
}

/// @notice Standard EIP-2612 permit interface
interface IERC20Permit {
    function permit(
        address owner,
        address spender,
        uint256 value,
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;
}

/// @notice DAI-style legacy permit interface
interface IDaiLikePermit {
    function permit(
        address holder,
        address spender,
        uint256 nonce,
        uint256 expiry,
        bool allowed,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;
}

/// @notice ERC-3009 authorization transfer (USDC, PYUSD, etc.)
interface IERC3009 {
    function transferWithAuthorization(
        address from,
        address to,
        uint256 value,
        uint256 validAfter,
        uint256 validBefore,
        bytes32 nonce,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) external;
}

error InvalidAuthData();
error ExpiredAuthorization();
error InvalidPermitData();
error UnsupportedMethod();
error SettlementFailed();

/// @title MultiStableSettlement
/// @notice Abstract contract to be inherited by settlement/receiver contracts
/// @dev Provides a single internal settlement method that handles all major
///      stablecoin authorization patterns on Base (2026)
abstract contract MultiStableSettlement {
    using SafeTransferLib for address;

    /// @dev Canonical Uniswap Permit2 address (immutable across EVM chains)
    address public constant PERMIT2 = 0x000000000022D473030F116dDEE9F6B43aC78BA3;

    uint8 private constant METHOD_PERMIT2     = 0x01;
    uint8 private constant METHOD_EIP2612     = 0x02;
    uint8 private constant METHOD_DAI         = 0x03;
    uint8 private constant METHOD_DIRECT      = 0x04;
    uint8 private constant METHOD_ERC3009     = 0x05;

    /// @notice Internal settlement function — pulls tokens directly to address(this)
    /// @param token The ERC-20 stablecoin address
    /// @param from The account authorizing and providing the tokens
    /// @param amount The amount to transfer
    /// @param authData Method selector (first byte) + encoded authorization data
    function _settle(
        address token,
        address from,
        uint256 amount,
        bytes calldata authData
    ) internal {
        if (authData.length == 0) revert InvalidAuthData();

        uint8 method = uint8(authData[0]);
        bytes calldata payload = authData[1:];

        if (method == METHOD_PERMIT2) {
            _executePermit2(token, from, amount, payload);
        } else if (method == METHOD_EIP2612) {
            _executeEIP2612(token, from, amount, payload);
        } else if (method == METHOD_DAI) {
            _executeDaiPermit(token, from, amount, payload);
        } else if (method == METHOD_DIRECT) {
            token.safeTransferFrom(from, address(this), amount);
        } else if (method == METHOD_ERC3009) {
            _executeERC3009(token, from, amount, payload);
        } else {
            revert UnsupportedMethod();
        }
    }

    function _executePermit2(
        address token,
        address from,
        uint256 amount,
        bytes calldata payload
    ) private {
        (IPermit2.PermitTransferFrom memory permit, bytes memory signature) =
            abi.decode(payload, (IPermit2.PermitTransferFrom, bytes));

        if (permit.permitted.token != token) revert InvalidPermitData();
        if (permit.permitted.amount < amount) revert InvalidPermitData();
        if (permit.deadline < block.timestamp) revert ExpiredAuthorization();

        IPermit2.SignatureTransferDetails memory details = IPermit2.SignatureTransferDetails({
            to: address(this),
            requestedAmount: amount
        });

        IPermit2(PERMIT2).permitTransferFrom(permit, details, from, signature);
    }

    function _executeEIP2612(
        address token,
        address from,
        uint256 amount,
        bytes calldata payload
    ) private {
        (uint256 deadline, uint8 v, bytes32 r, bytes32 s) =
            abi.decode(payload, (uint256, uint8, bytes32, bytes32));

        if (deadline < block.timestamp) revert ExpiredAuthorization();

        (bool success, bytes memory ret) = token.call(
            abi.encodeWithSelector(
                IERC20Permit.permit.selector,
                from,
                address(this),
                amount,
                deadline,
                v,
                r,
                s
            )
        );

        if (!success || (ret.length > 0 && !abi.decode(ret, (bool)))) {
            revert SettlementFailed();
        }

        token.safeTransferFrom(from, address(this), amount);
    }

    function _executeDaiPermit(
        address token,
        address from,
        uint256 amount,
        bytes calldata payload
    ) private {
        (uint256 nonce, uint256 expiry, uint8 v, bytes32 r, bytes32 s) =
            abi.decode(payload, (uint256, uint256, uint8, bytes32, bytes32));

        if (expiry < block.timestamp) revert ExpiredAuthorization();

        IDaiLikePermit(token).permit(from, address(this), nonce, expiry, true, v, r, s);
        token.safeTransferFrom(from, address(this), amount);
    }

    function _executeERC3009(
        address token,
        address from,
        uint256 amount,
        bytes calldata payload
    ) private {
        (
            uint256 validAfter,
            uint256 validBefore,
            bytes32 nonce,
            uint8 v,
            bytes32 r,
            bytes32 s
        ) = abi.decode(payload, (uint256, uint256, bytes32, uint8, bytes32, bytes32));

        if (block.timestamp < validAfter || block.timestamp > validBefore) {
            revert ExpiredAuthorization();
        }

        IERC3009(token).transferWithAuthorization(
            from,
            address(this),
            amount,
            validAfter,
            validBefore,
            nonce,
            v,
            r,
            s
        );
    }
}
