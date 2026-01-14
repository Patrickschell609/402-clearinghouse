//! Configuration management

use anyhow::{Context, Result};
use std::env;

#[derive(Clone, Debug)]
pub struct Config {
    pub port: u16,
    pub chain_id: u64,
    pub rpc_url: String,
    pub clearinghouse_address: String,
    pub usdc_address: String,
    pub private_key: Option<String>, // For relay transactions
    pub quote_validity_seconds: u64,
}

impl Config {
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            port: env::var("PORT")
                .unwrap_or_else(|_| "8080".to_string())
                .parse()
                .context("Invalid PORT")?,
            
            chain_id: env::var("CHAIN_ID")
                .unwrap_or_else(|_| "84532".to_string()) // Base Sepolia
                .parse()
                .context("Invalid CHAIN_ID")?,
            
            rpc_url: env::var("RPC_URL")
                .unwrap_or_else(|_| "https://sepolia.base.org".to_string()),
            
            clearinghouse_address: env::var("CLEARINGHOUSE_ADDRESS")
                .context("CLEARINGHOUSE_ADDRESS required")?,
            
            usdc_address: env::var("USDC_ADDRESS")
                .context("USDC_ADDRESS required")?,
            
            private_key: env::var("RELAY_PRIVATE_KEY").ok(),
            
            quote_validity_seconds: env::var("QUOTE_VALIDITY_SECONDS")
                .unwrap_or_else(|_| "300".to_string()) // 5 minutes
                .parse()
                .context("Invalid QUOTE_VALIDITY_SECONDS")?,
        })
    }
}
