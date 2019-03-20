__all__ = ('handle_generic_prerender',)


async def handle_generic_prerender(*, event, schema, app, logger):
    logger.info('In handle_generic_prerender', event=event)
