# Development Guide

## Project Structure

This project follows a clean architecture with dependency injection and SOLID principles:

```
src/prompt_mapper/
├── __init__.py                 # Package initialization
├── cli/                        # Command-line interface
│   ├── __init__.py
│   └── main.py                 # CLI entry point with Click
├── config/                     # Configuration management
│   ├── __init__.py
│   ├── config_manager.py       # YAML config loading
│   └── models.py               # Pydantic config models
├── core/                       # Core business logic
│   ├── __init__.py
│   ├── interfaces/             # Abstract interfaces (DI)
│   │   ├── __init__.py
│   │   ├── file_scanner.py
│   │   ├── llm_service.py
│   │   ├── movie_orchestrator.py
│   │   ├── movie_resolver.py
│   │   ├── radarr_service.py
│   │   └── tmdb_service.py
│   ├── models/                 # Data models
│   │   ├── __init__.py
│   │   ├── file_info.py
│   │   ├── llm_response.py
│   │   ├── movie.py
│   │   └── processing_result.py
│   └── services/               # Service implementations
│       ├── __init__.py
│       ├── file_scanner.py
│       ├── llm_services.py     # OpenAI & Anthropic
│       ├── movie_orchestrator.py
│       ├── movie_resolver.py
│       ├── radarr_service.py
│       └── tmdb_service.py
├── infrastructure/             # Cross-cutting concerns
│   ├── __init__.py
│   ├── container.py            # DI container
│   └── logging.py              # Logging setup
└── utils/                      # Utilities
    ├── __init__.py
    ├── exceptions.py           # Custom exceptions
    ├── file_utils.py           # File operations
    └── text_utils.py           # Text processing
```

## Architecture Principles

### SOLID Principles

1. **Single Responsibility**: Each class has one reason to change
   - `FileScanner`: Only handles file scanning
   - `TMDbService`: Only handles TMDb API operations
   - `MovieResolver`: Only handles movie resolution logic

2. **Open/Closed**: Extensible through interfaces
   - Add new LLM providers by implementing `ILLMService`
   - Add new metadata sources by implementing similar interfaces

3. **Liskov Substitution**: Implementations are interchangeable
   - `OpenAILLMService` and `AnthropicLLMService` are interchangeable
   - Mock implementations can replace real ones for testing

4. **Interface Segregation**: Small, focused interfaces
   - Separate interfaces for each major concern
   - No client depends on methods it doesn't use

5. **Dependency Inversion**: Depend on abstractions
   - All services depend on interfaces, not concrete classes
   - DI container manages dependencies

### Dependency Injection

The `Container` class manages all dependencies:

```python
# Registration (in container.configure_default_services())
container.register_singleton(ILLMService, OpenAILLMService)
container.register_singleton(ITMDbService, TMDbService)

# Resolution (automatic dependency injection)
orchestrator = container.get(IMovieOrchestrator)
```

### Configuration

YAML-based configuration with Pydantic validation:

```python
# Load config
config_manager = ConfigManager()
config = config_manager.load_config()

# Access typed configuration
print(config.llm.provider)  # Type-safe access
```

## Development Workflow

### Setup

```bash
make setup          # Complete development setup
make install-dev    # Install with dev dependencies
```

### Code Quality

```bash
make format         # Format code with black/isort
make lint           # Run linting (flake8)
make type-check     # Run type checking (mypy)
make test           # Run tests
make check          # Run all checks
```

### Running

```bash
make run                    # Show help
prompt-mapper init         # Create config file
make run-test-auto         # Test automated mode
make run-test              # Test interactive mode
prompt-mapper scan /path/to/movies
```

## Testing

### Test Structure

```
tests/
├── conftest.py         # Pytest fixtures
├── unit/               # Unit tests (11 tests)
│   ├── test_config.py
│   └── test_file_scanner.py
└── integration/        # Integration tests (16 tests)
    ├── conftest.py     # Integration fixtures
    ├── test_end_to_end.py
    └── test_cli_integration.py
```

