"""Post-render handler for technotes.
"""

__all__ = ('handle_technote_postrender',)


async def handle_technote_postrender(*, event, schema, app, logger):
    """Handle a ``templatebot-postrender`` event for a technote-type of
    template.

    This handler activates Travis CI for the repository.
    """
    logger.debug('In handle_technote_postrender', event_data=event)
