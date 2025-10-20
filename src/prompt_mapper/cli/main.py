"""Main CLI entry point."""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click

from .. import __version__
from ..config import ConfigManager
from ..core.models import ProcessingResult, SessionSummary
from ..infrastructure import Container, setup_logging
from ..utils import ConfigurationError, PromptMapperError


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--dry-run", is_flag=True, help="Run without making changes")
@click.version_option(version=__version__, prog_name="prompt-mapper")
@click.pass_context
def cli(ctx: click.Context, config: Optional[Path], verbose: bool, dry_run: bool) -> None:
    """Prompt-Based Movie Mapper - Match local movies with TMDb and Radarr."""
    # Initialize context object
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run
    ctx.obj["config_path"] = config

    # Skip configuration loading for commands that don't need it
    if ctx.invoked_subcommand == "init":
        return

    try:
        # Load configuration
        config_manager = ConfigManager(config)
        app_config = config_manager.load_config()

        # Override dry-run from command line
        if dry_run:
            app_config.app.dry_run = True

        # Set up logging
        if verbose:
            app_config.logging.level = "DEBUG"
        setup_logging(app_config.logging)

        # Create container
        container = Container(config_manager)
        container.configure_default_services()

        ctx.obj["config"] = app_config
        ctx.obj["container"] = container

    except (ConfigurationError, FileNotFoundError, ValueError) as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Initialization error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--prompt", "-p", help="Custom prompt for movie resolution")
