from aiohttp import web

from templatebotaide.routes import root_routes

__all__ = ["get_index"]


@root_routes.get("/")
async def get_index(request):
    name = request.config_dict["api.lsst.codes/name"]
    return web.Response(text=name)
