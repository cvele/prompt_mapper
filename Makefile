# Makefile for Prompt-Based Movie Mapper
# Cross-platform compatible (macOS, Linux, Windows with WSL/MSYS2)

SHELL := /bin/bash
PYTHON := python3
VENV_DIR := .venv
SRC_DIR := src
TESTS_DIR := tests

# Platform detection
# Detect the platform and shell environment
UNAME_S := $(shell uname -s 2>/dev/null || echo "Windows")
ifeq ($(UNAME_S),Darwin)
    PLATFORM := macos
    PYTHON := python3
    ACTIVATE := source $(VENV_DIR)/bin/activate &&
    PIP := pip
else ifeq ($(UNAME_S),Linux)
    PLATFORM := linux
    PYTHON := python3
    ACTIVATE := source $(VENV_DIR)/bin/activate &&
    PIP := pip
else ifneq (,$(findstring MINGW,$(UNAME_S)))
    # Git Bash on Windows (MINGW64_NT, MINGW32_NT)
    PLATFORM := windows-gitbash
    PYTHON := python
    ACTIVATE := source $(VENV_DIR)/Scripts/activate &&
    PIP := python -m pip
else ifneq (,$(findstring MSYS,$(UNAME_S)))
    # MSYS2 on Windows
    PLATFORM := windows-msys
    PYTHON := python
    ACTIVATE := source $(VENV_DIR)/Scripts/activate &&
    PIP := python -m pip
else ifeq ($(OS),Windows_NT)
    # Native Windows
    PLATFORM := windows
    PYTHON := python
    ACTIVATE := $(VENV_DIR)\Scripts\activate.bat &&
    PIP := python -m pip
else
    # Default to Unix-like
    PLATFORM := unix
    PYTHON := python3
    ACTIVATE := source $(VENV_DIR)/bin/activate &&
    PIP := pip
endif

.PHONY: help install install-dev setup clean test lint format type-check run build dist clean-dist venv-create venv-clean

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Virtual Environment Management
venv-create: ## Create virtual environment
	@echo "Creating virtual environment for $(PLATFORM)..."
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Virtual environment created at $(VENV_DIR)"

venv-clean: ## Remove virtual environment
	@echo "Removing virtual environment..."
	rm -rf $(VENV_DIR)

venv-activate: ## Activate virtual environment
	@echo "Activating virtual environment..."
	$(ACTIVATE)

# Installation
install: venv-create ## Install package and dependencies
	@echo "Installing package and dependencies..."
	$(ACTIVATE) $(PIP) install --upgrade pip setuptools wheel
	$(ACTIVATE) $(PIP) install -e .

install-dev: venv-create ## Install package with development dependencies
	@echo "Installing package with development dependencies..."
	$(ACTIVATE) $(PIP) install --upgrade pip setuptools wheel
	$(ACTIVATE) $(PIP) install -e ".[dev]"
	@if [ -f requirements-dev.txt ]; then $(ACTIVATE) $(PIP) install -r requirements-dev.txt; fi
	$(ACTIVATE) pre-commit install

install-binary: venv-create ## Install package with minimal dependencies for binary builds
	@echo "Installing package with binary build dependencies..."
	$(ACTIVATE) $(PIP) install --upgrade pip setuptools wheel
	$(ACTIVATE) $(PIP) install -e .
	$(ACTIVATE) $(PIP) install pyinstaller>=5.0.0

# Setup
setup: install-dev ## Complete development setup
	@echo "Setting up development environment..."
	@if [ ! -f config/config.yaml ]; then \
		mkdir -p config; \
		cp config/config.example.yaml config/config.yaml; \
		echo "Created config/config.yaml from example"; \
	fi
	@echo "Setup complete!"

# Code Quality
lint: type-check ## Run linting (matches pre-commit hooks)
	$(ACTIVATE) flake8 $(SRC_DIR) $(TESTS_DIR) scripts/
	$(ACTIVATE) isort --check-only $(SRC_DIR) $(TESTS_DIR) scripts/
	$(ACTIVATE) black --check $(SRC_DIR) $(TESTS_DIR) scripts/

format: ## Format code
	$(ACTIVATE) isort $(SRC_DIR) $(TESTS_DIR) scripts/
	$(ACTIVATE) black $(SRC_DIR) $(TESTS_DIR) scripts/

