#!/bin/bash
# Stop test environment

set -e

echo "🛑 Stopping test environment..."

# Stop Docker Compose services (try both new and old syntax)
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose down
elif command -v docker >/dev/null 2>&1; then
    docker compose down
else
    echo "❌ Neither 'docker compose' nor 'docker-compose' found"
    exit 1
fi

echo "✅ Test environment stopped."
echo ""
echo "💡 To clean up completely (remove volumes):"
if command -v docker-compose >/dev/null 2>&1; then
    echo "   docker-compose down -v"
elif command -v docker >/dev/null 2>&1; then
    echo "   docker compose down -v"
fi
echo "   rm -rf docker/radarr"
