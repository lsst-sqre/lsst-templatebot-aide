"""Post-render handler for technotes.
"""

__all__ = ('handle_technote_postrender',)

from templatebotaide.travisci import (
    activate_travis, sync_travis_account, make_travis_repo_url)
from templatebotaide.slack import post_message


async def handle_technote_postrender(*, event, schema, app, logger):
    """Handle a ``templatebot-postrender`` event for a technote-type of
    template.

    This handler activates Travis CI for the repository.
    """
    logger.debug('In handle_technote_postrender', event_data=event)

    github_repo_url_parts = event['github_repo'].split('/')
    slug = '/'.join((github_repo_url_parts[-2], github_repo_url_parts[-1]))
    travis_url = make_travis_repo_url(slug)

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
