"""
Main FastAPI application for the Todo Web Application backend.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from fastapi import FastAPI
from apps.backend.api.v1.endpoints import auth, tasks, chat
from apps.backend.core.errors import register_error_handlers
from apps.backend.core.cors import configure_cors
from apps.backend.core.middleware import add_security_middleware
from apps.backend.core.rate_limiter import init_rate_limiter
from apps.backend.mcp.server import mcp
from db.session import warmup_db

# Build MCP sub-app so we can wire its lifespan into FastAPI
_mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run the MCP server's lifespan within FastAPI's lifespan.
    Also warms up the database connection pool on startup."""
    warmup_db()
    async with _mcp_app.lifespan(_mcp_app):
        yield


app = FastAPI(
    title="Todo Web Application API",
    description="REST API for the Todo Web Application",
    version="1.0.0",
    lifespan=lifespan,
)

init_rate_limiter(app)
configure_cors(app)
add_security_middleware(app)
register_error_handlers(app)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

# Mount MCP server (Streamable HTTP transport) for AI agent tool access
app.mount("/mcp", _mcp_app)


@app.get("/")
def read_root():
    return {"message": "Todo Web Application API", "status": "running", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "todo-backend-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "apps.backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=True,
    )
