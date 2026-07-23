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

from hn_jobs.middleware import SentryASGIMetricsMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hn_jobs.settings.production")

django_application = get_asgi_application()

from mcp_server.server import mcp  # noqa: E402

mcp_http_application = mcp.http_app(
    path="/",
    json_response=True,
    stateless_http=True,
)
mcp_application = SentryASGIMetricsMiddleware(
    mcp_http_application,
    route_name="mcp",
)

application = Starlette(
    routes=[
        Mount("/mcp", app=mcp_application),
        Mount("/", app=django_application),
    ],
    lifespan=mcp_http_application.lifespan,
)
