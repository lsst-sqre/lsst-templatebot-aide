"""Administrative command line interface."""

from typing import Optional

import click
from aiohttp.web import run_app

from templatebotaide.app import create_app

__all__ = ("main", "help", "run")

# Add -h as a help shortcut option
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(message="%(version)s")
@click.pass_context
def main(ctx: click.Context) -> None:
    """templatebot-aide

    Admin and dev commands for lsst-templatebot-aide.
    """
    # Subcommands should use the click.pass_obj decorator to get this
    # ctx object as the first argument.
    ctx.obj = {}


@main.command()
@click.argument("topic", default=None, required=False, nargs=1)
@click.pass_context
def help(ctx: click.Context, topic: Optional[str]) -> None:
    """Show help for any command."""
    # The help command implementation is taken from
    # https://www.burgundywall.com/post/having-click-help-subcommand
    if topic:
        if topic in main.commands:
            click.echo(main.commands[topic].get_help(ctx))
        else:
            raise click.UsageError(f"Unknown help topic {topic}", ctx)
    else:
        assert ctx.parent
        click.echo(ctx.parent.get_help())


@main.command()
@click.option(
    "--port", default=8080, type=int, help="Port to run the application on."
)
@click.pass_context
def run(ctx: click.Context, port: int) -> None:
    """Run the application (for production)."""
    app = create_app()
    run_app(app, port=port)
