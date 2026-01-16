# Gnosis Safe Multisig Setup Guide

## Overview

For production deployment, all admin functions should be controlled by a multisig wallet. This guide walks through setting up a 2-of-3 Gnosis Safe on Base mainnet.

## Why Multisig?

- **No single point of failure**: Admin keys can't be compromised by one leak
- **Audit trail**: All transactions visible on-chain
- **Time to react**: Malicious transactions can be caught before execution
- **Team coordination**: Major changes require consensus

## Step 1: Generate Fresh Keys (AIRGAPPED!)

**CRITICAL: Do this on an airgapped machine!**

```bash
# On airgapped machine with foundry installed

# Owner 1 (Primary)
cast wallet new
# Save: address, private key

# Owner 2 (Secondary)
cast wallet new
# Save: address, private key

# Owner 3 (Recovery)
cast wallet new
# Save: address, private key
```

**Storage recommendations:**
- Owner 1: Hardware wallet (Ledger/Trezor)
- Owner 2: Encrypted USB in physical safe
- Owner 3: Paper wallet in safety deposit box

## Step 2: Create Safe on Base

1. Go to: https://app.safe.global/
2. Click "Create new Safe"
3. Select network: **Base**
4. Add owners:
   - Owner 1 address
   - Owner 2 address
   - Owner 3 address
5. Set threshold: **2 of 3**
6. Review and create
7. Fund Safe with small ETH for gas (~0.01 ETH)

**Record your Safe address:** `0x...`

## Step 3: Transfer Contract Ownership

After deploying contracts, transfer ownership to the Safe:

### AgentRegistry

```bash
# Current owner transfers to Safe
cast send $REGISTRY_ADDRESS "transferOwnership(address)" $SAFE_ADDRESS \
  --rpc-url https://mainnet.base.org \
  --private-key $DEPLOYER_PRIVATE_KEY
```

### AIGuardian

The AIGuardian needs an owner modifier added. For now, the deployer retains control of `setRegistry` and `setClearinghouse`. In production, add:

```solidity
address public owner;
modifier onlyOwner() { require(msg.sender == owner); _; }

function transferOwnership(address newOwner) external onlyOwner {
    owner = newOwner;
}
```

### Clearinghouse402Multi

```bash
cast send $CLEARINGHOUSE_ADDRESS "transferOwnership(address)" $SAFE_ADDRESS \
  --rpc-url https://mainnet.base.org \
  --private-key $DEPLOYER_PRIVATE_KEY
```

## Step 4: Verify Ownership Transfer

```bash
# Check AgentRegistry owner
cast call $REGISTRY_ADDRESS "owner()(address)" --rpc-url https://mainnet.base.org

# Check Clearinghouse owner
cast call $CLEARINGHOUSE_ADDRESS "owner()(address)" --rpc-url https://mainnet.base.org

# Both should return your Safe address
```

## Step 5: Test Multisig Flow

1. Go to Safe app
2. Click "New Transaction" > "Contract Interaction"
3. Enter contract address (e.g., AgentRegistry)
4. Select function: `whitelistProtocol(address)`
5. Enter a test address
6. Submit for signatures
7. Owner 1 signs
8. Owner 2 signs
9. Execute

**Verify the protocol was whitelisted:**
```bash
cast call $REGISTRY_ADDRESS "authorizedProtocols(address)(bool)" $TEST_ADDRESS \
  --rpc-url https://mainnet.base.org
```

## Admin Functions Behind Multisig

### AgentRegistry
- `updateRoot(bytes32)` - Update Merkle root
- `whitelistProtocol(address)` - Authorize protocols
- `removeProtocol(address)` - Revoke authorization
- `registerSandwichAgent(address,bytes32)` - Register TEE+MPC agents
- `deactivateAgent(address)` - Emergency deactivation
- `slash(address,uint256,string)` - Penalize bad actors

### Clearinghouse402Multi
- `setPaused(bool)` - Emergency pause
- `whitelistToken(address,bool)` - Add/remove tokens
- `setTreasury(address)` - Change fee recipient
- `treasuryWithdraw(address,uint256,address)` - Withdraw fees

## Emergency Procedures

### Pause Everything
If exploit detected:
1. Open Safe app
2. New Transaction > Contract Interaction
3. Clearinghouse402Multi: `setPaused(true)`
4. Get 2 signatures immediately
5. Execute

### Deactivate Malicious Agent
1. Safe > Contract Interaction
2. AgentRegistry: `deactivateAgent(maliciousAddress)`
3. Sign and execute

## Security Checklist

- [ ] All 3 keys generated on airgapped machine
- [ ] Keys stored in separate physical locations
- [ ] Safe created on Base mainnet
- [ ] Threshold set to 2-of-3
- [ ] Ownership transferred from deployer
- [ ] Test transaction executed successfully
- [ ] Deployer key securely destroyed or stored offline
- [ ] Safe address documented in all relevant configs

## Addresses Template

```
Safe Address:       0x...
Owner 1 (Primary):  0x...
Owner 2 (Secondary):0x...
Owner 3 (Recovery): 0x...

Contracts Owned:
- AgentRegistry:        0x...
- Clearinghouse402Multi: 0x...
```

---

**Remember:** The deployer key used for initial deployment should be rotated out after ownership transfer. Either destroy it or store it in deep cold storage as emergency backup.
