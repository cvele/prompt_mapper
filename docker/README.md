# Docker Integration Testing Environment

This directory contains the Docker setup for integration testing the Prompt-Based Movie Mapper.

## Services

### Radarr
- **Image**: `lscr.io/linuxserver/radarr:latest`
- **Port**: 7878
- **Purpose**: Movie management and file import testing

### Test Server (Optional)
- **Image**: `nginx:alpine`
- **Port**: 8080
- **Purpose**: Serve test movie files for download testing

## Quick Start

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f radarr

# Stop services
docker-compose down
```

## Directory Structure

```
docker/
├── radarr/
│   ├── config/          # Radarr configuration
│   ├── movies/          # Movie library
│   └── downloads/       # Download folder
└── nginx.conf           # Nginx configuration
```

## Radarr Setup

After starting Radarr for the first time:

1. Open http://localhost:7878
2. Complete the setup wizard
3. Configure:
   - Root folder: `/movies`
   - Quality profiles
   - Download clients (optional)

## Integration with Tests

The integration tests expect:
- Radarr running on port 7878
- Test movies in `../test_movies/`
- Radarr API accessible without authentication (for testing)

## Volumes

- `./radarr/config:/config` - Radarr configuration persistence
- `./radarr/movies:/movies` - Movie library
- `./radarr/downloads:/downloads` - Downloads
- `../test_movies:/test_movies:ro` - Read-only test files

## Environment Variables

- `PUID=1000` - User ID for file permissions
- `PGID=1000` - Group ID for file permissions
- `TZ=UTC` - Timezone

## Health Checks

Radarr includes a health check that pings the service every 30 seconds.

## Troubleshooting

### Port Already in Use
```bash
# Check what's using port 7878
lsof -i :7878

# Or use different port
docker-compose up -d --scale radarr=0
docker run -d -p 7879:7878 --name radarr-test lscr.io/linuxserver/radarr:latest
```

### Permission Issues
```bash
# Fix ownership
sudo chown -R 1000:1000 docker/radarr/
```

### Container Won't Start
```bash
# Check logs
docker-compose logs radarr

# Remove and recreate
docker-compose down -v
docker-compose up -d
```

## Cleanup

```bash
# Stop and remove containers
docker-compose down

# Remove volumes and data
docker-compose down -v
rm -rf radarr/
```
