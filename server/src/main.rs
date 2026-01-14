//! 402 Clearinghouse Server
//! 
//! An x402-compliant API gateway for agent-native RWA settlement.

use axum::{
    Router,
    routing::{get, post},
};
use std::net::SocketAddr;
use tower_http::{
    cors::{Any, CorsLayer},
    trace::TraceLayer,
};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

mod config;
mod error;
mod handlers;
mod middleware;
mod models;
mod services;

use config::Config;
use services::blockchain::BlockchainService;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "clearinghouse_server=debug,tower_http=debug".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    // Load configuration
    dotenvy::dotenv().ok();
    let config = Config::from_env()?;
    
    tracing::info!("Starting 402 Clearinghouse Server");
    tracing::info!("Chain: Base Sepolia ({})", config.chain_id);
    tracing::info!("Clearinghouse: {}", config.clearinghouse_address);

    // Initialize blockchain service
    let blockchain = BlockchainService::new(&config).await?;
    let state = handlers::AppState::new(config.clone(), blockchain);

    // Build router
    let app = Router::new()
        // Health check
        .route("/health", get(handlers::health))
        
        // x402 Trade endpoints
        .route("/api/v1/trade/quote/:asset", get(handlers::get_quote))
        .route("/api/v1/trade/buy/:asset", get(handlers::buy_challenge))
        .route("/api/v1/trade/buy/:asset", post(handlers::execute_buy))
        
        // Asset discovery
        .route("/api/v1/assets", get(handlers::list_assets))
        .route("/api/v1/assets/:asset", get(handlers::get_asset))
        
        // Agent verification status
        .route("/api/v1/agent/:address/status", get(handlers::agent_status))
        
        // Compliance circuit info
        .route("/api/v1/compliance/circuit/:asset", get(handlers::get_compliance_circuit))
        
        // State
        .with_state(state)
        
        // Middleware
        .layer(TraceLayer::new_for_http())
        .layer(
            CorsLayer::new()
                .allow_origin(Any)
                .allow_methods(Any)
                .allow_headers(Any),
        );

    // Start server
    let addr = SocketAddr::from(([0, 0, 0, 0], config.port));
    tracing::info!("Listening on {}", addr);
    
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
