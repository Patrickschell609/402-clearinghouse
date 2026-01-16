// SPDX-License-Identifier: MIT
pragma solidity ^0.8.23;

import {IPermit2} from "./MultiStableSettlement.sol";

library AuthDataBuilder {
    uint8 internal constant METHOD_PERMIT2  = 0x01;
    uint8 internal constant METHOD_EIP2612  = 0x02;
    uint8 internal constant METHOD_DAI      = 0x03;
    uint8 internal constant METHOD_DIRECT   = 0x04;
    uint8 internal constant METHOD_ERC3009  = 0x05;

    function forPermit2(
        IPermit2.PermitTransferFrom memory permit,
        bytes memory signature
    ) internal pure returns (bytes memory) {
        return abi.encodePacked(
            METHOD_PERMIT2,
            abi.encode(permit, signature)
        );
    }

    function forEIP2612(
        uint256 deadline,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) internal pure returns (bytes memory) {
        return abi.encodePacked(
            METHOD_EIP2612,
            abi.encode(deadline, v, r, s)
        );
    }

    function forDaiPermit(
        uint256 nonce,
        uint256 expiry,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) internal pure returns (bytes memory) {
        return abi.encodePacked(
            METHOD_DAI,
            abi.encode(nonce, expiry, v, r, s)
        );
    }

    function forDirectTransfer() internal pure returns (bytes memory) {
        return abi.encodePacked(METHOD_DIRECT);
    }

    function forERC3009(
        uint256 validAfter,
        uint256 validBefore,
        bytes32 nonce,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) internal pure returns (bytes memory) {
        return abi.encodePacked(
            METHOD_ERC3009,
            abi.encode(validAfter, validBefore, nonce, v, r, s)
        );
    }
}
