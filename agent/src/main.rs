//! Autonomous Agent for x402 RWA Acquisition
//!
//! This agent demonstrates the complete flow:
//! 1. Discover assets via API
//! 2. Receive 402 challenge
//! 3. Generate ZK compliance proof
//! 4. Execute atomic settlement

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Parser)]
#[command(name = "agent")]
#[command(about = "Autonomous RWA acquisition agent")]
struct Cli {
    /// Clearinghouse server URL
    #[arg(long, default_value = "http://localhost:8080")]
    server: String,
    
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// List available assets
    List,
    
    /// Get quote for an asset
    Quote {
        /// Asset ID (e.g., TBILL-26)
        #[arg(short, long)]
        asset: String,
        
        /// Amount to purchase
        #[arg(short = 'n', long, default_value = "100")]
        amount: u64,
    },
    
    /// Execute purchase (full x402 flow)
    Buy {
        /// Asset ID
        #[arg(short, long)]
        asset: String,
        
        /// Amount to purchase
        #[arg(short = 'n', long, default_value = "100")]
        amount: u64,
        
        /// Dry run (don't actually execute)
        #[arg(long)]
        dry_run: bool,
    },
    
    /// Check agent status
    Status {
        /// Agent address
        #[arg(short, long)]
        address: String,
    },
}

#[derive(Debug, Deserialize)]
struct Asset {
    id: String,
    name: String,
    symbol: String,
    address: String,
    price_per_unit: u64,
    currency: String,
    active: bool,
}

#[derive(Debug, Deserialize)]
struct Quote {
    asset_id: String,
    amount: u64,
    price_per_unit: u64,
    total_price: u64,
    fee: u64,
    expiry: u64,
    quote_id: String,
}

#[derive(Debug, Deserialize)]
struct X402Response {
    error: String,
    message: String,
    protocol: String,
    asset: String,
    amount: u64,
    total_price: u64,
    currency: String,
    expiry: u64,
    quote_id: String,
    compliance_circuit: String,
    payment_address: String,
}

#[derive(Debug, Serialize)]
struct SettlementRequest {
    asset: String,
    amount: u64,
    quote_id: String,
    compliance_proof: String,
    public_values: String,
}

#[derive(Debug, Deserialize)]
struct SettlementResponse {
    status: String,
    tx_hash: Option<String>,
    asset_delivered: String,
    amount: u64,
    settlement_id: String,
    timestamp: u64,
}

#[derive(Debug, Deserialize)]
struct AgentStatus {
    address: String,
    verified: bool,
    verified_until: Option<u64>,
    total_settlements: u64,
    total_volume_usdc: u64,
}

struct Agent {
    client: Client,
    server: String,
    wallet_address: String,
}

impl Agent {
    fn new(server: &str) -> Self {
        Self {
            client: Client::new(),
            server: server.to_string(),
            // Mock wallet address for demo
            wallet_address: "0x742d35Cc6634C0532925a3b844Bc9e7595f1Ab23".to_string(),
        }
    }
    
    async fn list_assets(&self) -> Result<Vec<Asset>> {
        let url = format!("{}/api/v1/assets", self.server);
        let resp = self.client.get(&url).send().await?;
        let assets: Vec<Asset> = resp.json().await?;
        Ok(assets)
    }
    
    async fn get_quote(&self, asset: &str, amount: u64) -> Result<Quote> {
        let url = format!("{}/api/v1/trade/quote/{}?amount={}", self.server, asset, amount);
        let resp = self.client.get(&url).send().await?;
        let quote: Quote = resp.json().await?;
        Ok(quote)
    }
    
