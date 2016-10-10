from .routes import setup_routes
from aiohttp import web

__all__ = ['run_server']

def run_server(args):
    # TODO Install authentication and authorization middleware
    app = web.Application()
    setup_routes(app)
    return app
