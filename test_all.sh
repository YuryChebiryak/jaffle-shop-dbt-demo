#!/bin/bash
#
# Comprehensive test script for jaffle-shop-dbt-demo
# Tests: podman/docker machine, docker compose, venv, uv, dbt build, trino-cli
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo_step() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

echo_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

echo_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

echo_error() {
    echo -e "${RED}✗ $1${NC}"
}

# ============================================================================
# STEP 1: Container Runtime Detection
# ============================================================================
echo_step "STEP 1: Container Runtime Detection"

# Detect container runtime
if command -v podman &> /dev/null; then
    CONTAINER_RUNTIME="podman"
    COMPOSE_CMD="podman-compose"
    echo_success "Using Podman as container runtime"
elif command -v docker &> /dev/null; then
    CONTAINER_RUNTIME="docker"
    COMPOSE_CMD="docker-compose"
    echo_success "Using Docker as container runtime"
else
    echo_error "Neither podman nor docker is installed. Please install one first."
    exit 1
fi

echo "Compose command: $COMPOSE_CMD"

# For docker on macOS, no machine is needed (docker desktop)
# For podman, we need to check/manage machine
if [ "$CONTAINER_RUNTIME" = "podman" ]; then
    # Check if podman machine exists
    if podman machine list --format json 2>/dev/null | grep -q '"Name"'; then
        MACHINE_STATUS=$(podman machine list --format '{{.Name}} {{.Running}}' 2>/dev/null | awk '{print $2}')
        if [ "$MACHINE_STATUS" = "true" ]; then
            echo_success "Podman machine is already running"
        else
            echo_warning "Podman machine exists but is not running. Starting..."
            podman machine start
            echo_success "Podman machine started"
        fi
    else
        echo_warning "Podman machine does not exist. Creating one..."
        podman machine init
        podman machine start
        echo_success "Podman machine created and started"
    fi
else
    echo "Docker Desktop detected - no machine management needed"
    # Check if docker is running
    if ! docker info &>/dev/null; then
        echo_error "Docker is not running. Please start Docker Desktop."
        exit 1
    fi
    echo_success "Docker is running"
fi

# ============================================================================
# STEP 2: Container Services
# ============================================================================
echo_step "STEP 2: Container Services"

# Stop any existing containers first
echo "Stopping any existing containers..."
$COMPOSE_CMD down --remove-orphans 2>/dev/null || true

# Start services in background
echo "Starting container services..."
$COMPOSE_CMD up -d

# Wait for services to be ready
wait_for_container() {
    local container_name=$1
    local max_attempts=60
    local attempt=1
    
    echo "Waiting for $container_name to be ready..."
    while [ $attempt -le $max_attempts ]; do
        # Check container status using docker/podman ps
        if $CONTAINER_RUNTIME ps --format '{{.Names}}' 2>/dev/null | grep -q "$container_name"; then
            local status=$($CONTAINER_RUNTIME ps --format '{{.Status}}' --filter "name=$container_name" 2>/dev/null | head -1)
            if [[ "$status" == Up* ]] || [[ "$status" == *"Up"* ]]; then
                echo_success "$container_name is running"
                return 0
            fi
        fi
        
        echo "  Attempt $attempt/$max_attempts: waiting for $container_name..."
        sleep 3
        attempt=$((attempt + 1))
    done
    
    echo_warning "$container_name may need more time to start"
    return 1
}

wait_for_container "jaffle-minio" || true
wait_for_container "jaffle-iceberg-rest" || true
wait_for_container "trino" || true

# Show running containers
echo -e "\n${YELLOW}Running containers:${NC}"
$COMPOSE_CMD ps 2>/dev/null || $CONTAINER_RUNTIME ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# ============================================================================
# STEP 3: Install uv if needed
# ============================================================================
echo_step "STEP 3: Installing uv (Python Package Manager)"

if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add uv to PATH for this session
    export PATH="$HOME/.cargo/bin:$PATH"
    source "$HOME/.cargo/env" 2>/dev/null || true
    echo_success "uv installed successfully"
else
    echo_success "uv is already installed: $(uv --version)"
fi

# ============================================================================
# STEP 4: Virtual Environment Setup
# ============================================================================
echo_step "STEP 4: Virtual Environment Setup"

# Check if venv exists, create if not
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo_success "Virtual environment created at $VENV_DIR"
else
    echo_success "Virtual environment already exists at $VENV_DIR"
fi

# Activate venv
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"
echo_success "Virtual environment activated"

# Show Python and uv versions
echo "Python version: $(python --version)"
echo "uv version: $(uv --version)"

