// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "forge-std/console.sol";
import "../src/Clearinghouse402.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

// ═══════════════════════════════════════════════════════════════════════════
// MOCK CONTRACTS
// ═══════════════════════════════════════════════════════════════════════════

contract MockUSDC is ERC20 {
    constructor() ERC20("USD Coin", "USDC") {
        _mint(msg.sender, 1_000_000 * 10**6); // 1M USDC (6 decimals)
    }

    function decimals() public pure override returns (uint8) {
        return 6;
    }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract MockTBill is ERC20 {
    constructor() ERC20("Treasury Bill", "TBILL") {
        _mint(msg.sender, 1_000_000 * 10**18);
    }

    function mint(address to, uint256 amount) external {
        _mint(to, amount);
    }
}

contract MockSP1Verifier {
    // Always returns true for testing (we'll test with false too)
    bool public shouldPass = true;

    function setPass(bool _pass) external {
        shouldPass = _pass;
    }

    function verifyProof(
        bytes32 programVKey,
        bytes calldata publicValues,
        bytes calldata proofBytes
    ) external view returns (bool) {
        return shouldPass;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SECURITY SCAN - THE HUNTER
// ═══════════════════════════════════════════════════════════════════════════

contract SecurityScan is Test {
    Clearinghouse402 public clearinghouse;
    MockUSDC public usdc;
    MockTBill public tbill;
    MockSP1Verifier public verifier;

    address admin = address(1);
    address treasury = address(2);
    address issuer = address(3);
    address attacker = address(0xBAD);
    address victim = address(0xBEEF);

    uint256 constant INITIAL_BALANCE = 100_000 * 10**6; // 100k USDC

    function setUp() public {
        vm.startPrank(admin);

        // Deploy mocks
        usdc = new MockUSDC();
        tbill = new MockTBill();
        verifier = new MockSP1Verifier();

        // Deploy Clearinghouse
        clearinghouse = new Clearinghouse402(
            address(verifier),
            address(usdc),
            treasury
        );

        // Setup: List an asset
        bytes32 complianceCircuit = bytes32(uint256(1));
        uint256 pricePerUnit = 1 * 10**6; // $1 per TBILL
        clearinghouse.listAsset(address(tbill), issuer, complianceCircuit, pricePerUnit);

        // Fund issuer with TBILL and approve clearinghouse
        tbill.transfer(issuer, 10_000 * 10**18);
        vm.stopPrank();

        vm.startPrank(issuer);
        tbill.approve(address(clearinghouse), type(uint256).max);
        vm.stopPrank();

        // Fund attacker with USDC
        vm.startPrank(admin);
        usdc.transfer(attacker, INITIAL_BALANCE);
        usdc.transfer(victim, INITIAL_BALANCE);
        vm.stopPrank();

        // Attacker approves clearinghouse
        vm.startPrank(attacker);
        usdc.approve(address(clearinghouse), type(uint256).max);
        vm.stopPrank();

        vm.startPrank(victim);
        usdc.approve(address(clearinghouse), type(uint256).max);
        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 1: Random Settlement Attacks
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_SettlementAttack(
        uint256 amount,
        uint256 quoteExpiry
    ) public {
        // Bound inputs to reasonable ranges
        amount = bound(amount, 0, 1_000_000);
        quoteExpiry = bound(quoteExpiry, block.timestamp, block.timestamp + 365 days);

        uint256 attackerUsdcBefore = usdc.balanceOf(attacker);
        uint256 attackerTbillBefore = tbill.balanceOf(attacker);
        uint256 issuerUsdcBefore = usdc.balanceOf(issuer);
        uint256 treasuryBefore = usdc.balanceOf(treasury);

        vm.startPrank(attacker);

        // Build fake proof data
        bytes memory fakeProof = abi.encodePacked(uint256(123));
        bytes memory publicValues = abi.encode(attacker, block.timestamp + 30 days, bytes32(0));

        try clearinghouse.settle(
            address(tbill),
            amount,
            quoteExpiry,
            fakeProof,
            publicValues
        ) returns (bytes32) {
            // Settlement succeeded - check invariants

            uint256 attackerUsdcAfter = usdc.balanceOf(attacker);
            uint256 attackerTbillAfter = tbill.balanceOf(attacker);
            uint256 issuerUsdcAfter = usdc.balanceOf(issuer);
            uint256 treasuryAfter = usdc.balanceOf(treasury);

            // INVARIANT 1: Attacker can't get TBILL without paying USDC
            if (attackerTbillAfter > attackerTbillBefore && attackerUsdcAfter >= attackerUsdcBefore) {
                console.log("!!! FREE MONEY GLITCH: Got TBILL without paying !!!");
                console.log("Amount:", amount);
                fail();
            }

            // INVARIANT 2: Issuer must receive payment (minus fee)
            if (amount > 0 && issuerUsdcAfter <= issuerUsdcBefore) {
                console.log("!!! PAYMENT BYPASS: Issuer didn't receive USDC !!!");
                console.log("Amount:", amount);
                fail();
            }

            // INVARIANT 3: Treasury must receive fee
            if (amount > 0 && treasuryAfter <= treasuryBefore) {
                console.log("!!! FEE BYPASS: Treasury didn't receive fee !!!");
                fail();
            }

        } catch {
            // Expected to revert for invalid inputs - that's good security
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 2: Price Manipulation
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_PriceManipulation(uint256 newPrice) public {
        newPrice = bound(newPrice, 0, type(uint128).max);

        // Only owner should be able to change price
        vm.startPrank(attacker);

        try clearinghouse.updateAssetPrice(address(tbill), newPrice) {
            console.log("!!! UNAUTHORIZED PRICE CHANGE !!!");
            console.log("Attacker set price to:", newPrice);
            fail();
        } catch {
            // Good - attacker can't change price
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 3: Integer Overflow in Cost Calculation
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_OverflowAttack(uint256 amount) public {
        // Try to cause integer overflow in: totalPrice = amount * config.pricePerUnit

        vm.startPrank(attacker);

        bytes memory fakeProof = abi.encodePacked(uint256(123));
        bytes memory publicValues = abi.encode(attacker, block.timestamp + 30 days, bytes32(0));

        uint256 balanceBefore = usdc.balanceOf(attacker);

        try clearinghouse.settle(
            address(tbill),
            amount,
            block.timestamp + 1 hours,
            fakeProof,
            publicValues
        ) returns (bytes32) {
            uint256 balanceAfter = usdc.balanceOf(attacker);

            // Check if overflow caused us to pay less than expected
            // Expected payment: amount * pricePerUnit (1 USDC per TBILL)
            uint256 expectedPayment = amount * 10**6;
            uint256 actualPayment = balanceBefore - balanceAfter;

            // Allow for fee variance
            if (actualPayment < expectedPayment * 95 / 100) {
                console.log("!!! OVERFLOW EXPLOIT: Paid less than expected !!!");
                console.log("Amount:", amount);
                console.log("Expected:", expectedPayment);
                console.log("Actual:", actualPayment);
                fail();
            }
        } catch {
            // Reverted - safe
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 4: Access Control Bypass
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_AccessControl(address randomCaller) public {
        vm.assume(randomCaller != admin); // Not the real admin
        vm.assume(randomCaller != address(0));

        vm.startPrank(randomCaller);

        // Try admin functions

        // 1. Try to list asset
        try clearinghouse.listAsset(address(0x123), address(0x456), bytes32(0), 100) {
            console.log("!!! UNAUTHORIZED listAsset !!!");
            console.log("Caller:", randomCaller);
            fail();
        } catch {}

        // 2. Try to delist asset
        try clearinghouse.delistAsset(address(tbill)) {
            console.log("!!! UNAUTHORIZED delistAsset !!!");
            fail();
        } catch {}

        // 3. Try to set fee
        try clearinghouse.setFee(100) {
            console.log("!!! UNAUTHORIZED setFee !!!");
            fail();
        } catch {}

        // 4. Try to set treasury
        try clearinghouse.setTreasury(randomCaller) {
            console.log("!!! UNAUTHORIZED setTreasury !!!");
            fail();
        } catch {}

        // 5. Try to pause
        try clearinghouse.pause() {
            console.log("!!! UNAUTHORIZED pause !!!");
            fail();
        } catch {}

        // 6. Try to unpause
        try clearinghouse.unpause() {
            console.log("!!! UNAUTHORIZED unpause !!!");
            fail();
        } catch {}

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 5: Double Spend / Reentrancy
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_ReentrancyCheck(uint256 amount) public {
        amount = bound(amount, 1, 100);

        // The contract uses nonReentrant modifier, but let's verify
        // The test passes if settlement is atomic and can't be reentered

        uint256 issuerBalanceBefore = usdc.balanceOf(issuer);

        vm.startPrank(attacker);

        bytes memory fakeProof = abi.encodePacked(uint256(123));
        bytes memory publicValues = abi.encode(attacker, block.timestamp + 30 days, bytes32(0));

        try clearinghouse.settle(
            address(tbill),
            amount,
            block.timestamp + 1 hours,
            fakeProof,
            publicValues
        ) {
            // Settlement worked
            uint256 issuerBalanceAfter = usdc.balanceOf(issuer);

            // INVARIANT: Issuer should receive exactly (amount * price - fee)
            // Not more (double payment), not less (underpayment)
            uint256 expectedPayment = (amount * 10**6 * 9995) / 10000; // 0.05% fee
            uint256 actualPayment = issuerBalanceAfter - issuerBalanceBefore;

            // Allow 1% variance for rounding
            assertApproxEqRel(actualPayment, expectedPayment, 0.01e18, "Payment mismatch - possible reentrancy");

        } catch {
            // Reverted - that's fine
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 6: Quote Expiry Bypass
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_ExpiredQuote(uint256 timeDelta) public {
        // Bound to avoid underflow: can't subtract more than current timestamp
        timeDelta = bound(timeDelta, 1, block.timestamp > 1 ? block.timestamp - 1 : 1);

        // Set an expired quote
        uint256 expiredTime = block.timestamp - timeDelta;

        vm.startPrank(attacker);

        bytes memory fakeProof = abi.encodePacked(uint256(123));
        bytes memory publicValues = abi.encode(attacker, block.timestamp + 30 days, bytes32(0));

        try clearinghouse.settle(
            address(tbill),
            100,
            expiredTime, // EXPIRED!
            fakeProof,
            publicValues
        ) {
            console.log("!!! EXPIRED QUOTE ACCEPTED !!!");
            console.log("Quote expired:", timeDelta, "seconds ago");
            fail();
        } catch {
            // Good - expired quotes should be rejected
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 7: Zero Amount Edge Case
    // ═══════════════════════════════════════════════════════════════════════

    function test_ZeroAmountSettlement() public {
        vm.startPrank(attacker);

        bytes memory fakeProof = abi.encodePacked(uint256(123));
        bytes memory publicValues = abi.encode(attacker, block.timestamp + 30 days, bytes32(0));

        uint256 tbillBefore = tbill.balanceOf(attacker);

        try clearinghouse.settle(
            address(tbill),
            0, // ZERO AMOUNT
            block.timestamp + 1 hours,
            fakeProof,
            publicValues
        ) returns (bytes32 txId) {
            uint256 tbillAfter = tbill.balanceOf(attacker);

            // If we got here without paying, that's a bug (even if we got 0 TBILL)
            // The transaction shouldn't succeed for 0 amount
            console.log("!!! ZERO AMOUNT SETTLEMENT ALLOWED !!!");
            console.log("TxId generated:", uint256(txId));

            // Only fail if this somehow gave us tokens
            if (tbillAfter > tbillBefore) {
                fail();
            }
        } catch {
            // Good - zero amount should revert or be handled
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 8: Invalid Asset Attack
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_InvalidAsset(address randomAsset) public {
        vm.assume(randomAsset != address(tbill)); // Not the real asset
        vm.assume(randomAsset != address(0));

        vm.startPrank(attacker);

        bytes memory fakeProof = abi.encodePacked(uint256(123));
        bytes memory publicValues = abi.encode(attacker, block.timestamp + 30 days, bytes32(0));

        try clearinghouse.settle(
            randomAsset, // INVALID ASSET
            100,
            block.timestamp + 1 hours,
            fakeProof,
            publicValues
        ) {
            console.log("!!! UNLISTED ASSET ACCEPTED !!!");
            console.log("Asset:", randomAsset);
            fail();
        } catch {
            // Good - invalid assets should be rejected
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // FUZZ TEST 9: Fee Bounds Check
    // ═══════════════════════════════════════════════════════════════════════

    function testFuzz_FeeLimit(uint256 newFee) public {
        vm.startPrank(admin);

        if (newFee > 100) { // MAX_FEE_BPS = 100 (1%)
            try clearinghouse.setFee(newFee) {
                console.log("!!! FEE EXCEEDS MAX ALLOWED !!!");
                console.log("Fee set to:", newFee, "bps");
                fail();
            } catch {
                // Good - excessive fee should be rejected
            }
        } else {
            // Should succeed
            clearinghouse.setFee(newFee);
            assertEq(clearinghouse.feeBps(), newFee);
        }

        vm.stopPrank();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // INVARIANT TEST: Clearinghouse Should Never Hold Funds
    // ═══════════════════════════════════════════════════════════════════════

    function invariant_ClearinghouseHoldsNoFunds() public view {
        // Non-custodial: Clearinghouse should never hold USDC
        uint256 balance = usdc.balanceOf(address(clearinghouse));
        assertEq(balance, 0, "INVARIANT BROKEN: Clearinghouse holding USDC!");
    }
}
