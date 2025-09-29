#!/bin/bash
# Stop test environment

set -e

echo "🛑 Stopping test environment..."

# Stop Docker Compose services
docker-compose down

echo "✅ Test environment stopped."
echo ""
echo "💡 To clean up completely (remove volumes):"
echo "   docker-compose down -v"
echo "   rm -rf docker/radarr"
