# Prompt-Based Movie Mapper

A powerful, prompt-driven tool for matching local movie files with canonical metadata and integrating with Radarr for automated library management.

## Features

- **Prompt-driven matching**: Use natural language to describe your naming conventions
- **Cross-platform support**: Works on macOS, Linux, and Windows
- **Standalone binaries**: No Python installation required - just download and run
- **Radarr integration**: Automatic movie addition and hard-link importing
- **TMDb integration**: Accurate metadata matching
- **Batch processing**: Efficiently handles directories with hundreds of movies
- **Configurable**: YAML-based configuration with profiles
- **Testable architecture**: Dependency injection and SOLID principles
- **Dry-run mode**: Test matching without making changes
- **Version support**: `--version` flag shows current version

## Quick Start

### Prerequisites

- Python 3.9 or higher
- Make (for build automation)
- TMDb API key
- Radarr instance (optional)

### Installation

#### Option 1: Download Standalone Binary (Recommended)

1. Go to [Releases](https://github.com/your-username/prompt_mapper/releases)
2. Download the binary for your platform:
   - `prompt-mapper-windows.exe` (Windows)
   - `prompt-mapper-linux` (Linux)
   - `prompt-mapper-macos` (macOS)
3. Make executable (Linux/macOS): `chmod +x prompt-mapper-*`

#### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/your-username/prompt_mapper.git
cd prompt_mapper

# Set up development environment
make setup

# Or just install the package
make install
```

### Configuration

1. Copy the example configuration:
```bash
cp config/config.example.yaml config/config.yaml
```

2. Edit `config/config.yaml` with your API keys and preferences.

### Basic Usage

```bash
# Check version
prompt-mapper --version

# Initialize configuration file
prompt-mapper init

# Scan a directory (automatically detects single movie vs multiple movies)
prompt-mapper -c config.yaml scan /path/to/movie/directory

# Scan with custom prompt for Serbian/Croatian titles
prompt-mapper -c config.yaml scan /path/to/movies --prompt "Serbian and Croatian titles, translate to English"

# Dry run (no actual changes to Radarr)
prompt-mapper -c config.yaml scan /path/to/movies --dry-run

# Non-interactive mode (auto-select best matches)
# Edit config.yaml: set interactive: false
prompt-mapper -c config.yaml scan /path/to/movies

# Check system status
prompt-mapper -c config.yaml status

# Validate configuration
prompt-mapper -c config.yaml validate
```

## Working Examples

### Serbian/Croatian Title Translation
```bash
# Input file: "Beli očnjak (2018).mkv"
prompt-mapper scan /movies --prompt "Serbian titles, translate to English"
# Output: Successfully identifies as "White Fang (2018)"
# Result: Added to Radarr with TMDb ID
```

### Large Directory Processing
```bash
# Directory with 290 mixed movie files
prompt-mapper -c config.yaml scan /mixed_movies --prompt "Animated movies collection"
# Behavior: Automatically detects multiple movies and processes each individually
# Performance: Limits to first 20 movies to prevent overwhelming APIs
# Result: Each movie gets analyzed separately by LLM and matched with TMDb
```

### Interactive vs Automated
```bash
# Interactive: Prompts for user confirmation
prompt-mapper scan /movies  # Uses config: interactive: true

# Automated: Auto-selects best matches
# Edit config.yaml: set interactive: false
prompt-mapper scan /movies  # No user prompts, processes automatically
```

## Development

### Environment Variables

The project supports several environment variables for configuration and CI/CD:

| Variable | Description | Default |
|----------|-------------|---------|
| `MOVIES_DIR` | Directory for test movie files | `./test_movies` |
| `PUID` | Docker container user ID | `1000` |
| `PGID` | Docker container group ID | `1000` |
| `LC_ALL` | Locale setting for UTF-8 support | `C.UTF-8` |
| `LANG` | Language setting | `C.UTF-8` |

#### CI/CD Considerations

In CI environments, the test movie creation automatically uses `$RUNNER_TEMP/test_movies` for guaranteed write permissions. The UTF-8 locale is also automatically set to handle filenames with special characters (č, ć, š, ž).

For local development with Docker:
```bash
# Set proper UID/GID to match your user
export PUID=$(id -u)
export PGID=$(id -g)

# Use a custom test movies directory
export MOVIES_DIR=/tmp/test_movies

# Start test environment
make integration-setup
```

### Make Commands

```bash
make help              # Show all available commands
make setup             # Complete development setup
make test-unit         # Run unit tests
make test-integration  # Run integration tests (requires Docker)
make test-all          # Run all tests
make lint              # Run linting
make format            # Format code
make type-check        # Run type checking
make check             # Run all checks (lint, type-check, unit tests)
make clean             # Clean generated files

# Testing and Demo
make run-test          # Interactive test with test movies (prompts for input)
make run-test-auto     # Automated test (no prompts, auto-selects)
make docker-up         # Start Radarr test environment
make docker-down       # Stop test environment
```

### Integration Testing

The project includes comprehensive integration tests with a Docker-based test environment:

```bash
# Complete integration test setup and run
./scripts/run_integration_tests.sh

# Or step by step:
make integration-setup  # Start Radarr + create minimal test movies (~332KB)
make test-integration   # Run integration tests
make integration-teardown # Clean up
```

**Test Environment Includes:**
- Radarr instance in Docker (v5.27.5.10198)
- 82 minimal dummy movie files (~332KB total) in flat structure
- Serbian/Croatian titles: "Beli očnjak", "Čarobni princ", etc.
- Real API integration: OpenAI (gpt-4o-mini), TMDb, Radarr
- Automatic batch detection for multiple movies

### Project Structure

```
src/prompt_mapper/
├── __init__.py
├── cli/                    # Command-line interface
├── config/                 # Configuration management
├── core/                   # Core business logic
│   ├── interfaces/         # Abstract interfaces
│   ├── models/            # Data models
│   └── services/          # Service implementations
├── external/              # External API clients
├── infrastructure/        # Infrastructure concerns
└── utils/                 # Utility functions

tests/                     # Test suite
config/                    # Configuration files
```

## Architecture

This project follows SOLID principles with dependency injection:

- **Single Responsibility**: Each class has one reason to change
- **Open/Closed**: Extensible through interfaces
- **Liskov Substitution**: Implementations are interchangeable
- **Interface Segregation**: Small, focused interfaces
- **Dependency Inversion**: Depend on abstractions, not concretions

## Configuration

The application uses YAML configuration with environment variable expansion:

```yaml
llm:
  provider: "openai"  # or "anthropic"
  model: "gpt-4o-mini"  # Working model
  api_key: "${OPENAI_API_KEY}"

tmdb:
  api_key: "${TMDB_API_KEY}"
  language: "en-US"

radarr:
  enabled: true
  url: "http://localhost:7878"
  api_key: "${RADARR_API_KEY}"
  default_profile:
    quality_profile_id: 1
    root_folder_path: "/movies"

matching:
  confidence_threshold: 0.95  # High for interactive prompts
  year_tolerance: 1
  auto_add_to_radarr: false

app:
  interactive: true  # Set to false for automated processing
```

### Environment Variables

Create a `.env` file with your API keys:
```bash
OPENAI_API_KEY=your_openai_key
TMDB_API_KEY=your_tmdb_key
RADARR_API_KEY=your_radarr_key
```

## License

MIT License - see LICENSE file for details.
