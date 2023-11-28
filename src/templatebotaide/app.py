"""Application factory for the aiohttp.web-based app."""

__all__ = ["create_app"]

import asyncio
import logging
import ssl
import sys
from pathlib import Path
from typing import Any, AsyncIterator, List

import cachetools
import structlog
from aiohttp import ClientSession, web
from aiokafka import AIOKafkaProducer
from gidgethub.aiohttp import GitHubAPI
from kafkit.registry import Serializer
from kafkit.registry.aiohttp import RegistryApi

from .config import create_config
from .events.router import consume_events
from .middleware import setup_middleware
from .routes import init_root_routes, init_routes


def create_app() -> web.Application:
    """Create the aiohttp.web application."""
    config = create_config()
    configure_logging(
        profile=config["api.lsst.codes/profile"],
        log_level=config["api.lsst.codes/logLevel"],
        logger_name=config["api.lsst.codes/loggerName"],
    )

    root_app = web.Application()
    for key, value in config.items():
        root_app[key] = value
    root_app.add_routes(init_root_routes())
    root_app.cleanup_ctx.append(init_http_session)
    root_app.cleanup_ctx.append(init_gidgethub_session)
    root_app.cleanup_ctx.append(configure_kafka_ssl)
    root_app.cleanup_ctx.append(init_producer)
    root_app.cleanup_ctx.append(init_avro_serializer)
    root_app.on_startup.append(start_events_listener)
    root_app.on_cleanup.append(stop_events_listener)

    # Create sub-app for the app's public APIs at the correct prefix
    prefix = "/" + root_app["api.lsst.codes/name"]
    app = web.Application()
    setup_middleware(app)
    app.add_routes(init_routes())
    app["root"] = root_app  # to make the root app's configs available
    root_app.add_subapp(prefix, app)

    logger = structlog.get_logger(root_app["api.lsst.codes/loggerName"])
    logger.info("Started lsst-templatebot-aide")

    return root_app


def configure_logging(
    profile: str = "development",
    log_level: str = "info",
    logger_name: str = "templatebotaide",
) -> None:
    """Configure logging and structlog."""
    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger(logger_name)
    logger.addHandler(stream_handler)
    logger.setLevel(log_level.upper())

    if profile == "production":
        # JSON-formatted logging
        processors: List[Any] = [
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
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


async def init_http_session(app: web.Application) -> AsyncIterator[None]:
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
    app["api.lsst.codes/httpSession"] = session
    yield

    # Cleanup phase
    await app["api.lsst.codes/httpSession"].close()


async def init_gidgethub_session(app: web.Application) -> AsyncIterator[None]:
    """Create a Gidgethub client session to access the GitHub api.

    Notes
    -----
    Use this function as a cleanup content.

    Access the client as ``app['templatebot-aide/gidgethub']``.
    """
    session = app["api.lsst.codes/httpSession"]
    token = app["templatebot-aide/githubToken"]
    username = app["templatebot-aide/githubUsername"]
    cache: cachetools.LRUCache[Any, Any] = cachetools.LRUCache(maxsize=500)
    gh = GitHubAPI(session, username, oauth_token=token, cache=cache)
    app["templatebot-aide/gidgethub"] = gh

    yield

    # No cleanup to do


async def configure_kafka_ssl(app: web.Application) -> AsyncIterator[None]:
    """Configure an SSL context for the Kafka client (if appropriate).

    Notes
    -----
    Use this function as a `cleanup context`_:

    .. code-block:: python

       app.cleanup_ctx.append(init_http_session)
    """
    logger = structlog.get_logger(app["api.lsst.codes/loggerName"])

    ssl_context_key = "templatebot-aide/kafkaSslContext"

    if app["templatebot-aide/kafkaProtocol"] != "SSL":
        app[ssl_context_key] = None
        return

    cluster_ca_cert_path = app["templatebot-aide/clusterCaPath"]
    client_ca_cert_path = app["templatebot-aide/clientCaPath"]
    client_cert_path = app["templatebot-aide/clientCertPath"]
    client_key_path = app["templatebot-aide/clientKeyPath"]

    if cluster_ca_cert_path is None:
        raise RuntimeError("Kafka protocol is SSL but cluster CA is not set")
    if client_cert_path is None:
        raise RuntimeError("Kafka protocol is SSL but client cert is not set")
    if client_key_path is None:
        raise RuntimeError("Kafka protocol is SSL but client key is not set")

    if client_ca_cert_path is not None:
        logger.info("Concatenating Kafka client CA and certificate files.")
        # Need to contatenate the client cert and CA certificates. This is
        # typical for Strimzi-based Kafka clusters.
        client_ca = Path(client_ca_cert_path).read_text()
        client_cert = Path(client_cert_path).read_text()
        new_client_cert = "\n".join([client_cert, client_ca])
        new_client_cert_path = (
            app["templatebot-aide/certCacheDir"] / "client.crt"
        )
        new_client_cert_path.write_text(new_client_cert)
        client_cert_path = str(new_client_cert_path)

    # Create a SSL context on the basis that we're the client authenticating
    # the server (the Kafka broker).
    ssl_context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH, cafile=cluster_ca_cert_path
    )
    # Add the certificates that the Kafka broker uses to authenticate us.
    ssl_context.load_cert_chain(
        certfile=client_cert_path, keyfile=client_key_path
    )
    app[ssl_context_key] = ssl_context

    logger.info("Created Kafka SSL context")

    yield