    /// Core x402 flow: Get challenge, generate proof, execute settlement
    async fn buy(&self, asset: &str, amount: u64, dry_run: bool) -> Result<SettlementResponse> {
        println!("\n[*] Agent: Initiating x402 purchase flow");
        println!("    Asset: {}", asset);
        println!("    Amount: {}", amount);
        
        // Step 1: Initial probe (expecting 402)
        let url = format!("{}/api/v1/trade/buy/{}?amount={}", self.server, asset, amount);
        println!("\n[1] Sending initial request to {}", url);
        
        let resp = self.client.get(&url).send().await?;
        
        if resp.status().as_u16() != 402 {
            anyhow::bail!("Expected 402 Payment Required, got {}", resp.status());
        }
        
        println!("[!] Received 402 Payment Required");
        
        // Step 2: Parse x402 headers
        let headers = resp.headers();
        let asset_id = headers.get("X-402-Asset-ID")
            .and_then(|v| v.to_str().ok())
            .context("Missing X-402-Asset-ID")?;
        let price = headers.get("X-402-Price")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.parse::<u64>().ok())
            .context("Missing X-402-Price")?;
        let compliance_circuit = headers.get("X-402-Compliance-Circuit")
            .and_then(|v| v.to_str().ok())
            .context("Missing X-402-Compliance-Circuit")?;
        let payment_address = headers.get("X-402-Payment-Address")
            .and_then(|v| v.to_str().ok())
            .context("Missing X-402-Payment-Address")?;
        let expiry = headers.get("X-402-Expiry")
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.parse::<u64>().ok())
            .context("Missing X-402-Expiry")?;
        let quote_id = headers.get("X-402-Quote-ID")
            .and_then(|v| v.to_str().ok())
            .context("Missing X-402-Quote-ID")?;
        
        println!("\n[2] Parsed x402 challenge:");
        println!("    Asset ID: {}", asset_id);
        println!("    Price: {} USDC", price as f64 / 1_000_000.0);
        println!("    Compliance Circuit: {}...", &compliance_circuit[..16]);
        println!("    Payment Address: {}", payment_address);
        println!("    Expiry: {}", expiry);
        println!("    Quote ID: {}", quote_id);
        
        // Step 3: Decision engine (risk assessment)
        let risk_acceptable = self.evaluate_risk(asset_id, price, amount, expiry);
        if !risk_acceptable {
            anyhow::bail!("Risk assessment failed - aborting purchase");
        }
        println!("\n[3] Risk assessment: PASSED");
        
        // Step 4: Generate ZK compliance proof
        println!("\n[4] Generating ZK compliance proof...");
        let (proof, public_values) = self.generate_compliance_proof(compliance_circuit)?;
        println!("    Proof generated: {} bytes", proof.len() / 2);
        
        // Step 5: Prepare payment (in production: sign USDC transfer)
        println!("\n[5] Preparing payment transaction...");
        // In production: create and sign the USDC approval/transfer
        
        if dry_run {
            println!("\n[DRY RUN] Would submit:");
            println!("    Proof: {}...", &proof[..32]);
            println!("    Public values: {}...", &public_values[..32]);
            
            return Ok(SettlementResponse {
                status: "dry_run".to_string(),
                tx_hash: None,
                asset_delivered: asset.to_string(),
                amount,
                settlement_id: "DRY_RUN".to_string(),
                timestamp: SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs(),
            });
        }
        
        // Step 6: Execute settlement
        println!("\n[6] Executing atomic settlement...");
        
        let settlement_request = SettlementRequest {
            asset: asset.to_string(),
            amount,
            quote_id: quote_id.to_string(),
            compliance_proof: proof,
            public_values,
        };
        
        let resp = self.client
            .post(&url)
            .json(&settlement_request)
            .send()
            .await?;
        
        if !resp.status().is_success() {
            let error_text = resp.text().await?;
            anyhow::bail!("Settlement failed: {}", error_text);
        }
        
        let settlement: SettlementResponse = resp.json().await?;
        
        println!("\n[$] SETTLEMENT COMPLETE");
        println!("    Status: {}", settlement.status);
        println!("    TX Hash: {}", settlement.tx_hash.as_deref().unwrap_or("N/A"));
        println!("    Asset Delivered: {}", settlement.asset_delivered);
        println!("    Amount: {}", settlement.amount);
        
        Ok(settlement)
    }
    
    /// Simple risk evaluation (expand in production)
    fn evaluate_risk(&self, asset: &str, total_price: u64, amount: u64, expiry: u64) -> bool {
        // Check asset is known
        if !asset.starts_with("TBILL") {
            tracing::warn!("Unknown asset type: {}", asset);
            return false;
        }

        // Check price is reasonable (T-Bills trade near par ~$0.98)
        let price_per_unit = (total_price as f64 / amount as f64) / 1_000_000.0;
        if price_per_unit < 0.90 || price_per_unit > 1.10 {
            tracing::warn!("Price outside acceptable range: ${:.4}/unit", price_per_unit);
            return false;
        }
        
        // Check expiry is in the future
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
        if expiry <= now {
            tracing::warn!("Quote already expired");
            return false;
        }
        
        true
    }
    
    /// Generate SP1 ZK proof for compliance
    fn generate_compliance_proof(&self, circuit_id: &str) -> Result<(String, String)> {
        // In production:
        // 1. Load the SP1 prover
        // 2. Prepare private inputs (identity, KYC attestation, etc.)
        // 3. Generate proof
        
        // Mock proof for demo
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();
        
        // Mock proof data
        let mut hasher = Sha256::new();
        hasher.update(circuit_id.as_bytes());
        hasher.update(&now.to_le_bytes());
        hasher.update(self.wallet_address.as_bytes());
        let proof_hash = hasher.finalize();
        
        // Create mock proof (in production: actual SP1 proof bytes)
        let mock_proof = format!("{:x}", proof_hash);
        
        // Public values: (agent_address, valid_until, jurisdiction_hash)
        // ABI encoded as bytes
        let valid_until = now + 30 * 24 * 60 * 60; // 30 days
        let mut public_values = Vec::new();
        
        // Pad address to 32 bytes
        public_values.extend_from_slice(&[0u8; 12]);
        public_values.extend_from_slice(&hex::decode(&self.wallet_address[2..]).unwrap_or_default());
        
        // Add valid_until (32 bytes)
        public_values.extend_from_slice(&[0u8; 24]);
        public_values.extend_from_slice(&valid_until.to_be_bytes());
        
        // Add jurisdiction hash (32 bytes)
        let mut hasher = Sha256::new();
        hasher.update(b"US");
        public_values.extend_from_slice(&hasher.finalize());
        
        Ok((format!("0x{}", mock_proof), format!("0x{}", hex::encode(&public_values))))
    }
    
    async fn get_status(&self, address: &str) -> Result<AgentStatus> {
        let url = format!("{}/api/v1/agent/{}/status", self.server, address);
        let resp = self.client.get(&url).send().await?;
        let status: AgentStatus = resp.json().await?;
        Ok(status)
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt::init();
    dotenvy::dotenv().ok();
    
    let cli = Cli::parse();
    let agent = Agent::new(&cli.server);
    
    match cli.command {
        Commands::List => {
            println!("Fetching available assets...\n");
            let assets = agent.list_assets().await?;
            
            println!("{:<12} {:<30} {:<10} {:<12}", "ID", "Name", "Price", "Status");
            println!("{}", "-".repeat(70));
            
            for asset in assets {
                let price = asset.price_per_unit as f64 / 1_000_000.0;
                let status = if asset.active { "Active" } else { "Inactive" };
                println!("{:<12} {:<30} ${:<9.4} {:<12}", 
                    asset.id, asset.name, price, status);
            }
        }
        
        Commands::Quote { asset, amount } => {
            println!("Fetching quote for {} units of {}...\n", amount, asset);
            let quote = agent.get_quote(&asset, amount).await?;
            
            let price_per_unit = quote.price_per_unit as f64 / 1_000_000.0;
            let total = quote.total_price as f64 / 1_000_000.0;
            let fee = quote.fee as f64 / 1_000_000.0;
            
            println!("Quote Details:");
            println!("  Asset:         {}", quote.asset_id);
            println!("  Amount:        {}", quote.amount);
            println!("  Price/Unit:    ${:.4}", price_per_unit);
            println!("  Fee:           ${:.4} (0.05%)", fee);
            println!("  Total:         ${:.4}", total);
            println!("  Quote ID:      {}", quote.quote_id);
            println!("  Valid Until:   {}", quote.expiry);
        }
        
        Commands::Buy { asset, amount, dry_run } => {
            if dry_run {
                println!("=== DRY RUN MODE ===\n");
            }
            agent.buy(&asset, amount, dry_run).await?;
        }
        
        Commands::Status { address } => {
            let status = agent.get_status(&address).await?;
            
            println!("Agent Status:");
            println!("  Address:           {}", status.address);
            println!("  Verified:          {}", status.verified);
            if let Some(until) = status.verified_until {
                println!("  Verified Until:    {}", until);
            }
            println!("  Total Settlements: {}", status.total_settlements);
            println!("  Total Volume:      ${:.2}", status.total_volume_usdc as f64 / 1_000_000.0);
        }
    }
    
    Ok(())
}