@click.option("--profile", help="Use named prompt profile")
@click.option("--batch", is_flag=True, help="Process multiple directories")
@click.option("--auto-add", is_flag=True, help="Automatically add movies to Radarr")
@click.option("--auto-import", is_flag=True, help="Automatically import files")
@click.pass_context
def scan(
    ctx: click.Context,
    paths: List[Path],
    prompt: Optional[str],
    profile: Optional[str],
    batch: bool,
    auto_add: bool,
    auto_import: bool,
) -> None:
    """Scan directories for movies and process them."""
    config = ctx.obj["config"]
    container = ctx.obj["container"]

    # Determine prompt to use
    if prompt:
        user_prompt = prompt
    elif profile and profile in config.prompts.profiles:
        user_prompt = config.prompts.profiles[profile]
    else:
        user_prompt = config.prompts.default

    # Override config with command line options
    if auto_add:
        config.matching.auto_add_to_radarr = True
    if auto_import:
        config.matching.auto_import = True

    try:
        # Run the scan
        asyncio.run(
            _run_scan(
                container=container,
                paths=list(paths),
                user_prompt=user_prompt,
                batch=batch,
                dry_run=ctx.obj["dry_run"],
            )
        )
    except KeyboardInterrupt:
        click.echo("\nOperation cancelled by user.")
        sys.exit(1)
    except PromptMapperError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx: click.Context) -> None:
    """Validate configuration and prerequisites."""
    container = ctx.obj["container"]

    try:
        asyncio.run(_validate_setup(container))
        click.echo("All prerequisites validated successfully")
    except Exception as e:
        click.echo(f"Validation failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path.cwd() / "config" / "config.yaml",
    help="Output path for configuration file",
)
def init(output: Path) -> None:
    """Initialize configuration file."""
    try:
        if output.exists():
            if not click.confirm(f"Configuration file {output} already exists. Overwrite?"):
                return

        # Create directory if needed
        output.parent.mkdir(parents=True, exist_ok=True)

        # Create default config
        ConfigManager.create_default_config(output)
        click.echo(f"Configuration file created at: {output}")
        click.echo("Please edit the configuration file with your API keys and preferences.")

    except Exception as e:
        click.echo(f"Failed to create configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show system status and configuration."""
    config = ctx.obj["config"]
    container = ctx.obj["container"]

    click.echo("Prompt-Based Movie Mapper Status")
    click.echo("=" * 40)

    # Configuration status
    click.echo(f"LLM Provider: {config.llm.provider}")
    click.echo(f"LLM Model: {config.llm.model}")
    click.echo(f"TMDb Configured: {'✓' if config.tmdb.api_key else '✗'}")
    click.echo(f"Radarr Enabled: {'✓' if config.radarr.enabled else '✗'}")
    click.echo(f"Dry Run Mode: {'✓' if config.app.dry_run else '✗'}")

    # Try to validate services
    try:
        asyncio.run(_check_services_status(container))
    except Exception as e:
        click.echo(f"Service check failed: {e}")


async def _run_scan(
    container: Container,
    paths: List[Path],
    user_prompt: str,
    batch: bool,
    dry_run: bool,
) -> None:
    """Run the scanning process."""
    from ..core.interfaces import IMovieOrchestrator, IRadarrService, ITMDbService

    try:
        orchestrator = container.get(IMovieOrchestrator)  # type: ignore
        orchestrator.set_interactive_mode(not batch)

        # Validate prerequisites
        errors = await orchestrator.validate_prerequisites()
        if errors:
            for error in errors:
                click.echo(f"✗ {error}", err=True)
            raise PromptMapperError("Prerequisites not met")

        if len(paths) == 1 and not batch:
            # Single movie processing
            click.echo(f"Processing: {paths[0]}")
            result = await orchestrator.process_single_movie(
                path=paths[0], user_prompt=user_prompt, dry_run=dry_run
            )
            _display_result(result)
        else:
            # Batch processing
            click.echo(f"Processing {len(paths)} directories...")
            summary = await orchestrator.process_batch(
                paths=paths, user_prompt=user_prompt, dry_run=dry_run
            )
            _display_summary(summary)

    finally:
        # Cleanup HTTP sessions
        try:
            tmdb_service = container.get(ITMDbService)  # type: ignore
            if hasattr(tmdb_service, "close"):
                await tmdb_service.close()
        except Exception:
            pass

        try:
            radarr_service = container.get(IRadarrService)  # type: ignore
            if hasattr(radarr_service, "close"):
                await radarr_service.close()
        except Exception:
            pass


async def _validate_setup(container: Container) -> None:
    """Validate setup and prerequisites."""
    from ..core.interfaces import IMovieOrchestrator

    orchestrator = container.get(IMovieOrchestrator)  # type: ignore
    errors = await orchestrator.validate_prerequisites()

    if errors:
        for error in errors:
            click.echo(f"✗ {error}")
        raise PromptMapperError("Validation failed")


async def _check_services_status(container: Container) -> None:
    """Check status of external services."""
    try:
        from ..core.interfaces import IRadarrService

        radarr = container.get(IRadarrService)  # type: ignore
        if radarr.is_available():
            status = await radarr.get_system_status()
            click.echo(f"Radarr Status: ✓ {status.get('version', 'Unknown')}")
        else:
            click.echo("Radarr Status: ✗ Unavailable")
    except Exception:
        click.echo("Radarr Status: ✗ Error")


def _display_result(result: ProcessingResult) -> None:
    """Display processing result."""
    click.echo(f"Status: {result.status.value}")
    if result.movie_match:
        movie = result.movie_match.movie_info
        click.echo(f"Movie: {movie.title} ({movie.year})")
        click.echo(f"TMDb ID: {movie.tmdb_id}")
        click.echo(f"Confidence: {result.movie_match.confidence:.2f}")

    if result.radarr_action:
        click.echo(f"Radarr Action: {result.radarr_action.value}")

    if result.import_results:
        imported = sum(1 for r in result.import_results if r.imported)
        click.echo(f"Files Imported: {imported}/{len(result.import_results)}")

    if result.error_message:
        click.echo(f"Error: {result.error_message}", err=True)


def _display_summary(summary: SessionSummary) -> None:
    """Display session summary."""
    click.echo("\nSession Summary")
    click.echo("=" * 20)
    click.echo(f"Total Processed: {summary.total_processed}")
    click.echo(f"Successful: {summary.successful}")
    click.echo(f"Failed: {summary.failed}")
    click.echo(f"Skipped: {summary.skipped}")
    click.echo(f"Success Rate: {summary.success_rate:.1%}")
    click.echo(f"Movies Added: {summary.movies_added_to_radarr}")
    click.echo(f"Files Imported: {summary.files_imported}")
    click.echo(f"Total Time: {summary.total_processing_time_seconds:.1f}s")


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
