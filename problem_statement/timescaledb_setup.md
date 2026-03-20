# TimescaleDB Setup & Restore Guide

Quick guide for installing TimescaleDB and restoring the ProductionDB database.

---

## Download Database Dump

> [!IMPORTANT]
> Download the database dump file from Google Drive before proceeding with the restore steps.

**Database Dump File:** [ProductionDB_aggregates_20251214.dump](https://drive.google.com/file/d/1S1MoJjClcI0RewEP9wwQmXD4dGsWlrEt/view?usp=sharing)

**File Size:** ~600 MB (compressed dump file)  
**Restored Database Size:** ~10-12 GB (after restoration)

> [!WARNING]
> Ensure your database instance has at least **15 GB of free disk space** before proceeding with the restoration to accommodate the database and allow for growth.

**Data Range:** December 5, 2025 to December 14, 2025 (9 days of production data)

This dump contains:
- All hierarchy tables (enterprises, sites, factories, zones, lines, equipment)
- Tag metadata
- Shifts configuration
- Counter aggregates (10sec, 30sec, 1min, 30min, 1hour)
- Numeric aggregates (10sec, 30sec, 1min, 30min, 1hour)
- Boolean state durations
- Continuous aggregate definitions

---

## Installation

### Docker (Recommended)

```bash
# Pull and run TimescaleDB HA container (High Availability version)
docker pull timescale/timescaledb-ha:pg17

docker run -d \
  --name timescaledb \
  -p 5432:5432 \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_USER=your_username \
  -v timescaledb_data:/var/lib/postgresql/data \
  timescale/timescaledb-ha:pg17
```

### Native (Ubuntu/Debian)

```bash
# Install TimescaleDB (see official docs for detailed steps)
sudo apt update
sudo apt install timescaledb-2-postgresql-17
sudo timescaledb-tune --quiet --yes
sudo systemctl restart postgresql
```

---

## Database Setup

### Docker Setup

```bash
# Enter the container
docker exec -it timescaledb bash

# Create database (connect to postgres to create new database)
psql -U your_username -d postgres -c "CREATE DATABASE ProductionDB;"

# Enable TimescaleDB extension (connect to ProductionDB)
psql -U your_username -d ProductionDB -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Verify extension (in ProductionDB)
psql -U your_username -d ProductionDB -c "\dx"
```

### Native Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# Create user (if needed)
CREATE USER your_username WITH PASSWORD 'your_password' SUPERUSER;

# Create database
CREATE DATABASE ProductionDB OWNER your_username;

# Connect to database
\c ProductionDB

# Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

# Verify extension
\dx

# Exit
\q
```

---

## Restore from Dump (Docker)

### Step 1: Copy Dump File to Container

```bash
# Copy dump file from host to container
docker cp /path/to/ProductionDB_aggregates_20251214.dump timescaledb:/tmp/
```

### Step 2: Restore Database

**Method 1: Single command restore**

```bash
docker exec -it timescaledb bash -c "
psql -U your_username -d postgres -c 'DROP DATABASE IF EXISTS ProductionDB;' &&
psql -U your_username -d postgres -c 'CREATE DATABASE ProductionDB;' &&
psql -U your_username -d ProductionDB -c 'CREATE EXTENSION IF NOT EXISTS timescaledb;' &&
pg_restore -U your_username -d ProductionDB --no-owner --no-privileges --jobs=1 /tmp/ProductionDB_aggregates_20251214.dump
"
```

**Method 2: Step-by-step**

```bash
# Enter container
docker exec -it timescaledb bash

# Drop existing database (if needed) - connect to postgres
psql -U your_username -d postgres -c "DROP DATABASE IF EXISTS ProductionDB;"

# Create database - connect to postgres
psql -U your_username -d postgres -c "CREATE DATABASE ProductionDB;"

# Enable TimescaleDB - connect to ProductionDB
psql -U your_username -d ProductionDB -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Restore dump
pg_restore -U your_username -d ProductionDB \
  --no-owner \
  --no-privileges \
  --jobs=1 \
  /tmp/ProductionDB_aggregates_20251214.dump

# Exit container
exit
```

---

## Restore from Dump (Native)

### Step 1: Prepare Database

```bash
# Drop existing database (if needed) - connect to postgres
sudo -u postgres psql -d postgres -c "DROP DATABASE IF EXISTS ProductionDB;"

# Create database - connect to postgres
sudo -u postgres psql -d postgres -c "CREATE DATABASE ProductionDB OWNER your_username;"

# Enable TimescaleDB - connect to ProductionDB
sudo -u postgres psql -d ProductionDB -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### Step 2: Restore Dump

```bash
# Restore using pg_restore
pg_restore -U your_username -d ProductionDB \
  --no-owner \
  --no-privileges \
  --jobs=1 \
  /path/to/ProductionDB_aggregates_20251214.dump
```

**Or if using a .sql.gz file:**

```bash
# Decompress and restore
gunzip -c /path/to/ProductionDB_20251213.sql.gz | psql -U your_username -d ProductionDB
```

---

## Verification

### Check Database Size

```bash
# Docker
docker exec -it timescaledb psql -U your_username -d ProductionDB -c "SELECT pg_size_pretty(pg_database_size('ProductionDB'));"

# Native
psql -U your_username -d ProductionDB -c "SELECT pg_size_pretty(pg_database_size('ProductionDB'));"
```

### Check Table Counts

```sql
-- Connect to database
psql -U your_username -d ProductionDB

-- Check row counts
SELECT COUNT(*) as boolean_states FROM agg_boolean_state_durations;
SELECT COUNT(*) as counter_delta FROM agg_counter_10sec_delta;
SELECT COUNT(*) as tags FROM tags_metadata;
SELECT COUNT(*) as equipment FROM equipment;

-- Check continuous aggregates
SELECT COUNT(*) FROM agg_counter_10sec;
SELECT COUNT(*) FROM agg_counter_30sec;
SELECT COUNT(*) FROM agg_numeric_10sec;

-- List all tables
\dt

-- Exit
\q
```

### Expected Results

### Expected Results

| Table | Expected Rows |
|-------|---------------|
| `agg_boolean_state_durations` | 549,979 |
| `agg_counter_10sec_delta` | 222,192 |
| `agg_counter_10sec` | 222,195 |
| `agg_counter_30sec` | 74,064 |
| `agg_numeric_10sec` | 12,072,564 |
| `tags_metadata` | 50 |
| `equipment` | 1 |

---

## Troubleshooting

### Common Issues

**1. Connection Refused**
```bash
# Check if container is running
docker ps

# Check PostgreSQL logs
docker logs timescaledb
```

**2. Permission Denied**
```bash
# Ensure user has correct permissions
psql -U your_username -d postgres -c "ALTER USER your_username WITH SUPERUSER;"
```

**3. Restore Errors**
- Ignore TimescaleDB metadata errors (normal)
- Check if data loaded despite errors
- Use `--jobs=1` for single-threaded restore

**4. Out of Memory**
```bash
# Increase Docker memory limit
docker update --memory 8g timescaledb
```

---

## Quick Reference

### Docker Commands

```bash
# Start container
docker start timescaledb

# Stop container
docker stop timescaledb

# Remove container
docker rm timescaledb

# Access PostgreSQL
docker exec -it timescaledb psql -U your_username -d ProductionDB

# View logs
docker logs -f timescaledb
```

### PostgreSQL Commands

```sql
-- List databases
\l

-- Connect to database
\c ProductionDB

-- List tables
\dt

-- List extensions
\dx

-- Describe table
\d+ agg_boolean_state_durations

-- Exit
\q
```

---

## Additional Resources

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Documentation](https://docs.docker.com/)

---

**Setup complete! Your TimescaleDB instance is ready for production use.** ✅