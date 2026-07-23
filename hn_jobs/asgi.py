"""
ASGI config for hn_jobs project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.routing import Mount

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hn_jobs.settings.production")

django_application = get_asgi_application()

from mcp_server.server import mcp  # noqa: E402

mcp_application = mcp.http_app(
    path="/",
    json_response=True,
    stateless_http=True,
)

application = Starlette(
    routes=[
        Mount("/mcp", app=mcp_application),
        Mount("/", app=django_application),
    ],
    lifespan=mcp_application.lifespan,
)