### Writing Tests

```python
@pytest.mark.asyncio
async def test_file_scanner(config, sample_movie_files):
    scanner = FileScanner(config)
    result = await scanner.scan_directory(sample_movie_files)
    assert len(result.video_files) == 1
```

### Mocking

Use dependency injection for easy mocking:

```python
def test_orchestrator_with_mocks(config):
    mock_scanner = Mock()
    mock_resolver = Mock()
    mock_radarr = Mock()

    orchestrator = MovieOrchestrator(
        config, mock_scanner, mock_resolver, mock_radarr
    )
```

## Adding New Features

### New LLM Provider

1. Implement `ILLMService` interface
2. Add to container configuration
3. Update config models if needed

```python
class MyLLMService(ILLMService):
    async def resolve_movie(self, file_info, user_prompt, context=""):
        # Implementation
        pass
```

### New Metadata Source

1. Create new interface (e.g., `IIMDbService`)
2. Implement the service
3. Integrate into resolver or orchestrator

### New File Formats

1. Update `FilesConfig` extensions
2. Modify `FileScanner` logic if needed
3. Add tests

## Cross-Platform Considerations

### File Operations

Use `pathlib.Path` for all file operations:

```python
from pathlib import Path
path = Path("movies") / "The Matrix (1999)"
```

### System Commands

Avoid shell commands; use Python libraries:

```python
# Good
shutil.copy2(source, target)

# Avoid
os.system(f"cp {source} {target}")
```

### Environment Variables

Use `python-dotenv` and config expansion:

```yaml
# config.yaml
api_key: "${TMDB_API_KEY}"  # Expanded automatically
```

## Performance Considerations

### Async Operations

All I/O operations are async:

```python
# File scanning
scan_result = await file_scanner.scan_directory(path)

# API calls
candidates = await tmdb_service.search_movies(llm_response)
```

### Batch Processing

Use semaphores to limit concurrent operations:

```python
semaphore = asyncio.Semaphore(max_parallel)
async with semaphore:
    # Process item
```

### Caching

Configuration supports caching (future enhancement):

```yaml
app:
  cache_enabled: true
  cache_ttl_hours: 24
```

## Error Handling

### Custom Exceptions

Use specific exceptions for different error types:

```python
from prompt_mapper.utils import LLMServiceError, TMDbServiceError

try:
    response = await llm_service.resolve_movie(...)
except LLMServiceError as e:
    # Handle LLM-specific error
    pass
```

### Logging

Use the logging mixin:

```python
class MyService(LoggerMixin):
    def process(self):
        self.logger.info("Processing started")
        self.logger.error("Something went wrong")
```

## Deployment

### Production Setup

1. Set environment variables
2. Create production config
3. Use proper logging configuration
4. Consider using a process manager

### Current Status

The system is **production-ready** with:
- ✅ Full end-to-end functionality working
- ✅ Interactive and automated modes
- ✅ Real API integration (OpenAI, TMDb, Radarr)
- ✅ Docker test environment
- ✅ Comprehensive CI/CD pipelines
- ✅ Cross-platform support

### Docker Integration

Docker Compose environment for testing:
```bash
make docker-up         # Start Radarr test instance
make integration-setup # Complete test environment
make docker-down       # Clean up
```

### GitHub Workflows

Comprehensive CI/CD pipelines:
- **PR Validation**: Code quality, tests, security scans
- **Release Pipeline**: Cross-platform builds, GitHub releases
- **Code Quality**: Linting, formatting, type checking

### Proven Working Examples

**Serbian Title Translation:**
- Input: "Beli očnjak (2018).mkv"
- LLM Output: "White Fang (2018)"
- TMDb Match: Found with high confidence
- Radarr: Successfully added

**Batch Processing:**
- Input: 71 movie files in flat directory
- Behavior: Automatically detects and processes each movie individually
- Result: Each movie gets its own LLM analysis and TMDb match
