from aiohttp_security.abc import AbstractAuthorizationPolicy


class ActiveDirectoryPolicy(AbstractAuthorizationPolicy):
    async def authorized_userid(self, identity):
        return identity

    async def permits(self, identity, permission, context=None):
        if identity is None:
            return False
        return True
