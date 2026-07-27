from asgiref.sync import sync_to_async
from django.db import close_old_connections
from starlette.responses import JSONResponse

from users.api_keys import authenticate_api_key, parse_bearer_api_key


def authenticate_api_key_with_fresh_connection(api_key):
    close_old_connections()
    try:
        return authenticate_api_key(api_key)
    finally:
        close_old_connections()


authenticate_api_key_async = sync_to_async(authenticate_api_key_with_fresh_connection, thread_sensitive=False)


class APIKeyAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = {name.lower(): value for name, value in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        api_key = parse_bearer_api_key(authorization)
        user = None
        if api_key:
            user = await authenticate_api_key_async(api_key)

        if user is None:
            response = JSONResponse(
                {"error": "Unauthorized"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            return await response(scope, receive, send)

        scope["user"] = user
        return await self.app(scope, receive, send)
