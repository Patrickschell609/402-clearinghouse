#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   SANDWICH MODEL ORCHESTRATOR                                                ║
║   TEE + zkML + MPC Self-Custody for AI Agents                               ║
║                                                                              ║
║   Author: Patrick Schell (@Patrickschell609)                                ║
║   License: MIT                                                               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

The Sandwich Model Flow:
    1. TEE (Phala) → Runs model in secure enclave, produces attested signal
    2. zkML (EZKL/SP1) → Generates ZK proof of inference
    3. MPC (NEAR) → Signs transaction with distributed keys
    4. Settlement (Base) → Executes verified action on-chain

No single point holds all keys. True self-custody.
"""

import os
import json
import asyncio
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from dotenv import load_dotenv

# Web3 imports
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


@dataclass
class TeeOutput:
    """Output from TEE enclave"""
    signal: int  # -1 (sell), 0 (hold), 1 (buy)
    confidence: float
    action_payload: bytes
    signature: bytes
    timestamp: int


@dataclass
class ZkProof:
    """zkML proof of inference"""
    proof: bytes
    public_values: bytes
    model_hash: bytes
    data_hash: bytes


@dataclass
class MpcSignature:
    """MPC-derived signature"""
    signature: bytes
    recovery_id: int
    mpc_request_id: str


class TeeClient:
    """
    Client for Phala TEE (Trusted Execution Environment)

    The TEE runs the actual trading model in a secure enclave.
    It produces:
        - Trading signal (buy/sell/hold)
        - Attested signature proving computation happened in TEE
    """

    def __init__(self, endpoint: str, enclave_key: str):
        self.endpoint = endpoint
        self.enclave_key = enclave_key
        logger.info(f"TEE Client initialized: {endpoint}")

    async def query_signal(self, market_data: Dict[str, Any]) -> TeeOutput:
        """
        Query TEE for trading signal

        In production, this calls the Phala TEE endpoint.
        The enclave runs the model and signs the output.
        """
        logger.info("Querying TEE for signal...")

        # TODO: Replace with actual Phala TEE call
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{self.endpoint}/inference",
        #         json={"market_data": market_data},
        #         headers={"X-Enclave-Key": self.enclave_key}
        #     )
        #     result = response.json()

        # For now, simulate TEE response
        signal = 1  # Buy signal
        confidence = 0.85

        # Create action payload
        action_payload = self._encode_action(signal, market_data)

        # TEE signs the payload (simulated)
        # In production, this signature comes from the enclave
        nonce = int(datetime.now().timestamp() * 1000)
        message_hash = Web3.keccak(action_payload + nonce.to_bytes(32, 'big'))

        # Simulate TEE signing (in production, enclave does this)
        tee_private_key = os.getenv("TEE_PRIVATE_KEY")
        if tee_private_key:
            account = Account.from_key(tee_private_key)
            signed = account.sign_message(encode_defunct(message_hash))
            signature = signed.signature
        else:
            signature = b'\x00' * 65  # Placeholder

        return TeeOutput(
            signal=signal,
            confidence=confidence,
            action_payload=action_payload,
            signature=signature,
            timestamp=nonce
        )

    def _encode_action(self, signal: int, market_data: Dict) -> bytes:
        """Encode trading action as bytes"""
        action = {
            "type": "TRADE",
            "signal": signal,
            "asset": market_data.get("asset", "TBILL-26"),
            "amount": market_data.get("amount", 100),
            "timestamp": int(datetime.now().timestamp())
        }
        return json.dumps(action).encode()


class ZkmlProver:
    """
    zkML Proof Generator

    Generates zero-knowledge proofs that the AI model:
        1. Used the registered model (strategy binding)
        2. Ran on valid input data (data integrity)
        3. Produced the claimed output (computation proof)

    Supports both EZKL (for ONNX models) and SP1 (for Rust circuits).
    """

    def __init__(self, model_path: str, prover_type: str = "sp1"):
        self.model_path = Path(model_path)
        self.prover_type = prover_type
        logger.info(f"zkML Prover initialized: {prover_type}")

    async def generate_proof(
        self,
        input_data: Dict[str, Any],
        model_output: int
    ) -> ZkProof:
        """
        Generate zkML proof of inference
        """
        logger.info("Generating zkML proof...")

        if self.prover_type == "ezkl":
            return await self._generate_ezkl_proof(input_data, model_output)
        elif self.prover_type == "sp1":
            return await self._generate_sp1_proof(input_data, model_output)
        else:
            raise ValueError(f"Unknown prover type: {self.prover_type}")

    async def _generate_ezkl_proof(
        self,
        input_data: Dict,
        model_output: int
    ) -> ZkProof:
        """Generate proof using EZKL"""
        # TODO: Integrate actual EZKL prover
        # import ezkl
        #
        # # Prepare witness
        # witness = ezkl.gen_witness(
        #     self.model_path,
        #     input_data
        # )
        #
        # # Generate proof
        # proof = ezkl.prove(
        #     witness,
        #     self.model_path / "pk.key",
        #     self.model_path / "circuit.ezkl"
        # )

        # Simulated proof
        model_hash = hashlib.sha256(b"decision_model_v1").digest()
        data_hash = hashlib.sha256(json.dumps(input_data).encode()).digest()

        return ZkProof(
            proof=b'\x12\x34' * 130,  # 260 bytes like Groth16
            public_values=model_hash + data_hash + model_output.to_bytes(8, 'big'),
            model_hash=model_hash,
            data_hash=data_hash
        )

    async def _generate_sp1_proof(
        self,
        input_data: Dict,
        model_output: int
    ) -> ZkProof:
        """Generate proof using SP1 zkVM"""
        # TODO: Call SP1 prover binary
        # This would typically shell out to the Rust prover
        #
        # import subprocess
        # result = subprocess.run([
        #     "./target/release/prover",
        #     "--input", json.dumps(input_data),
        #     "--output", str(model_output)
        # ], capture_output=True)
        #
        # proof_data = json.loads(result.stdout)

        # Simulated SP1 proof
        model_hash = hashlib.sha256(b"transformer_attention_v1").digest()
        data_hash = hashlib.sha256(json.dumps(input_data).encode()).digest()

        return ZkProof(
            proof=b'\xAB\xCD' * 130,  # 260 bytes Groth16
            public_values=model_hash + data_hash + model_output.to_bytes(8, 'big'),
            model_hash=model_hash,
            data_hash=data_hash
        )


class MpcSigner:
    """
    NEAR MPC Signer Client

    Requests signatures from NEAR's MPC network.
    The private key is split across multiple nodes - no single party controls it.

    This enables true self-custody: the agent controls funds without
    any server holding the full private key.
    """

    def __init__(
        self,
        account_id: str,
        private_key: str,
        mpc_contract: str = "v2.multichain-mpc.testnet"
    ):
        self.account_id = account_id
        self.private_key = private_key
        self.mpc_contract = mpc_contract
        logger.info(f"MPC Signer initialized: {account_id} -> {mpc_contract}")

    async def request_signature(
        self,
        payload_hash: bytes,
        path: str = "ethereum-1"
    ) -> MpcSignature:
        """
        Request MPC signature from NEAR network

        The payload_hash is the hash of the transaction to sign.
        The path determines which derived key to use.
        """
        logger.info("Requesting MPC signature from NEAR...")

        # TODO: Integrate actual NEAR MPC call
        # from py_near.account import Account
        # from py_near.dapps.core import NEAR
        #
        # near = NEAR()
        # account = Account(self.account_id, self.private_key)
        #
        # result = await account.function_call(
        #     self.mpc_contract,
        #     "sign",
        #     {
        #         "request": {
        #             "payload": list(payload_hash),
        #             "path": path,
        #             "key_version": 0
        #         }
        #     },
        #     gas=300_000_000_000_000
        # )
        #
        # signature = bytes(result["signature"])
        # recovery_id = result["recovery_id"]

        # Simulated MPC signature
        # In production, this comes from NEAR MPC nodes
        return MpcSignature(
            signature=b'\x00' * 65,
            recovery_id=0,
            mpc_request_id="mpc_req_" + hashlib.sha256(payload_hash).hexdigest()[:8]
        )


class BaseExecutor:
    """
    Base Chain Transaction Executor

    Submits verified transactions to Base mainnet.
    All verification happens on-chain via AIGuardian.
    """

    def __init__(self, rpc_url: str, private_key: str):
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.account = Account.from_key(private_key)
        logger.info(f"Base Executor initialized: {self.account.address}")

        # Contract addresses (Base mainnet)
        self.guardian_address = os.getenv(
            "AI_GUARDIAN_ADDRESS",
            "0x0000000000000000000000000000000000000000"  # Deploy address
        )

        # AIGuardian ABI (minimal)
        self.guardian_abi = [
            {
                "inputs": [
                    {"name": "actionPayload", "type": "bytes"},
                    {"name": "teeSignature", "type": "bytes"},
                    {"name": "nonce", "type": "bytes32"},
                    {"name": "zkProof", "type": "bytes"},
                    {"name": "publicValues", "type": "bytes"}
                ],
                "name": "executeSecuredAction",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]

    async def execute_sandwich(
        self,
        action_payload: bytes,
        tee_signature: bytes,
        nonce: bytes,
        zk_proof: bytes,
        public_values: bytes
    ) -> str:
        """
        Execute verified action via AIGuardian

        This calls executeSecuredAction which verifies:
            1. MPC wallet is registered
            2. Nonce hasn't been used
            3. TEE signature is valid
            4. zkML proof is valid

        Only then does it execute the action.
        """
        logger.info("Executing Sandwich action on Base...")

        guardian = self.w3.eth.contract(
            address=self.guardian_address,
            abi=self.guardian_abi
        )

        # Build transaction
        tx = guardian.functions.executeSecuredAction(
            action_payload,
            tee_signature,
            nonce,
            zk_proof,
            public_values
        ).build_transaction({
            'from': self.account.address,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'gas': 500000,
            'gasPrice': self.w3.eth.gas_price,
            'chainId': 8453  # Base mainnet
        })

        # Sign and send
        signed_tx = self.account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        logger.info(f"Transaction sent: {tx_hash.hex()}")

        # Wait for confirmation
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt['status'] == 1:
            logger.info(f"Transaction confirmed in block {receipt['blockNumber']}")
        else:
            logger.error("Transaction failed!")

        return tx_hash.hex()


class AgentController:
    """
    Main Orchestrator for Sandwich Model

    Coordinates the full flow:
        TEE → zkML → MPC → Settlement

    Usage:
        controller = AgentController()
        tx_hash = await controller.run_cycle({"asset": "TBILL-26", "amount": 100})
    """

    def __init__(self):
        # Load configuration
        self.tee_endpoint = os.getenv("TEE_ENDPOINT", "http://localhost:8090")
        self.tee_key = os.getenv("TEE_ENCLAVE_KEY", "")

        self.near_account = os.getenv("NEAR_ACCOUNT_ID", "")
        self.near_key = os.getenv("NEAR_PRIVATE_KEY", "")
        self.mpc_contract = os.getenv("MPC_CONTRACT", "v2.multichain-mpc.testnet")

        self.model_path = os.getenv("MODEL_PATH", "./models/decision_model.onnx")
        self.prover_type = os.getenv("PROVER_TYPE", "sp1")

        self.base_rpc = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
        self.mpc_wallet_key = os.getenv("MPC_WALLET_KEY", "")

        # Initialize clients
        self.tee = TeeClient(self.tee_endpoint, self.tee_key)
        self.zkml = ZkmlProver(self.model_path, self.prover_type)
        self.mpc = MpcSigner(self.near_account, self.near_key, self.mpc_contract)
        self.executor = BaseExecutor(self.base_rpc, self.mpc_wallet_key)

        logger.info("AgentController initialized")

    async def run_cycle(self, market_data: Dict[str, Any]) -> Optional[str]:
        """
        Run one complete Sandwich cycle

        Returns transaction hash if action was executed, None otherwise.
        """
        logger.info("=" * 60)
        logger.info("SANDWICH CYCLE START")
        logger.info("=" * 60)

        try:
            # ═══════════════════════════════════════════════════════════
            # LAYER 1: TEE Inference
            # ═══════════════════════════════════════════════════════════
            logger.info("[1/4] Querying TEE for signal...")
            tee_output = await self.tee.query_signal(market_data)

            logger.info(f"  Signal: {tee_output.signal}")
            logger.info(f"  Confidence: {tee_output.confidence:.2%}")

            # Check if we should act
            if tee_output.signal == 0:
                logger.info("  Signal is HOLD - skipping execution")
                return None

            if tee_output.confidence < 0.7:
                logger.info("  Confidence too low - skipping execution")
                return None

            # ═══════════════════════════════════════════════════════════
            # LAYER 2: zkML Proof Generation
            # ═══════════════════════════════════════════════════════════
            logger.info("[2/4] Generating zkML proof...")
            zk_proof = await self.zkml.generate_proof(
                market_data,
                tee_output.signal
            )

            logger.info(f"  Model hash: {zk_proof.model_hash.hex()[:16]}...")
            logger.info(f"  Proof size: {len(zk_proof.proof)} bytes")

            # ═══════════════════════════════════════════════════════════
            # LAYER 3: MPC Signature (Optional - for full self-custody)
            # ═══════════════════════════════════════════════════════════
            logger.info("[3/4] Requesting MPC signature...")

            # Hash of the full transaction for MPC signing
            tx_hash = hashlib.sha256(
                tee_output.action_payload +
                zk_proof.proof
            ).digest()

            mpc_sig = await self.mpc.request_signature(tx_hash)
            logger.info(f"  MPC request ID: {mpc_sig.mpc_request_id}")

            # ═══════════════════════════════════════════════════════════
            # LAYER 4: On-Chain Execution
            # ═══════════════════════════════════════════════════════════
            logger.info("[4/4] Executing on Base...")

            nonce = tee_output.timestamp.to_bytes(32, 'big')

            tx_hash = await self.executor.execute_sandwich(
                action_payload=tee_output.action_payload,
                tee_signature=tee_output.signature,
                nonce=nonce,
                zk_proof=zk_proof.proof,
                public_values=zk_proof.public_values
            )

            logger.info("=" * 60)
            logger.info("SANDWICH CYCLE COMPLETE")
            logger.info(f"TX: {tx_hash}")
            logger.info("=" * 60)

            return tx_hash

        except Exception as e:
            logger.error(f"Sandwich cycle failed: {e}")
            raise

    async def run_continuous(self, interval_seconds: int = 60):
        """
        Run continuous trading loop
        """
        logger.info(f"Starting continuous mode (interval: {interval_seconds}s)")

        while True:
            try:
                # Fetch current market data
                market_data = await self._fetch_market_data()

                # Run cycle
                await self.run_cycle(market_data)

            except Exception as e:
                logger.error(f"Cycle error: {e}")

            await asyncio.sleep(interval_seconds)

    async def _fetch_market_data(self) -> Dict[str, Any]:
        """Fetch current market data for the model"""
        # TODO: Integrate real data sources
        return {
            "asset": "TBILL-26",
            "amount": 100,
            "price": 0.98,
            "timestamp": int(datetime.now().timestamp())
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Sandwich Model Agent Controller")
    parser.add_argument("--once", action="store_true", help="Run single cycle")
    parser.add_argument("--continuous", action="store_true", help="Run continuous loop")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval (seconds)")
    parser.add_argument("--asset", type=str, default="TBILL-26", help="Asset to trade")
    parser.add_argument("--amount", type=int, default=100, help="Amount to trade")

    args = parser.parse_args()

    controller = AgentController()

    if args.continuous:
        await controller.run_continuous(args.interval)
    else:
        market_data = {
            "asset": args.asset,
            "amount": args.amount,
            "timestamp": int(datetime.now().timestamp())
        }
        result = await controller.run_cycle(market_data)
        if result:
            print(f"Transaction: {result}")
        else:
            print("No action taken")


if __name__ == "__main__":
    asyncio.run(main())
