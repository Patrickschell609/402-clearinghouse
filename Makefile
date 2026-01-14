# 402 Clearinghouse - Development Makefile
#
# Usage:
#   make help      - Show available commands
#   make dev       - Start development server
#   make test      - Run all tests
#   make deploy    - Deploy contracts to testnet

.PHONY: help dev server agent contracts test clean docker

# Colors
GREEN  := \033[0;32m
YELLOW := \033[0;33m
NC     := \033[0m

help:
	@echo "$(GREEN)402 Clearinghouse - Development Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)Development:$(NC)"
	@echo "  make dev        - Start server in development mode"
	@echo "  make server     - Build and run server (release)"
	@echo "  make agent      - Run agent demo"
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@echo "  make test       - Run all tests"
	@echo "  make test-e2e   - Run E2E integration test"
	@echo "  make test-unit  - Run unit tests"
	@echo ""
	@echo "$(YELLOW)Contracts:$(NC)"
	@echo "  make contracts  - Build contracts"
	@echo "  make deploy     - Deploy to Base Sepolia"
	@echo "  make verify     - Verify on Basescan"
	@echo ""
	@echo "$(YELLOW)Docker:$(NC)"
	@echo "  make docker     - Build Docker image"
	@echo "  make docker-up  - Start all services"
	@echo "  make docker-down- Stop all services"
	@echo ""
	@echo "$(YELLOW)Utilities:$(NC)"
	@echo "  make clean      - Clean build artifacts"
	@echo "  make fmt        - Format all code"
	@echo "  make lint       - Run linters"

# ============ Development ============

dev:
	@echo "$(GREEN)Starting development server...$(NC)"
	cd server && RUST_LOG=debug cargo run

server:
	@echo "$(GREEN)Building server (release)...$(NC)"
	cd server && cargo build --release
	@echo "$(GREEN)Starting server...$(NC)"
	./server/target/release/clearinghouse-server

agent:
	@echo "$(GREEN)Running agent demo...$(NC)"
	cd agent && cargo run -- list
	@echo ""
	cd agent && cargo run -- buy --asset TBILL-26 --amount 100 --dry-run

# ============ Testing ============

test: test-unit test-e2e

test-unit:
	@echo "$(GREEN)Running unit tests...$(NC)"
	cd server && cargo test
	cd contracts && forge test

test-e2e:
	@echo "$(GREEN)Running E2E integration test...$(NC)"
	python3 tests/e2e_test.py --server http://localhost:8080

# ============ Contracts ============

contracts:
	@echo "$(GREEN)Building contracts...$(NC)"
	cd contracts && forge build

deploy:
	@echo "$(GREEN)Deploying to Base Sepolia...$(NC)"
	cd contracts && forge script script/Deploy.s.sol \
		--rpc-url https://sepolia.base.org \
		--broadcast \
		--verify

verify:
	@echo "$(GREEN)Verifying contracts on Basescan...$(NC)"
	cd contracts && forge verify-contract \
		$${CLEARINGHOUSE_ADDRESS} \
		src/Clearinghouse402.sol:Clearinghouse402 \
		--chain base-sepolia

# ============ SP1 Circuits ============

circuits:
	@echo "$(GREEN)Building SP1 circuit...$(NC)"
	cd circuits && cargo prove build

circuits-test:
	@echo "$(GREEN)Testing SP1 circuit...$(NC)"
	cd circuits && cargo prove test

# ============ Docker ============

docker:
	@echo "$(GREEN)Building Docker image...$(NC)"
	docker build -t clearinghouse-402:latest .

docker-up:
	@echo "$(GREEN)Starting services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Services started. Server at http://localhost:8080$(NC)"

docker-down:
	@echo "$(GREEN)Stopping services...$(NC)"
	docker-compose down

docker-logs:
	docker-compose logs -f

# ============ Utilities ============

clean:
	@echo "$(GREEN)Cleaning build artifacts...$(NC)"
	cd server && cargo clean
	cd agent && cargo clean
	cd circuits && cargo clean
	cd contracts && forge clean
	rm -rf target/

fmt:
	@echo "$(GREEN)Formatting code...$(NC)"
	cd server && cargo fmt
	cd agent && cargo fmt
	cd circuits && cargo fmt
	cd contracts && forge fmt

lint:
	@echo "$(GREEN)Running linters...$(NC)"
	cd server && cargo clippy -- -D warnings
	cd agent && cargo clippy -- -D warnings
	cd contracts && forge lint

# ============ Quick Start ============

setup:
	@echo "$(GREEN)Setting up development environment...$(NC)"
	@echo "1. Installing Rust dependencies..."
	rustup update
	@echo "2. Installing Foundry..."
	curl -L https://foundry.paradigm.xyz | bash
	foundryup
	@echo "3. Installing Python dependencies..."
	pip install requests
	@echo "4. Creating .env from template..."
	cp -n .env.example .env || true
	@echo ""
	@echo "$(GREEN)Setup complete!$(NC)"
	@echo "Edit .env with your contract addresses, then run: make dev"
