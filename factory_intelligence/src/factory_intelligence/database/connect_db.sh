#!/bin/bash
DB_USER="gayu"
CONTAINER_NAME="timescaledb"
DB_NAME="ProductionDB"

# Start container if stopped
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting container..."
    docker start "$CONTAINER_NAME"
    sleep 3
fi

docker exec -it "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME"