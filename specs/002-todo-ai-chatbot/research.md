# Research: Todo AI Chatbot (Phase III)

**Branch**: `002-todo-ai-chatbot` | **Date**: 2026-02-13

## R1: OpenAI ChatKit Architecture (Frontend + Backend)

### Decision: Use ChatKit Python SDK (self-hosted) for backend, `@openai/chatkit-react` for frontend

### Rationale

ChatKit supports two deployment modes: OpenAI-hosted (Agent Builder) and self-hosted (ChatKit Python SDK). The self-hosted approach is required because:

- We need a custom AI pipeline (OpenAI Agents SDK + MCP tools), not a pre-built OpenAI workflow
- We need to integrate with our existing Better Auth session-based authentication
- Conversation and task data must persist in our own Neon PostgreSQL database
- We need full control over the data flow and tool execution

### Architecture

**Frontend (`@openai/chatkit-react`)**:
- React component `<ChatKit />` renders the full chat UI (thread, composer, message list)
- `useChatKit` hook manages configuration and events
- Connects to our FastAPI backend via ChatKit's HTTP protocol
- Handles streaming responses, tool call visualization, widget rendering
- Requires loading `chatkit.js` script from OpenAI CDN

**Backend (ChatKit Python SDK `openai-chatkit`)**:
- `ChatKitServer` base class subclassed for custom logic
- `respond` method executes when user sends a message — this is where we invoke the Agents SDK
- Built-in thread and message management protocol
- Streaming response via `ThreadStreamEvent` types
- Custom `DataStore` implementation for database persistence (threads, messages, attachments)
- Mounts as routes within our existing FastAPI application

### Alternatives Considered

| Alternative | Rejected Because |
|---|---|
| Build custom chat UI from scratch | Massive frontend effort; ChatKit provides production-ready streaming, message rendering, tool visualization |
| Use ChatKit with OpenAI-hosted backend | Cannot integrate our own Agents SDK + MCP pipeline; no control over data storage |
| Use a different chat UI library (e.g., Vercel AI SDK) | User specified ChatKit; ChatKit Python SDK provides seamless server-side integration |

---

## R2: OpenAI Agents SDK Integration

### Decision: Use OpenAI Agents SDK `Agent` + `Runner.run_streamed()` inside ChatKit's `respond` method

### Rationale

The Agents SDK provides the agentic loop (LLM reasoning → tool calls → response) with first-class MCP support. It is lightweight, minimal in abstraction, and handles:

- System prompt configuration for the todo assistant persona
- MCP server tool discovery and invocation
- Multi-turn conversation via message history passed to `Runner.run()`
- Streaming responses via `Runner.run_streamed()` for real-time output
- Model selection via environment variable

### Key Concepts

- **Agent**: Declarative configuration — name, instructions (system prompt), model, mcp_servers, tools
- **Runner**: Execution engine — `Runner.run_streamed(agent, messages)` returns streaming events
- **Conversation History**: Application-managed list of messages, passed to each `Runner.run()` call. The SDK does not persist history — our ChatKit DataStore handles that.
- **MCP Integration**: Agent accepts `mcp_servers` parameter, auto-discovers tools at connection time

### Model Configuration

- Model is set per-Agent as a string (e.g., `"gpt-4o"`, `"gpt-4o-mini"`)
- Configurable via `OPENAI_MODEL` environment variable
- Supports any OpenAI-compatible API via `ModelProvider` abstraction

### Alternatives Considered

| Alternative | Rejected Because |
|---|---|
| Direct OpenAI API calls (no Agents SDK) | Would require manual tool-calling loop, MCP integration, retry logic |
| LangChain / LangGraph | User specified OpenAI Agents SDK; heavier abstraction than needed |
| Anthropic Claude SDK | User specified OpenAI ecosystem |

---

## R3: MCP Server Transport

### Decision: Use FastMCP with Streamable HTTP transport, mounted within the FastAPI application

### Rationale

Five MCP transport options exist in the Agents SDK:

| Transport | Description | Suitability |
|---|---|---|
| `HostedMCPTool` | OpenAI-hosted; requires public URL | Not suitable — tools need DB access |
| `MCPServerStreamableHttp` | HTTP connection to local/remote server | **Best fit** — in-process, no subprocess overhead |
| `MCPServerSse` | HTTP + SSE | Deprecated by MCP project |
| `MCPServerStdio` | Subprocess via stdin/stdout | Works but spawns separate process per request |
| `MCPServerManager` | Multi-server coordinator | Overkill for single server |

