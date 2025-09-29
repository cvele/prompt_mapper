#!/bin/bash
# Setup Radarr with basic configuration

export $(cat .env | xargs)

echo "🔧 Setting up Radarr with basic configuration..."

# Check if Radarr is running
if ! curl -s http://localhost:7878/ping >/dev/null; then
    echo "❌ Radarr is not running. Start with: make docker-up"
    exit 1
fi

echo "✅ Radarr is running"

# Create root folder if it doesn't exist
echo "📁 Setting up root folder..."
ROOT_FOLDER_DATA='{
    "path": "/movies",
    "accessible": true,
    "freeSpace": 0,
    "unmappedFolders": []
}'

# Try to add root folder (will fail if already exists, which is fine)
curl -s -X POST \
    -H "X-Api-Key: $RADARR_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$ROOT_FOLDER_DATA" \
    http://localhost:7878/api/v3/rootfolder >/dev/null 2>&1

# Check root folders
echo "📋 Available root folders:"
curl -s -H "X-Api-Key: $RADARR_API_KEY" http://localhost:7878/api/v3/rootfolder | python -m json.tool

# Check quality profiles
echo ""
echo "🎯 Available quality profiles:"
curl -s -H "X-Api-Key: $RADARR_API_KEY" http://localhost:7878/api/v3/qualityprofile | python -c "
import sys, json
data = json.load(sys.stdin)
for profile in data:
    print(f'  ID: {profile[\"id\"]}, Name: {profile[\"name\"]}')
"

echo ""
echo "✅ Radarr setup complete!"
echo "💡 You can now test movie addition with: make run-test"
