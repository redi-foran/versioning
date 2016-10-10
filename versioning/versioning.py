import asyncio
import sqlalchemy as sa
from aiohttp import web
import aiohttp_session
import aiohttp_security
from ad_auth import ActiveDirectoryPolicy
from service import routes
from service.db import tables


class DatabaseConnectionMiddlewareFactory(object):
    def __init__(self, db_engine):
        self._db_engine = db_engine
        tables.metadata.create_all(self._db_engine)

    async def __call__(self, app, handler):
        async def middleware_handler(request):
            request.db_engine = self._db_engine
            request.db_connection = self._db_engine.connect()
            return await handler(request)
        return middleware_handler


async def initialize(loop):
    db_engine = sa.create_engine("sqlite://")
    application = web.Application(loop=loop, middlewares=[DatabaseConnectionMiddlewareFactory(db_engine)])
    aiohttp_session.setup(application, aiohttp_session.SimpleCookieStorage())
    aiohttp_security.setup(application, aiohttp_security.SessionIdentityPolicy(), ActiveDirectoryPolicy())

    routes.setup_routes(application)

    handler = application.make_handler()
    server = await loop.create_server(handler, 'nydevl0008.rdti.com', 8081)
    return server, application, handler


async def finalize(server, application, handler):
    await handler.finish_connections(1.0)
    server.close()
    await server.wait_closed()
    await application.finish()
    return server, application, handler


def main():
    loop = asyncio.get_event_loop()
    server, application, handler = loop.run_until_complete(initialize(loop))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete((finalize(server, application, handler)))


if __name__ == "__main__":
    main()