type-check: ## Run type checking
	$(ACTIVATE) mypy $(SRC_DIR)

pre-commit-check: ## Run all pre-commit checks locally
	$(ACTIVATE) pre-commit run --all-files

pre-commit-install: ## Install pre-commit hooks
	$(ACTIVATE) pre-commit install

# Testing
test: ## Run unit tests only
	$(ACTIVATE) python -m pytest $(TESTS_DIR)/unit -v

test-unit: ## Run unit tests only
	$(ACTIVATE) python -m pytest $(TESTS_DIR)/unit -v

test-integration: integration-setup ## Run integration tests (requires test environment)
	$(ACTIVATE) python -m pytest $(TESTS_DIR)/integration -v -m integration
	$(MAKE) integration-teardown

test-all: ## Run all tests
	$(ACTIVATE) python -m pytest $(TESTS_DIR) -v

test-cov: ## Run tests with coverage
	$(ACTIVATE) python -m pytest $(TESTS_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing -v

test-integration-cov: ## Run integration tests with coverage
	$(ACTIVATE) python -m pytest $(TESTS_DIR)/integration --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing -v -m integration

# Application
run: ## Run the application
	$(ACTIVATE) prompt-mapper --help

# Build and Distribution
build: clean-dist ## Build distribution packages
	$(ACTIVATE) python -m build

dist: build ## Build and check distribution
	$(ACTIVATE) twine check dist/*

# Binary Distribution
build-binary: clean-dist install-binary ## Build standalone executable with PyInstaller
	$(ACTIVATE) pyinstaller prompt_mapper.spec --clean --noconfirm
	@echo "✅ Binary built successfully!"
	@ls -la dist/

build-binaries-all: ## Build binaries for all platforms (requires cross-compilation setup)
	@echo "Building binaries for all platforms..."
	$(MAKE) build-binary

clean-dist: ## Clean distribution files
	rm -rf build/ dist/ *.egg-info/

# Cleanup
clean: clean-dist ## Clean all generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/

# Development helpers
requirements: ## Generate requirements.txt
	$(ACTIVATE) $(PIP) freeze > requirements.txt

check: lint test-unit ## Run all checks (lint, unit tests)
check-strict: lint type-check test-unit ## Run all checks including type checking
check-pre-commit: pre-commit-check ## Run pre-commit checks (matches CI exactly)

# Docker and Integration Testing
docker-up: ## Start test environment (Radarr)
	./scripts/start_test_env.sh

docker-down: ## Stop test environment
	./scripts/stop_test_env.sh

docker-logs: ## Show Docker container logs
	docker-compose logs -f radarr

test-movies: ## Create test movie files
	@echo "📁 Creating test movie files..."
	@echo "💡 Using MOVIES_DIR: $${MOVIES_DIR:-./test_movies}"
	@LC_ALL=C.UTF-8 LANG=C.UTF-8 python scripts/create_test_movies.py

integration-setup: docker-up test-movies ## Set up complete integration test environment
	@echo "Waiting for Radarr to be ready..."
	@echo "💡 Test movies location: $${MOVIES_DIR:-./test_movies}"
	@for i in {1..30}; do \
		if curl -f http://localhost:7878/ping >/dev/null 2>&1; then \
			echo "✅ Radarr is ready!"; \
			break; \
		fi; \
		echo "⏳ Attempt $$i/30: Waiting for Radarr..."; \
		sleep 2; \
	done
	@./scripts/setup_radarr.sh
	@echo "Integration test environment ready!"

integration-teardown: docker-down ## Tear down integration test environment
	@echo "Integration test environment stopped"

# Platform-specific helpers
info: ## Show platform and environment info
	@echo "Platform: $(PLATFORM)"
	@echo "Python: $(PYTHON)"
	@echo "Virtual env: $(VENV_DIR)"
	@echo "Activation: $(ACTIVATE)"
	@echo "PIP: $(PIP)"
	@echo "UNAME_S: $(UNAME_S)"
	@echo "OS: $(OS)"
	@if [ -d "$(VENV_DIR)" ]; then \
		echo "Virtual environment exists"; \
		$(ACTIVATE) python --version; \
	else \
		echo "Virtual environment not found"; \
	fi
