#!/bin/bash
# Run complete integration test suite

set -e

echo "🧪 Prompt-Based Movie Mapper Integration Test Suite"
echo "=================================================="

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found."
    exit 1
fi

echo "✅ Prerequisites check passed"

# Set up environment
echo ""
echo "🏗️  Setting up test environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    make venv-create
fi

# Install dependencies
echo "📚 Installing dependencies..."
make install-dev

# Start Docker services
echo "🐳 Starting Docker services..."
make docker-up

# Create test movies if they don't exist
if [ ! -d "test_movies" ]; then
    echo "🎬 Creating minimal test movies..."
    make test-movies
else
    echo "🎬 Test movies already exist (~332KB total)"
fi

# Wait a bit more for services to stabilize
echo "⏳ Waiting for services to stabilize..."
sleep 5

# Run tests
echo ""
echo "🧪 Running integration tests..."
echo "================================"

# Set test environment variables
export PYTHONPATH="${PWD}/src:${PYTHONPATH}"

# Run the integration tests
if make test-integration; then
    echo ""
    echo "🎉 Integration tests PASSED!"
    exit_code=0
else
    echo ""
    echo "❌ Integration tests FAILED!"
    exit_code=1
fi

# Cleanup
echo ""
echo "🧹 Cleaning up..."
make docker-down

echo ""
if [ $exit_code -eq 0 ]; then
    echo "✅ Integration test suite completed successfully!"
else
    echo "❌ Integration test suite failed!"
    echo ""
    echo "💡 Troubleshooting tips:"
    echo "   - Check Docker logs: make docker-logs"
    echo "   - Verify test files: ls test_movies/"
    echo "   - Check configuration: cat config/config.example.yaml"
    echo "   - Run unit tests first: make test-unit"
fi

exit $exit_code
