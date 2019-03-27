"""Post-render handler for technotes.
"""

__all__ = ('handle_technote_postrender',)

from templatebotaide.lsstthedocs import register_ltd_product
from templatebotaide.travisci import (
    activate_travis, sync_travis_account, make_travis_repo_url)
from templatebotaide.slack import post_message


async def handle_technote_postrender(*, event, schema, app, logger):
    """Handle a ``templatebot-postrender`` event for a technote-type of
    template.

    This handler activates Travis CI for the repository.

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

    github_repo_url_parts = event['github_repo'].split('/')
    slug = '/'.join((github_repo_url_parts[-2], github_repo_url_parts[-1]))
    travis_url = make_travis_repo_url(slug)

    ltd_slug = '-'.join((event['variables']['series'].lower(),
                         event['variables']['serial_number']))

    try:
        ltd_product = await register_ltd_product(
            slug=ltd_slug,
            title=event['variables']['title'],
            github_repo=event['github_repo'],
            app=app,
            logger=logger)
        if event['slack_username'] is not None:
            await post_message(
                text="I've set up the technote on _LSST the Docs._ Your "
                     f"document will appear at {ltd_product['published_url']}",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
    except Exception:
        logger.exception(
            'Failed to create the LTD product',
            ltd_slug=ltd_slug)
        if event['slack_username'] is not None:
            await post_message(
                text="Something went wrong setting up _LSST the Docs._ I will "
                     "continue to configure the technote, but docs won't be "
                     "available right away. Contact SQuaRE for help.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )

    try:
        await sync_travis_account(slug=slug, app=app, logger=logger)
    except Exception:
        if event['slack_username'] is not None:
            await post_message(
                text="Something went wrong syncing with Travis. "
                     ":crying_cat_face: I can't fix it.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
        raise

    try:
        await activate_travis(slug=slug, app=app, logger=logger)
        if event['slack_username'] is not None:
            await post_message(
                text=f"I've activated Travis CI: {travis_url}",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app)
    except Exception:
        if event['slack_username'] is not None:
            await post_message(
                text=f"Something went wrong activating `{slug}` with Travis. "
                     ":crying_cat_face: I can't fix it.",
                channel=event['slack_channel'],
                thread_ts=event['slack_thread_ts'],
                logger=logger,
                app=app
            )
        raise
