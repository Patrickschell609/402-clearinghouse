# 402 Clearinghouse Server
# Multi-stage build for minimal production image

# ============ BUILD STAGE ============
FROM rust:1.75-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy workspace files
COPY server/Cargo.toml server/Cargo.lock* ./

# Create dummy main.rs for dependency caching
RUN mkdir -p src && echo "fn main() {}" > src/main.rs

# Build dependencies only (cached layer)
RUN cargo build --release && rm -rf src

# Copy actual source code
COPY server/src ./src

# Build the actual application
RUN touch src/main.rs && cargo build --release

# ============ RUNTIME STAGE ============
FROM debian:bookworm-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash clearinghouse

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/target/release/clearinghouse-server /app/clearinghouse-server

# Set ownership
RUN chown -R clearinghouse:clearinghouse /app

# Switch to non-root user
USER clearinghouse

# Expose server port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Environment variables (override at runtime)
ENV PORT=8080 \
    CHAIN_ID=84532 \
    RPC_URL=https://sepolia.base.org \
    RUST_LOG=info

# Run server
ENTRYPOINT ["/app/clearinghouse-server"]
