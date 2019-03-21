"""Application factory for the aiohttp.web-based app.
"""

__all__ = ('create_app',)

import asyncio
import logging
import sys

from aiohttp import web, ClientSession
from aiokafka import AIOKafkaProducer
import structlog
from gidgethub.aiohttp import GitHubAPI
import cachetools

from .config import create_config
from .routes import init_root_routes, init_routes
from .middleware import setup_middleware
from .events.router import consume_events


def create_app():
    """Create the aiohttp.web application.
    """
    config = create_config()
    configure_logging(
        profile=config['api.lsst.codes/profile'],
        log_level=config['api.lsst.codes/logLevel'],
        logger_name=config['api.lsst.codes/loggerName'])

    root_app = web.Application()
    root_app.update(config)
    root_app.add_routes(init_root_routes())
    root_app.cleanup_ctx.append(init_http_session)
    root_app.cleanup_ctx.append(init_gidgethub_session)
    root_app.cleanup_ctx.append(init_producer)
    root_app.on_startup.append(start_events_listener)
    root_app.on_cleanup.append(stop_events_listener)

    # Create sub-app for the app's public APIs at the correct prefix
    prefix = '/' + root_app['api.lsst.codes/name']
    app = web.Application()
    setup_middleware(app)
    app.add_routes(init_routes())
    app['root'] = root_app  # to make the root app's configs available
    root_app.add_subapp(prefix, app)

    logger = structlog.get_logger(root_app['api.lsst.codes/loggerName'])
    logger.info('Started lsst-templatebot-aide')

    return root_app


def configure_logging(profile='development', log_level='info',
                      logger_name='templatebotaide'):
    """Configure logging and structlog.
    """
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(logging.Formatter('%(message)s'))
    logger = logging.getLogger(logger_name)
    logger.addHandler(stream_handler)
    logger.setLevel(log_level.upper())

    if profile == 'production':
        # JSON-formatted logging
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Key-value formatted logging
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


async def init_http_session(app):
    """Create an aiohttp.ClientSession and make it available as a
    ``'api.lsst.codes/httpSession'`` key on the application.

    Notes
    -----
    Use this function as a `cleanup context`_:

    .. code-block:: python

       python.cleanup_ctx.append(init_http_session)

    The session is automatically closed on shut down.

    Access the session:

    .. code-block:: python

        session = app['api.lsst.codes/httpSession']

    .. cleanup context:
       https://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Application.cleanup_ctx
    """
    # Startup phase
    session = ClientSession()
    app['api.lsst.codes/httpSession'] = session
    yield

    # Cleanup phase
    await app['api.lsst.codes/httpSession'].close()


async def init_gidgethub_session(app):
    """Create a Gidgethub client session to access the GitHub api.

    Notes
    -----
    Use this function as a cleanup content.

    Access the client as ``app['templatebot-aide/gidgethub']``.
    """
    session = app['api.lsst.codes/httpSession']
    token = app['templatebot-aide/githubToken']
    username = app['templatebot-aide/githubUsername']
    cache = cachetools.LRUCache(maxsize=500)
    gh = GitHubAPI(session, username, oauth_token=token, cache=cache)
    app['templatebot-aide/gidgethub'] = gh

    yield

    # No cleanup to do


async def start_events_listener(app):
    """Start the Kafka consumer for templatebot events as a background task
    (``on_startup`` signal handler).
    """
    app['templatebot-aide/events_consumer_task'] = app.loop.create_task(
        consume_events(app))


async def stop_events_listener(app):
    """Stop the Kafka consumer for templatebot events (``on_cleanup`` signal
    handler).
    """
    app['templatebot-aide/events_consumer_task'].cancel()
    await app['templatebot-aide/events_consumer_task']


async def init_producer(app):
    """Initialize and cleanup the aiokafka Producer instance

    Notes
    -----
    Use this function as a cleanup context, see
    https://aiohttp.readthedocs.io/en/stable/web_reference.html#aiohttp.web.Application.cleanup_ctx

    To access the producer:

    .. code-block:: python

       producer = app['templatebot-aide/producer']
    """
    # Startup phase
    logger = structlog.get_logger(app['api.lsst.codes/loggerName'])
    logger.info('Starting Kafka producer')
    loop = asyncio.get_running_loop()
    producer = AIOKafkaProducer(
        loop=loop,
        bootstrap_servers=app['templatebot-aide/brokerUrl'])
    await producer.start()
    app['templatebot-aide/producer'] = producer
    logger.info('Finished starting Kafka producer')

    yield

    # cleanup phase
    logger.info('Shutting down Kafka producer')
    await producer.stop()
