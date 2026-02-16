"""MCP (Model Context Protocol) server package.

Exposes stateless todo management tools via FastMCP for consumption
by the OpenAI Agents SDK.  Each tool receives ``owner_user_id`` as a
parameter and creates its own database session, keeping the MCP layer
fully stateless.
"""
