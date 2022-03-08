"""Middleware that creates a response context-local structlog logger with
request information bound to it.
"""

import uuid
from typing import Awaitable, Callable, List

import structlog
from aiohttp import web
from aiohttp.web.web_response import Request, StreamResponse

from templatebotaide.logging import response_logger

Handler = Callable[[Request], Awaitable[StreamResponse]]

__all__: List[str] = []


@web.middleware
async def bind_logger(request: Request, handler: Handler) -> StreamResponse:
    """Bind request metadata to the context-local structlog logger.

    This is an aiohttp.web middleware.

    Notes
    -----
    This middleware initializes a new response-local structlog logger with
    context bound to it. All logging calls within the context of a response
    include this context. This makes it easy to search, filter, and aggregate
    logs for a specififc request. For background, see
    http://www.structlog.org/en/stable/getting-started.html#building-a-context

    The context fields are:

    ``request_id``
       A random UUID4 string that uniquely identifies the request.
    ``path``
       The path of the request.
    ``method``
       The http method of the request.

    Examples
    --------
    **Setting up the middleware**

    Use the `templatebotaide.middleware.setup_middleware` function to set this
    up:

    .. code-block:: python

       app = web.Application()
       setup_middleware(app)

    **Using the logger**

    Within a handler, you can access the logger directly from the 'logger'
    key of the request object:

    .. code-block:: python

       @routes.get('/')
       async def get_index(request):
           logger = request['logger']
           logger.info('Logged message', somekey='somevalue')

    If the request object is not available, you can still get the logger
    through the `templatebotaide.logging.get_response_logger` function:

    .. code-block:: python

       from templatebotaide.logging import get_response_logger

       logger = get_response_logger()
       logger.info('My message', somekey='somevalue')

    Under the hood, you can also get this logger from the
    `templatebotaide.logging.response_logger` context variable. For example:

    .. code-block:: python

       from templatebotaide.logging import response_logger

       logger = response_logger.get()
       logger.info('My message', somekey='somevalue')

    The ``response_logger.get()`` syntax is because ``response_logger`` is a
    `contextvars.ContextVar`. A `~contextvars.ContextVar` is isolated to each
    asyncio Task, which makes it great for storing context specific to each
    reponse.

    The ``request['logger']`` and `templatebotaide.logging.get_response_logger`
    APIs are the best ways to get the logger.

    **Logger name**

    By default, the logger is named for the ``api.lsst.codes/loggerName``
    configuration field. If that configuration is not set, the logger name
    falls back to ``__name__``.
    """
    try:
        logger_name = request.config_dict["api.lsst.codes/loggerName"]
    except KeyError:
        logger_name = __name__
    logger = structlog.get_logger(logger_name)
    logger = logger.new(
        request_id=str(uuid.uuid4()),
        path=request.path,
        method=request.method,
    )

    # Add the logger to the ContextVar
    response_logger.set(logger)

    # Also add the logger to the request instance
    request["logger"] = logger

    response = await handler(request)

    return response
