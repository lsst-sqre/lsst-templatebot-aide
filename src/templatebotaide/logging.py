"""Context-local logger."""

from contextvars import ContextVar

from structlog.stdlib import BoundLogger

__all__ = ["response_logger", "get_response_logger"]


response_logger: ContextVar[BoundLogger] = ContextVar("response_logger")
"""A context-local structlog logger.

This logger is set by templatebot.middleware.logging.

See also
--------
get_response_logger

Examples
--------
Usage:

>>> logger = response_logger.get()
>>> logger.info(key='value')
"""


def get_response_logger() -> BoundLogger:
    """Get the context-local structlog logger with bound request context.

    This logger is set by `templatebot.middleware.logging`.

    Examples
    --------
    Usage:

    .. code-block:: python

       from templatebot.logging import get_response_logger
       logger = get_response_logger()
       logger.info('Some message', somekey='somevalue')

    An alternative way to get the logger is through the ``request`` instance
    inside the handler. For example:

    .. code-block:: python

       @routes.get('/')
       async def get_index(request):
           logger = request['logger']
           logger.info('Logged message', somekey='somevalue')
    """
    return response_logger.get()
