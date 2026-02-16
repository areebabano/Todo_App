"""FastMCP server instance for the Todo AI Chatbot.

Creates a single ``FastMCP`` instance named *Todo Tools* that is shared
across the application.  Tool functions are registered in ``tools.py``
via the ``@mcp.tool()`` decorator.

The server is mounted as a sub-application inside FastAPI at ``/mcp``
using ``mcp.http_app()`` which returns a Starlette-compatible ASGI app
that speaks the MCP Streamable HTTP transport protocol.
"""

from fastmcp import FastMCP

mcp = FastMCP("Todo Tools")

# Import tools module so that @mcp.tool() decorators execute and
# register the tool functions on this server instance.
import apps.backend.mcp.tools  # noqa: F401, E402
