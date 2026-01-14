//! Data models for API requests/responses

use serde::{Deserialize, Serialize};

/// Asset information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Asset {
    pub id: String,
    pub name: String,
    pub symbol: String,
    pub address: String,
    pub issuer: String,
    pub price_per_unit: u64, // In atomic USDC (6 decimals)
    pub currency: String,
    pub compliance_circuit: String,
    pub active: bool,
}

/// Quote for purchasing an asset
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Quote {
    pub asset_id: String,
    pub amount: u64,
    pub price_per_unit: u64,
    pub total_price: u64,
    pub fee: u64,
    pub expiry: u64,
    pub quote_id: String,
}

/// x402 Challenge headers
#[derive(Debug, Clone, Serialize)]
pub struct X402Challenge {
    pub asset_id: String,
    pub price: u64,
    pub currency: String,
    pub compliance_circuit: String,
    pub payment_address: String,
    pub expiry: u64,
    pub quote_id: String,
}

/// Settlement request from agent
#[derive(Debug, Clone, Deserialize)]
pub struct SettlementRequest {
    pub asset: String,
    pub amount: u64,
    pub quote_id: String,
    pub compliance_proof: String, // Hex-encoded SP1 proof
    pub public_values: String,    // Hex-encoded public values
    pub payment_signature: Option<String>, // For permit-based payments
}

/// Settlement response
#[derive(Debug, Clone, Serialize)]
pub struct SettlementResponse {
    pub status: SettlementStatus,
    pub tx_hash: Option<String>,
    pub asset_delivered: String,
    pub amount: u64,
    pub settlement_id: String,
    pub timestamp: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SettlementStatus {
    Settled,
    Pending,
    Failed,
}

/// Agent verification status
#[derive(Debug, Clone, Serialize)]
pub struct AgentStatus {
    pub address: String,
    pub verified: bool,
    pub verified_until: Option<u64>,
    pub total_settlements: u64,
    pub total_volume_usdc: u64,
}

/// Compliance circuit metadata
#[derive(Debug, Clone, Serialize)]
pub struct ComplianceCircuit {
    pub circuit_id: String,
    pub name: String,
    pub description: String,
    pub ipfs_hash: String,
    pub verifier_address: String,
    pub required_claims: Vec<String>,
}

/// Health check response
#[derive(Debug, Clone, Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub chain_id: u64,
    pub block_number: u64,
    pub clearinghouse: String,
    pub version: String,
}
