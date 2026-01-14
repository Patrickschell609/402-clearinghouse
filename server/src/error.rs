//! Error types for the clearinghouse server

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum AppError {
    #[error("Asset not found: {0}")]
    AssetNotFound(String),
    
    #[error("Quote expired")]
    QuoteExpired,
    
    #[error("Invalid proof")]
    InvalidProof,
    
    #[error("Insufficient balance")]
    InsufficientBalance,
    
    #[error("Transaction failed: {0}")]
    TransactionFailed(String),
    
    #[error("Blockchain error: {0}")]
    BlockchainError(String),
    
    #[error("Invalid request: {0}")]
    BadRequest(String),
    
    #[error("Internal error: {0}")]
    Internal(String),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, error_message) = match &self {
            AppError::AssetNotFound(_) => (StatusCode::NOT_FOUND, self.to_string()),
            AppError::QuoteExpired => (StatusCode::GONE, self.to_string()),
            AppError::InvalidProof => (StatusCode::UNAUTHORIZED, self.to_string()),
            AppError::InsufficientBalance => (StatusCode::PAYMENT_REQUIRED, self.to_string()),
            AppError::TransactionFailed(_) => (StatusCode::BAD_REQUEST, self.to_string()),
            AppError::BlockchainError(_) => (StatusCode::SERVICE_UNAVAILABLE, self.to_string()),
            AppError::BadRequest(_) => (StatusCode::BAD_REQUEST, self.to_string()),
            AppError::Internal(_) => (StatusCode::INTERNAL_SERVER_ERROR, "Internal error".to_string()),
        };

        let body = Json(json!({
            "error": error_message,
            "code": status.as_u16()
        }));

        (status, body).into_response()
    }
}
