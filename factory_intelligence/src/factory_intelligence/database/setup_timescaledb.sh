#!/bin/bash
"""
Creates container, database, and restore data from dump file

Usage
-----
$ chmod +x setup_timescaleDB.sh
$ ./setup_timescaleDB.sh

Content of dump file
--------------------
- agg_boolean_state_durations
- agg_counter_10sec_delta
- agg_counter_10sec
- agg_counter_30sec
- agg_numeric_10sec
- tags_metadata
- equipment 
"""

set -e  # exit on any error
# ============================================================================
# Configuration
# ===========================================================================
DB_USER="gayu"
DB_PASSWORD="password"
CONTAINER_NAME="timescaledb"
DB_NAME="ProductionDB"
# 9 days of production data - December 5, 2025 to December 14, 2025 
# ~600 MB and restored database is ~10-12 GB
DUMP_FILE="$HOME/github/eqrx-ai-assessment/factory_intelligence/database/ProductionDB_aggregates_20251214.dump"

# ============================================================================
# Pre-checks
# ============================================================================
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Install it first."
    exit 1
fi

if [ ! -f "$DUMP_FILE" ]; then
    echo "Dump file not found at: $DUMP_FILE"
    exit 1
fi

# ============================================================================
# Pull and run TimescaleDB HA container (High Availability version)
# ============================================================================
# ----------
# Pull image
# ----------
echo "Pulling TimescaleDB image..."
docker pull timescale/timescaledb-ha:pg17

# ----------------------------------
# Start/Attach to existing container
# ----------------------------------
echo "Starting container..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container already exists, starting it..."
    docker start "$CONTAINER_NAME"
else
    docker run -d \
      --name "$CONTAINER_NAME" \
      -p 5432:5432 \
      -e POSTGRES_PASSWORD="$DB_PASSWORD" \
      -e POSTGRES_USER="$DB_USER" \
      -v timescaledb_data:/var/lib/postgresql/data \
      timescale/timescaledb-ha:pg17
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# -----------------------------------------------------------------------------------
# Database setup - Docker exec commands to create DB and enable TimescaleDB extension
# -----------------------------------------------------------------------------------
echo "Creating database and enabling TimescaleDB..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres \
    -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres \
    -c "CREATE DATABASE \"$DB_NAME\";"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" \
    -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

echo "Verifying extension (in ProductionDB)..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "\dx"

# ============================================================================
# Restore from Dump (Docker) - main part of the setup
# ===========================================================================
# ------------------------------------
# Step1: Copy dump file into container
# ------------------------------------
echo "Copying dump file into container (~600MB, may take a moment)..."
docker cp "$DUMP_FILE" "$CONTAINER_NAME":/tmp/ProductionDB_aggregates_20251214.dump

# ------------------------------------
# Step2: Restore database (single command restore from docs)
# ------------------------------------
echo "Restoring database (this takes a few minutes, warnings are normal)..."
docker exec "$CONTAINER_NAME" pg_restore \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --no-owner \
    --no-privileges \
    --jobs=1 \
    /tmp/ProductionDB_aggregates_20251214.dump || echo "Restore finished with warnings (normal for TimescaleDB)"

# Clean up dump from container
docker exec "$CONTAINER_NAME" rm /tmp/ProductionDB_aggregates_20251214.dump

# ============================================================================
# Verification
# ============================================================================
echo ""
echo "Verifying..."

# Check Database Size
echo "Database size:"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" \
    -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));"

# Check row counts
echo "Row counts:"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT COUNT(*) as boolean_states FROM agg_boolean_state_durations;
SELECT COUNT(*) as counter_delta FROM agg_counter_10sec_delta;
SELECT COUNT(*) as tags FROM tags_metadata;
SELECT COUNT(*) as equipment FROM equipment;
"

# Check continuous aggregates
echo "Continuous aggregates:"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT COUNT(*) as counter_10sec FROM agg_counter_10sec;
SELECT COUNT(*) as counter_30sec FROM agg_counter_30sec;
SELECT COUNT(*) as numeric_10sec FROM agg_numeric_10sec;
"

# List all tables
echo "All tables:"
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "\dt"

echo ""
echo "Setup complete!"
echo "Connect with:  docker exec -it $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME"
echo "Or from Mac:   psql -h localhost -U $DB_USER -d $DB_NAME"
echo "Python connection string: postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
