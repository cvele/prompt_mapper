#!/bin/bash
# Start test environment with Docker Compose

set -e

echo "Starting test environment..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker is not running. Please start Docker first."
    exit 1
fi

# Create necessary directories
mkdir -p docker/radarr/{config,movies,downloads}

# Set up environment for proper UID/GID handling
if [ -z "$PUID" ]; then
    export PUID=$(id -u)
fi
if [ -z "$PGID" ]; then
    export PGID=$(id -g)
fi

echo "Using PUID=$PUID, PGID=$PGID for Docker containers"
echo "Test movies directory: ${MOVIES_DIR:-./test_movies}"

# Start services
echo "Starting Radarr container..."
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d radarr
elif command -v docker >/dev/null 2>&1; then
    docker compose up -d radarr
else
    echo "ERROR: Neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

# Wait for Radarr to be ready
echo "Waiting for Radarr to start..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:7878/ping >/dev/null 2>&1; then
        echo "Radarr is ready at http://localhost:7878"
        break
    fi

    attempt=$((attempt + 1))
    echo "   Attempt $attempt/$max_attempts..."
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Radarr failed to start within expected time"
    echo "Checking container logs..."
    docker-compose logs radarr
    exit 1
fi

# Display status
echo ""
echo "Test environment is ready!"
echo "Radarr: http://localhost:7878"
echo "Config: ./docker/radarr/config"
echo "Movies: ./docker/radarr/movies"
echo "Downloads: ./docker/radarr/downloads"
echo "Test movies: ${MOVIES_DIR:-./test_movies}"
echo "Container UID/GID: $PUID/$PGID"
echo ""
echo "To stop the environment: ./scripts/stop_test_env.sh"
echo "To run integration tests: make test-integration"
