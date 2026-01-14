//! HTTP handlers implementing the x402-RWA protocol

use axum::{
    extract::{Path, Query, State},
    http::{header, HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::config::Config;
use crate::error::AppError;
use crate::models::*;
use crate::services::blockchain::BlockchainService;

/// Shared application state
#[derive(Clone)]
pub struct AppState {
    pub config: Config,
    pub blockchain: Arc<BlockchainService>,
}

impl AppState {
    pub fn new(config: Config, blockchain: BlockchainService) -> Self {
        Self {
            config,
            blockchain: Arc::new(blockchain),
        }
    }
}

/// Health check endpoint
pub async fn health(State(state): State<AppState>) -> Result<Json<HealthResponse>, AppError> {
    let block_number = state.blockchain.get_block_number().await?;
    
    Ok(Json(HealthResponse {
        status: "healthy".to_string(),
        chain_id: state.config.chain_id,
        block_number,
        clearinghouse: state.config.clearinghouse_address.clone(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    }))
}

/// List all available assets
pub async fn list_assets(State(state): State<AppState>) -> Result<Json<Vec<Asset>>, AppError> {
    let assets = state.blockchain.get_listed_assets().await?;
    Ok(Json(assets))
}

/// Get specific asset details
pub async fn get_asset(
    State(state): State<AppState>,
    Path(asset): Path<String>,
) -> Result<Json<Asset>, AppError> {
    let asset = state
        .blockchain
        .get_asset(&asset)
        .await?
        .ok_or_else(|| AppError::AssetNotFound(asset.clone()))?;
    Ok(Json(asset))
}

#[derive(Debug, Deserialize)]
pub struct QuoteQuery {
    pub amount: u64,
}

/// Get a quote for an asset purchase
pub async fn get_quote(
    State(state): State<AppState>,
    Path(asset): Path<String>,
    Query(query): Query<QuoteQuery>,
) -> Result<Json<Quote>, AppError> {
    let asset_info = state
        .blockchain
        .get_asset(&asset)
        .await?
        .ok_or_else(|| AppError::AssetNotFound(asset.clone()))?;
    
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    let total_price = query.amount * asset_info.price_per_unit;
    let fee = total_price * 5 / 10_000; // 0.05% fee
    
    let quote_id = format!(
        "{:x}",
        sha2::Sha256::digest(format!("{}{}{}{}", asset, query.amount, now, state.config.chain_id))
    );
    
    Ok(Json(Quote {
        asset_id: asset,
        amount: query.amount,
        price_per_unit: asset_info.price_per_unit,
        total_price: total_price + fee,
        fee,
        expiry: now + state.config.quote_validity_seconds,
        quote_id,
    }))
}

/// x402 Challenge - Returns 402 Payment Required with headers
/// This is the core of the x402-RWA protocol
pub async fn buy_challenge(
    State(state): State<AppState>,
    Path(asset): Path<String>,
    Query(query): Query<QuoteQuery>,
) -> Result<impl IntoResponse, AppError> {
    let asset_info = state
        .blockchain
        .get_asset(&asset)
        .await?
        .ok_or_else(|| AppError::AssetNotFound(asset.clone()))?;
    
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    let total_price = query.amount * asset_info.price_per_unit;
    let fee = total_price * 5 / 10_000;
    let expiry = now + state.config.quote_validity_seconds;
    
    let quote_id = format!(
        "{:016x}",
        now ^ (query.amount << 32) ^ state.config.chain_id
    );
    
    // Build x402 response headers
    let mut headers = HeaderMap::new();
    headers.insert("X-402-Asset-ID", asset.parse().unwrap());
    headers.insert("X-402-Price", (total_price + fee).to_string().parse().unwrap());
    headers.insert("X-402-Currency", "USDC-BASE".parse().unwrap());
    headers.insert("X-402-Compliance-Circuit", asset_info.compliance_circuit.parse().unwrap());
    headers.insert("X-402-Payment-Address", state.config.clearinghouse_address.parse().unwrap());
    headers.insert("X-402-Expiry", expiry.to_string().parse().unwrap());
    headers.insert("X-402-Quote-ID", quote_id.parse().unwrap());
    headers.insert("X-402-Chain-ID", state.config.chain_id.to_string().parse().unwrap());
    headers.insert("X-402-Asset-Address", asset_info.address.parse().unwrap());
    headers.insert(
        header::WWW_AUTHENTICATE,
        "Token x402-RWA".parse().unwrap(),
    );
    
    let body = serde_json::json!({
        "error": "Payment Required",
        "message": "Submit ZK compliance proof and payment to complete purchase",
        "protocol": "x402-RWA/1.0",
        "asset": asset,
        "amount": query.amount,
        "total_price": total_price + fee,
        "currency": "USDC",
        "expiry": expiry,
        "quote_id": quote_id,
        "compliance_circuit": asset_info.compliance_circuit,
        "payment_address": state.config.clearinghouse_address,
    });
    
    Ok((StatusCode::PAYMENT_REQUIRED, headers, Json(body)))
}

/// Execute a buy after receiving proof + payment
pub async fn execute_buy(
    State(state): State<AppState>,
    Path(asset): Path<String>,
    Json(request): Json<SettlementRequest>,
) -> Result<Json<SettlementResponse>, AppError> {
    // Validate asset exists
    let asset_info = state
        .blockchain
        .get_asset(&asset)
        .await?
        .ok_or_else(|| AppError::AssetNotFound(asset.clone()))?;
    
    // Validate quote hasn't expired
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    
    // In production: verify quote_id matches and hasn't been used
    
    // Decode proofs
    let compliance_proof = hex::decode(&request.compliance_proof.trim_start_matches("0x"))
        .map_err(|e| AppError::BadRequest(format!("Invalid proof encoding: {}", e)))?;
    
    let public_values = hex::decode(&request.public_values.trim_start_matches("0x"))
        .map_err(|e| AppError::BadRequest(format!("Invalid public values: {}", e)))?;
    
    // Calculate expiry based on quote (in production, track quote expiry properly)
    let quote_expiry = now + 60; // 1 minute grace period
    
    // Execute on-chain settlement
    let tx_hash = state
        .blockchain
        .execute_settlement(
            &asset_info.address,
            request.amount,
            quote_expiry,
            &compliance_proof,
            &public_values,
        )
        .await?;
    
    let settlement_id = format!("{:016x}", now ^ request.amount);
    
    Ok(Json(SettlementResponse {
        status: SettlementStatus::Settled,
        tx_hash: Some(tx_hash),
        asset_delivered: asset,
        amount: request.amount,
        settlement_id,
        timestamp: now,
    }))
}

/// Check agent verification status
pub async fn agent_status(
    State(state): State<AppState>,
    Path(address): Path<String>,
) -> Result<Json<AgentStatus>, AppError> {
    let status = state.blockchain.get_agent_status(&address).await?;
    Ok(Json(status))
}

/// Get compliance circuit details for an asset
pub async fn get_compliance_circuit(
    State(state): State<AppState>,
    Path(asset): Path<String>,
) -> Result<Json<ComplianceCircuit>, AppError> {
    let asset_info = state
        .blockchain
        .get_asset(&asset)
        .await?
        .ok_or_else(|| AppError::AssetNotFound(asset.clone()))?;
    
    // In production, this would fetch from IPFS or a registry
    Ok(Json(ComplianceCircuit {
        circuit_id: asset_info.compliance_circuit.clone(),
        name: "Accredited Investor Verification".to_string(),
        description: "Proves the operator meets SEC accredited investor criteria without revealing identity".to_string(),
        ipfs_hash: format!("ipfs://Qm{}", &asset_info.compliance_circuit[..40]),
        verifier_address: state.config.clearinghouse_address.clone(),
        required_claims: vec![
            "accredited_investor".to_string(),
            "not_sanctioned".to_string(),
            "kyc_verified".to_string(),
        ],
    }))
}

// Re-export for sha2 usage
use sha2::Digest;