async def start_events_listener(app: web.Application) -> None:
    """Start the Kafka consumer for templatebot events as a background task
    (``on_startup`` signal handler).
    """
    app["templatebot-aide/events_consumer_task"] = app.loop.create_task(
        consume_events(app)
    )


async def stop_events_listener(app: web.Application) -> None:
    """Stop the Kafka consumer for templatebot events (``on_cleanup`` signal
    handler).
    """
    app["templatebot-aide/events_consumer_task"].cancel()
    await app["templatebot-aide/events_consumer_task"]


async def init_producer(app: web.Application) -> AsyncIterator[None]:
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
    logger = structlog.get_logger(app["api.lsst.codes/loggerName"])
    logger.info("Starting Kafka producer")
    loop = asyncio.get_running_loop()
    producer = AIOKafkaProducer(
        loop=loop,
        bootstrap_servers=app["templatebot-aide/brokerUrl"],
        ssl_context=app["templatebot-aide/kafkaSslContext"],
        security_protocol=app["templatebot-aide/kafkaProtocol"],
    )
    await producer.start()
    app["templatebot-aide/producer"] = producer
    logger.info("Finished starting Kafka producer")

    yield

    # cleanup phase
    logger.info("Shutting down Kafka producer")
    await producer.stop()


async def init_avro_serializer(app: web.Application) -> AsyncIterator[None]:
    """Initialize the Avro serializer for ``templatebot.render-ready``
    messages.

    Access the serializer as::

        app['templatebot-aide/renderreadySerializer']

    Access the templatebot-render_ready topic name::

        app['templatebot-aide/renderreadyTopic']
    """
    logger = structlog.get_logger(app["api.lsst.codes/loggerName"])
    logger.info("Starting Kafka producer")

    subject = "templatebot.render_ready_v1"
    if app["templatebot-aide/subjectSuffix"]:
        v = app["templatebot-aide/subjectSuffix"]
        subject = f"{subject}{v}"

    logger.debug("Subject name", name=subject)

    registry = RegistryApi(
        session=app["api.lsst.codes/httpSession"],
        url=app["templatebot-aide/registryUrl"],
    )
    schema_info = await registry.get_schema_by_subject(
        subject, version="latest"
    )
    serializer = Serializer(
        schema=schema_info["schema"], schema_id=schema_info["id"]
    )

    app["templatebot-aide/renderreadySerializer"] = serializer

    yield