`MCPServerStreamableHttp` is the best fit because:

- The MCP server (FastMCP) mounts as an endpoint within the same FastAPI app (e.g., `/mcp/`)
- No subprocess management overhead (unlike Stdio)
- The MCP server shares the same Python process, simplifying database session management
- Not deprecated (unlike SSE)
- The Agent connects via `MCPServerStreamableHttp(url="http://localhost:{port}/mcp")`

### FastMCP Tool Definition Pattern

Tools defined with `@mcp.tool` decorator. Each tool:
- Receives parameters as typed function arguments
- Has a docstring that becomes the tool description
- Is stateless — receives `owner_user_id` as a parameter for user-scoped operations
- Invokes existing `TaskService` methods for database operations

### Tools Required (6 total)

1. `create_task` — Create a new todo
2. `list_tasks` — List todos with optional status filter
3. `update_task` — Update task title/description
4. `delete_task` — Delete a task by ID
5. `complete_task` — Mark a task as complete
6. `incomplete_task` — Mark a task as incomplete

### Alternatives Considered

| Alternative | Rejected Because |
|---|---|
| MCPServerStdio | Spawns subprocess; separate DB sessions; process management overhead |
| Direct function tools (no MCP) | User specifically requires MCP architecture |
| Separate MCP microservice | Unnecessary complexity; shared DB access simpler in-process |

---

## R4: Conversation Persistence Strategy

### Decision: Implement ChatKit `DataStore` interface backed by SQLModel + Neon PostgreSQL

### Rationale

The ChatKit Python SDK requires a `DataStore` implementation for persisting threads, messages, and attachments. Our implementation uses SQLModel models stored in the existing Neon PostgreSQL database, consistent with the Phase II data layer.

### Data Store Responsibilities

- **Thread CRUD**: Create, read, update, delete conversation threads
- **Message CRUD**: Create, read messages within threads; append new messages
- **Attachment handling**: Store and retrieve file attachments (if needed)
- **User scoping**: All operations filtered by `owner_user_id`

### Context Window Management

- Conversation history sent to the AI model is limited to the most recent 20 messages (configurable)
- Full conversation history is always persisted in the database and displayed in the UI
- The context window is a runtime concern handled when constructing the `Runner.run()` input

### Alternatives Considered

| Alternative | Rejected Because |
|---|---|
| In-memory conversation storage | Not persistent across server restarts; doesn't meet FR-009, FR-010 |
| Redis for conversation state | Adds infrastructure dependency; PostgreSQL sufficient for this scale |
| File-based storage | Not suitable for multi-user web application |

---

## R5: Authentication Integration

### Decision: Reuse existing Better Auth session-based authentication via cookie forwarding

### Rationale

Phase II already has a working authentication system:
- Better Auth manages user sessions via httpOnly cookies
- Backend verifies session tokens by querying the Better Auth session table
- All API endpoints extract `user_id` from the verified session

For Phase III:
- ChatKit frontend sends requests with cookies (same-origin, credentials included)
- ChatKit Python SDK server endpoints use the same session verification middleware
- `owner_user_id` is extracted from the session and passed to MCP tools
- MCP tools are stateless — they receive `owner_user_id` as a parameter, not from server state

### Security Model

- ChatKit's default auth uses a "client token" from OpenAI — we replace this with our Better Auth session
- The ChatKit Python SDK's `ChatKitServer` subclass integrates with our existing `verify_session_token` dependency
- All MCP tool invocations include the `owner_user_id` to enforce data isolation
- The MCP tools themselves do NOT authenticate — the calling layer (ChatKit Server) is responsible for auth

---

## References

- [OpenAI Agents SDK — MCP Integration](https://openai.github.io/openai-agents-python/mcp/)
- [FastMCP — OpenAI Integration](https://gofastmcp.com/integrations/openai)
- [ChatKit Python SDK](https://openai.github.io/chatkit-python/)
- [ChatKit JS Documentation](https://openai.github.io/chatkit-js/)
- [ChatKit Advanced Samples](https://github.com/openai/openai-chatkit-advanced-samples)
- [ChatKit React Package](https://www.npmjs.com/package/@openai/chatkit-react)
