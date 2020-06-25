"""Post-render handler for technotes."""

__all__ = ('handle_technote_postrender',)

from templatebotaide.slack import post_message
from templatebotaide.events.handlers.utilities import pr_latex_submodules


async def handle_technote_postrender(*, event, schema, app, logger):
    """Handle a ``templatebot-postrender`` event for a technote-type of
    template.

    Parameters
    ----------
    event : `dict`
        The parsed content of the ``templatebot-postrender`` event's message.
    schema : `dict`
        The Avro schema corresponding to the ``event``.
    app : `aiohttp.web.Application`
        The app instance.
    logger
        A `structlog` logger instance with bound context related to the
        Kafka event.
    """
    logger.debug('In handle_technote_postrender', event_data=event)

    if event['template_name'] in ('technote_latex', 'technote_aastex'):
        # Handle the configuration PR for a LaTeX technote to add the
        # lsst-texmf submodule.
        try:
            pr_data = await pr_latex_submodules(
                event=event,
                app=app,
                logger=logger
            )
            if event['slack_username'] is not None:
                await post_message(
                    text=(
                        f"<@{event['slack_username']}>, I've submitted a "
                        "pull request adding the `lsst-texmf` submodule. "
                        "It's optional but recommended:\n\n"
                        f"{pr_data['html_url']}"
                    ),
                    channel=event['slack_channel'],
                    thread_ts=event['slack_thread_ts'],
                    logger=logger,
                    app=app
                )
        except Exception:
            logger.exception(
                'Failed to PR latex submodules for technote',
                github_repo=event['github_repo'])
            if event['slack_username'] is not None:
                await post_message(
                    text=(
                        "Something went wrong adding the lsst-texmf submodule "
                        f"to {event['github_repo']}. Contact SQuaRE for help."
                    ),
                    channel=event['slack_channel'],
                    thread_ts=event['slack_thread_ts'],
                    logger=logger,
                    app=app
                )