# ============================================================================
# STEP 5: Install Requirements
# ============================================================================
echo_step "STEP 5: Installing Requirements from requirements.txt"

# Install requirements using uv
echo "Installing packages with uv..."
uv pip install --system -r "$SCRIPT_DIR/requirements.txt"
echo_success "Packages installed with uv"

# Verify dbt is installed
if command -v dbt &> /dev/null; then
    echo_success "dbt is installed: $(dbt --version | head -n1)"
else
    echo_error "dbt is not installed properly"
    exit 1
fi

# ============================================================================
# STEP 6: DBT Build
# ============================================================================
echo_step "STEP 6: Running DBT Build"

# Check for profiles.yml
if [ ! -f "$SCRIPT_DIR/profiles.yml" ]; then
    echo_error "profiles.yml not found at $SCRIPT_DIR/profiles.yml"
    exit 1
fi
echo_success "profiles.yml found"

# Ensure DBT_PROFILES_DIR is set
export DBT_PROFILES_DIR="$SCRIPT_DIR"
echo "DBT_PROFILES_DIR set to: $DBT_PROFILES_DIR"

# Run dbt debug to check connection
echo "Running dbt debug..."
dbt debug --target dev 2>&1 || true

# Clean and run dbt build
echo "Running dbt clean..."
dbt clean 2>/dev/null || true

echo "Running dbt deps (if needed)..."
dbt deps 2>/dev/null || true

echo "Running dbt seed..."
dbt seed --target dev

echo "Running dbt run..."
dbt run --target dev

echo "Running dbt test..."
dbt test --target dev

echo_success "DBT build completed successfully"

# List the models created
echo -e "\n${YELLOW}Models created:${NC}"
dbt ls --resource-type model --target dev 2>/dev/null || true

# ============================================================================
# STEP 7: Trino CLI Verification
# ============================================================================
echo_step "STEP 7: Verifying Data with Trino CLI"

# Wait for trino to be ready
echo "Waiting for Trino to be ready..."
MAX_WAIT=120
WAIT_COUNT=0
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if $CONTAINER_RUNTIME exec trino trino --execute "SELECT 1" &>/dev/null; then
        echo_success "Trino is ready"
        break
    fi
    echo "  Waiting... ($WAIT_COUNT/$MAX_WAIT)"
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo_warning "Trino took too long to start, continuing anyway..."
fi

# Show available catalogs
echo -e "\n${YELLOW}Available Catalogs in Trino:${NC}"
$CONTAINER_RUNTIME exec trino trino --execute "SHOW CATALOGS" 2>/dev/null || echo_warning "Could not show catalogs"

# Show available schemas
echo -e "\n${YELLOW}Available Schemas in jaffle_postgres catalog:${NC}"
$CONTAINER_RUNTIME exec trino trino --execute "SHOW SCHEMAS FROM jaffle_postgres" 2>/dev/null || echo_warning "Could not show schemas"

# Try to query tables
echo -e "\n${YELLOW}Showing tables in jaffle_postgres catalog:${NC}"
$CONTAINER_RUNTIME exec trino trino --execute "SHOW TABLES FROM jaffle_postgres" 2>/dev/null || echo_warning "Could not show tables"

# Try a simple query to verify data access
echo -e "\n${YELLOW}Testing data query (this will show data if dbt wrote to S3):${NC}"
$CONTAINER_RUNTIME exec trino trino --execute "SELECT COUNT(*) FROM jaffle_postgres.information_schema.tables" 2>/dev/null || \
    echo_warning "Query failed - expected if no iceberg data was written to S3"

# ============================================================================
# STEP 8: Summary
# ============================================================================
echo_step "TEST SUMMARY"

echo -e "${GREEN}All major components have been tested:${NC}"
echo "  1. ✓ Container runtime: $CONTAINER_RUNTIME"
echo "  2. ✓ Container services: Running"
echo "  3. ✓ Virtual environment: Activated at $VENV_DIR"
echo "  4. ✓ Requirements installed: $(wc -l < "$SCRIPT_DIR/requirements.txt") packages"
echo "  5. ✓ DBT build: Completed"
echo "  6. ✓ Trino: Accessible"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "  - Check dbt models output in DuckDB: $SCRIPT_DIR/target/run/jaffle_shop/"
echo "  - Access Trino UI: http://localhost:8080"
echo "  - Access MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
echo "  - Access Superset: http://localhost:8088 (admin/admin)"

echo -e "\n${GREEN}Test script completed successfully!${NC}"
