"""Administrative command line interface.
"""

__all__ = ('main', 'help', 'run')

from aiohttp.web import run_app
import click

from templatebotaide.app import create_app

# Add -h as a help shortcut option
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(message='%(version)s')
@click.pass_context
def main(ctx):
    """templatebot-aide

    Admin and dev commands for lsst-templatebot-aide.
    """
    # Subcommands should use the click.pass_obj decorator to get this
    # ctx object as the first argument.
    ctx.obj = {}


@main.command()
@click.argument('topic', default=None, required=False, nargs=1)
@click.pass_context
def help(ctx, topic, **kw):
    """Show help for any command.
    """
    # The help command implementation is taken from
    # https://www.burgundywall.com/post/having-click-help-subcommand
    if topic is None:
        click.echo(ctx.parent.get_help())
    else:
        click.echo(main.commands[topic].get_help(ctx))


@main.command()
@click.option(
    '--port', default=8080, type=int,
    help='Port to run the application on.'
)
@click.pass_context
def run(ctx, port):
    """Run the application (for production).
    """
    app = create_app()
    run_app(app, port=port)
