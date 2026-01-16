# Production Deployment Checklist

## Pre-Deployment

### Code Review
- [ ] All contracts compiled without errors
- [ ] Security tests pass (SandwichSecurityTest: 5/5)
- [ ] No compiler warnings on critical paths
- [ ] Slither/Mythril scan clean (or findings addressed)
- [ ] Manual review of all `external`/`public` functions

### Environment
- [ ] Fresh deployer wallet created (not reused)
- [ ] Deployer funded with ETH (~0.05 ETH for all deployments)
- [ ] PRIVATE_KEY exported correctly
- [ ] BASESCAN_API_KEY set (for verification)
- [ ] RPC endpoint tested (`cast block-number --rpc-url https://mainnet.base.org`)

### Dependencies
- [ ] Foundry updated to latest (`foundryup`)
- [ ] All dependencies installed (`forge install`)
- [ ] Remappings correct in foundry.toml

---

## Deployment: Sandwich Model

### Deploy AgentRegistry
```bash
./deploy_sandwich.sh
```

- [ ] Transaction confirmed
- [ ] Contract verified on BaseScan
- [ ] `owner()` returns deployer address

**Address:** `_____________________________`

### Deploy AIGuardian
- [ ] Correct SP1 Verifier address used
- [ ] Correct program vKey used
- [ ] Transaction confirmed
- [ ] Contract verified on BaseScan

**Address:** `_____________________________`

### Configuration
- [ ] `AIGuardian.setRegistry()` called
- [ ] `AgentRegistry.whitelistProtocol(guardian)` called
- [ ] Verify: `registry.authorizedProtocols(guardian)` returns `true`

---

## Deployment: Clearinghouse402Multi

### Deploy Clearinghouse
```bash
./deploy_multistable.sh
```

- [ ] Transaction confirmed
- [ ] Contract verified on BaseScan
- [ ] Treasury set correctly
- [ ] Paused = false

**Address:** `_____________________________`

### Token Whitelist
- [ ] USDC whitelisted
- [ ] USDT whitelisted
- [ ] DAI whitelisted
- [ ] PYUSD whitelisted

Verify:
```bash
cast call $CLEARINGHOUSE "whitelistedTokens(address)(bool)" 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 --rpc-url https://mainnet.base.org
```

---

## Post-Deployment Verification

### Functional Tests

#### 1. Register Sandwich Agent
```bash
# Register test agent
cast send $REGISTRY "registerSandwichAgent(address,bytes32)" \
  0xTEST_MPC_ADDRESS \
  0xTEST_TEE_PUBKEY \
  --rpc-url https://mainnet.base.org \
  --private-key $PRIVATE_KEY
```

- [ ] Transaction succeeded
- [ ] `isMpcWallet(testAddress)` returns `true`
- [ ] `agentTeePublicKey(testAddress)` returns correct key

#### 2. Test Deposit (Small Amount)
```bash
# Approve USDC
cast send 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  "approve(address,uint256)" $CLEARINGHOUSE 1000000 \
  --rpc-url https://mainnet.base.org \
  --private-key $PRIVATE_KEY

# Deposit 1 USDC via direct transfer (0x04)
cast send $CLEARINGHOUSE \
  "deposit(address,uint256,bytes)" \
  0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913 \
  1000000 \
  0x04 \
  --rpc-url https://mainnet.base.org \
  --private-key $PRIVATE_KEY
```

- [ ] Deposit succeeded
- [ ] Balance updated correctly
- [ ] Fee collected (0.5%)

#### 3. Test Withdrawal (After 24h or Skip Timelock for Test)
- [ ] Withdrawal succeeds after timelock
- [ ] Rate limit enforced (50% max)

---

## Security Hardening

### Ownership Transfer
- [ ] Gnosis Safe created (2-of-3)
- [ ] AgentRegistry ownership transferred
- [ ] Clearinghouse ownership transferred
- [ ] Verify new owner is Safe address

### Access Control Verification
```bash
# Attempt unauthorized action (should revert)
cast send $REGISTRY "registerSandwichAgent(address,bytes32)" \
  0xRANDOM 0xRANDOM \
  --rpc-url https://mainnet.base.org \
  --private-key $RANDOM_KEY
# Expected: revert "Ownable: caller is not the owner"
```

- [ ] Unauthorized calls revert correctly
- [ ] Only Safe can call admin functions

---

## SDK/Client Updates

### Update Contract Addresses
Files to update:
- [ ] `orchestrator/.env`
- [ ] `server/src/config.rs`
- [ ] `agent/src/config.rs`
- [ ] `HANDOFF_NOTES.md`

### Test End-to-End Flow
- [ ] Python orchestrator connects to new contracts
- [ ] Full Sandwich cycle completes
- [ ] Transaction visible on BaseScan

---

## Monitoring Setup

### Events to Monitor
- [ ] `SandwichAgentRegistered` - New agent registrations
- [ ] `SandwichActionExecuted` - Successful executions
- [ ] `Deposit` / `Withdrawal` - Fund movements
- [ ] `PauseToggled` - Emergency pauses

### Alerting
- [ ] Set up webhook for pause events
- [ ] Monitor for failed transactions
- [ ] Track gas usage

---

## Rollback Plan

If critical issue discovered:

1. **Pause immediately:**
   ```bash
   cast send $CLEARINGHOUSE "setPaused(bool)" true \
     --rpc-url https://mainnet.base.org \
     --private-key $SAFE_OWNER_KEY
   ```

2. **Communicate:**
   - Post status on social channels
   - DM affected users

3. **Investigate:**
   - Review transaction logs
   - Identify root cause

4. **Fix or Redeploy:**
   - Deploy patched contracts
   - Migrate state if needed

---

## Final Sign-Off

| Item | Verified By | Date |
|------|-------------|------|
| All tests pass | | |
| Contracts deployed | | |
| Ownership transferred | | |
| Monitoring active | | |
| Documentation updated | | |

**Deployment completed:** _____________________________

**Notes:**
```


```
