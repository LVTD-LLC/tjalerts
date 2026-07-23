import json

import anyio
from django.test import TransactionTestCase
from django.utils import timezone
from fastmcp import Client
from mcp.types import ToolAnnotations
from starlette.testclient import TestClient

from hn_jobs.asgi import application
from jobs.choices import PostSource
from jobs.models import Company, Post
from mcp_server.server import mcp

MCP_HEADERS = {
    "accept": "application/json, text/event-stream",
    "content-type": "application/json",
}


class MCPServerTests(TransactionTestCase):
    def setUp(self):
        company = Company.objects.create(name="Acme")
        self.post = Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="Remote Python role",
            source=PostSource.REMOTE_OK,
            is_remote=True,
        )

    def test_server_exposes_only_read_only_job_tools(self):
        async def run():
            tools = await mcp.list_tools(run_middleware=False)
            self.assertEqual({tool.name for tool in tools}, {"get_job", "search_jobs"})
            for tool in tools:
                self.assertEqual(
                    tool.annotations,
                    ToolAnnotations(
                        readOnlyHint=True,
                        destructiveHint=False,
                        idempotentHint=True,
                        openWorldHint=False,
                    ),
                )

            tools_by_name = {tool.name: tool for tool in tools}
            search_tool = tools_by_name["search_jobs"]
            self.assertEqual(search_tool.output_schema["type"], "object")
            self.assertIn("jobs", search_tool.output_schema["properties"])
            self.assertEqual(
                search_tool.parameters["properties"]["source"]["anyOf"][0]["enum"],
                ["Hacker News", "Remote OK", "We Work Remotely"],
            )
            self.assertIn(
                "description",
                tools_by_name["get_job"].output_schema["properties"],
            )

        anyio.run(run)

    def test_search_jobs_tool_uses_shared_job_service(self):
        async def run():
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "search_jobs",
                    {"query": "Python", "remote": True},
                )

            self.assertEqual(result.structured_content["count"], 1)
            self.assertEqual(
                result.structured_content["jobs"][0]["id"],
                str(self.post.id),
            )

        anyio.run(run)

    def test_mcp_is_mounted_as_stateless_http(self):
        with TestClient(application) as client:
            response = client.post(
                "/mcp/",
                headers=MCP_HEADERS,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "tjalerts-test", "version": "0.1"},
                    },
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["result"]["serverInfo"]["name"], "Tech Job Alerts")
        self.assertNotIn("Mcp-Session-Id", response.headers)
