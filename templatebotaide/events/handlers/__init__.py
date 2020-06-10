__all__ = [
    'handle_generic_prerender',
    'handle_document_prerender',
    'handle_document_postrender',
    'handle_technote_prerender',
    'handle_technote_postrender',
]

from .genericprerender import handle_generic_prerender
from .documentprerender import handle_document_prerender
from .documentpostrender import handle_document_postrender
from .technoteprerender import handle_technote_prerender
from .technotepostrender import handle_technote_postrender
