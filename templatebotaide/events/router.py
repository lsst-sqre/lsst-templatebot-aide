__all__ = ('consume_events',)

import asyncio

from aiokafka import AIOKafkaConsumer
from kafkit.registry.aiohttp import RegistryApi
from kafkit.registry import Deserializer
import structlog

from .handlers import (
    handle_generic_prerender, handle_technote_prerender,
    handle_technote_postrender)


TECHNOTE_TEMPLATES = ('technote_rst')
"""Names of templates in https://github.com/lsst/templates that correspond to
technical notes.

Technical notes have a special process for assigning document handles through
GitHub repository names in a given organization.
"""


async def consume_events(app):
    """Consume events from templatebot-related topics in SQuaRE Events (Kafka).
    """
    logger = structlog.get_logger(app['api.lsst.codes/loggerName'])

    registry = RegistryApi(
        session=app['api.lsst.codes/httpSession'],
        url=app['templatebot-aide/registryUrl'])
    deserializer = Deserializer(registry=registry)

    # Set up topic names
    if app['templatebot-aide/topicsVersion']:
        v = app['templatebot-aide/topicsVersion']
        app['templatebot-aide/prerenderTopic'] = f'templatebot-prerender-{v}'
        app['templatebot-aide/renderreadyTopic'] \
            = f'templatebot-render_ready-{v}'
        app['templatebot-aide/postrenderTopic'] = f'templatebot-postrender-{v}'
    else:
        app['templatebot-aide/prerenderTopic'] = f'templatebot-prerender'
        app['templatebot-aide/renderreadyTopic'] = 'templatebot-render_ready'
        app['templatebot-aide/postrenderTopic'] = f'templatebot-postrender'
    subscription_topic_names = [
        app['templatebot-aide/prerenderTopic'],
        app['templatebot-aide/postrenderTopic']
    ]

    # Set up the consumer group name
    if app['templatebot-aide/topicsVersion']:
        group_id = '_'.join((app["api.lsst.codes/name"],
                             app['templatebot-aide/topicsVersion']))
    else:
        group_id = app['api.lsst.codes/name']
    consumer_settings = {
        'bootstrap_servers': app['templatebot-aide/brokerUrl'],
        'group_id': group_id,
        'auto_offset_reset': 'latest'
    }
    consumer = AIOKafkaConsumer(
        loop=asyncio.get_event_loop(),
        **consumer_settings)

    try:
        await consumer.start()
        logger.info('Started Kafka consumer for events', **consumer_settings)

        logger.info('Subscribing to Kafka topics',
                    names=subscription_topic_names)
        consumer.subscribe(subscription_topic_names)

        partitions = consumer.assignment()
        while len(partitions) == 0:
            # Wait for the consumer to get partition assignment
            await asyncio.sleep(1.)
            partitions = consumer.assignment()
        logger.info(
            'Initial partition assignment for event topics',
            partitions=[str(p) for p in partitions])

        async for message in consumer:
            try:
                message_info = await deserializer.deserialize(
                    message.value, include_schema=True)
            except Exception:
                logger.exception(
                    'Failed to deserialize an event message',
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset)
                continue

            event = message_info['message']
            logger.debug(
                'New event message',
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                contents=event)

            try:
                await route_event(
                    app=app,
                    event=message_info['message'],
                    schema_id=message_info['id'],
                    schema=message_info['schema'],
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset)
            except Exception:
                logger.exception(
                    'Failed to handle event message',
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset)

    except asyncio.CancelledError:
        logger.info('consume_events task got cancelled')
    finally:
        logger.info('consume_events task cancelling')
        await consumer.stop()


async def route_event(*, event, app, schema_id, schema, topic, partition,
                      offset):
    """Route events from `consume_events` to specific handlers.
    """
    logger = structlog.get_logger(app['api.lsst.codes/loggerName'])
    logger = logger.bind(
        topic=topic, partition=partition, offset=offset, schema_id=schema_id
    )

    if topic == app['templatebot-aide/prerenderTopic']:
        if event['template_name'] in TECHNOTE_TEMPLATES:
            # Technote-type project
            await handle_technote_prerender(
                event=event,
                schema=schema,
                app=app,
                logger=logger)
        else:
            await handle_generic_prerender(
                event=event,
                schema=schema,
                app=app,
                logger=logger)

    elif topic == app['templatebot-aide/postrenderTopic']:
        if event['template_name'] in TECHNOTE_TEMPLATES:
            # Start post-render for technote projects
            await handle_technote_postrender(
                event=event,
                schema=schema,
                app=app,
                logger=logger)
