# Implementation Plan: Todo AI Chatbot (Phase III)

**Branch**: `002-todo-ai-chatbot` | **Date**: 2026-02-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/002-todo-ai-chatbot/spec.md`

## Summary

Phase III adds an AI-powered chatbot interface to the existing Phase II Full Stack Todo App. Authenticated users will manage their todos through natural language conversation via an OpenAI ChatKit frontend connected to a FastAPI backend. The backend uses the OpenAI Agents SDK to orchestrate AI reasoning and invoke stateless MCP tools (via FastMCP) for todo CRUD operations. Conversation history persists in the existing Neon PostgreSQL database. The chat endpoint is stateless — all context (conversation history, user identity) is provided per request.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript (frontend)
**Primary Dependencies**: FastAPI, OpenAI Agents SDK (`openai-agents`), ChatKit Python SDK (`openai-chatkit`), FastMCP (`fastmcp`), MCP SDK (`mcp`), `@openai/chatkit-react` (frontend)
**Storage**: Neon Serverless PostgreSQL (existing), SQLModel ORM, Alembic migrations
**Testing**: pytest (backend), manual E2E testing (frontend)
**Target Platform**: Web application (existing Phase II infrastructure)
**Project Type**: Web (frontend + backend monorepo)
**Performance Goals**: Chat response under 5 seconds, conversation history load under 2 seconds, 50 concurrent users
**Constraints**: Stateless MCP tools, stateless chat endpoint, user data isolation, existing auth reuse
**Scale/Scope**: Single active conversation per user, 20-message context window, 6 MCP tools

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Layered Architecture | PASS | New layers (MCP, Agent, ChatKit) follow strict separation |
| II. Domain-Driven Design | PASS | Existing Task model unchanged; new Conversation/Message models follow same patterns |
| IV. Explicit Dependency Injection | PASS | Agent, MCP server, ChatKit server receive dependencies explicitly |
| V. Type Safety and Documentation | PASS | Python type hints, TypeScript, Pydantic models throughout |
| VI. Error Handling Strategy | PASS | AI service unavailability handled gracefully (FR-017) |
| VIII. Simplicity and YAGNI | PASS | Minimal new entities (2); reuses existing TaskService |
| IX. Service-Oriented Architecture | PASS | Frontend ↔ Backend separation maintained; ChatKit protocol over HTTP |
| X. Authentication-First Design | PASS | Reuses Better Auth session authentication (FR-018) |
| XI. Data Ownership and Isolation | PASS | Conversations and Messages have owner_user_id; MCP tools receive user ID per call |
| XII. API Contract Stability | PASS | New endpoints additive; existing Phase II API unchanged |
| XIII. Frontend-Backend Separation | PASS | ChatKit React (frontend) ↔ ChatKit Python SDK (backend) |
| XIV. Database Integrity and Migrations | PASS | New tables via Alembic migration; cascade deletes on Conversation→Messages |
| XV. Security-First Development | PASS | Auth required on all chat endpoints; no cross-user data access |
| XVI. Web Accessibility | PASS | ChatKit provides accessible components by default |

**Gate result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-todo-ai-chatbot/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research output
├── data-model.md        # Entity design
├── quickstart.md        # Setup guide
├── contracts/
│   └── api-contracts.md # API and MCP tool contracts
└── tasks.md             # Implementation tasks (created by /sp.tasks)
```

### Source Code (additions to existing repository)

```text
apps/
├── backend/
│   ├── main.py                          # MODIFY: Mount ChatKit server routes + MCP endpoint
│   ├── api/v1/
│   │   └── endpoints/
│   │       └── chat.py                  # NEW: ChatKit server endpoint integration
│   ├── services/
│   │   ├── task_service.py              # EXISTING: No changes
│   │   └── chat_service.py             # NEW: ChatKit server subclass + DataStore
│   ├── mcp/
│   │   ├── __init__.py                  # NEW: MCP package
│   │   ├── server.py                    # NEW: FastMCP server instance + mounting
│   │   └── tools.py                     # NEW: 6 MCP tool definitions
│   └── agents/
│       ├── __init__.py                  # NEW: Agents package
│       └── todo_agent.py               # NEW: Agent config (system prompt, model, MCP)
├── frontend/
│   ├── app/
│   │   └── chat/
│   │       └── page.tsx                 # NEW: Chatbot page (protected route)
│   ├── components/
│   │   └── chat/
│   │       └── ChatInterface.tsx        # NEW: ChatKit React wrapper
│   ├── app/api/
│   │   └── chat/
│   │       └── [...path]/
│   │           └── route.ts             # NEW: API proxy for ChatKit protocol
│   └── middleware.ts                    # MODIFY: Add /chat to protected routes
db/
└── models/
    ├── conversation_model.py            # NEW: Conversation SQLModel
    └── message_model.py                 # NEW: Message SQLModel
```

**Structure Decision**: Extends the existing Phase II monorepo structure. New files are placed within the established `apps/backend/` and `apps/frontend/` directories, following the existing patterns (services, endpoints, components). MCP and Agents get their own packages under `apps/backend/` for clear separation.

---

## Implementation Phases

### Phase 1: Database Layer — Conversation and Message Models

**Goal**: Establish persistent storage for conversation state.

#### Milestone 1.1: SQLModel Entities

**Steps**:
1. Create `db/models/conversation_model.py` with the Conversation SQLModel:
   - Fields: id (UUID PK), owner_user_id (String, indexed), title (Optional String), is_active (Boolean, default True), created_at, updated_at
   - Indexes: owner_user_id, (owner_user_id + is_active composite)

2. Create `db/models/message_model.py` with the Message SQLModel:
   - Fields: id (UUID PK), conversation_id (UUID FK → Conversation.id), role (String enum: user/assistant), content (Text), tool_calls (JSON, optional), created_at
   - Indexes: conversation_id, (conversation_id + created_at composite)

3. Update `db/models/__init__.py` to export new models

#### Milestone 1.2: Alembic Migration

**Steps**:
1. Generate Alembic migration for Conversation and Message tables
2. Include indexes and foreign key constraints (cascade delete from Conversation to Messages)
3. Run migration against Neon PostgreSQL development database
4. Verify tables created with correct schema

---

### Phase 2: MCP Server — Stateless Todo Tools

**Goal**: Expose todo operations as stateless MCP tools via FastMCP.

#### Milestone 2.1: FastMCP Server Setup

**Steps**:
1. Install `fastmcp` and `mcp` Python packages (add to pyproject.toml)
2. Create `apps/backend/mcp/__init__.py`
3. Create `apps/backend/mcp/server.py`:
   - Instantiate FastMCP server with name "Todo Tools"
   - Configure HTTP transport for mounting within FastAPI
4. Mount the MCP server as a sub-application at `/mcp` in FastAPI's main.py

#### Milestone 2.2: MCP Tool Definitions

**Steps**:
1. Create `apps/backend/mcp/tools.py` with 6 tool functions decorated with `@mcp.tool`:

   - `create_task(owner_user_id: str, title: str, description: str | None) → dict`
     - Invokes `TaskService.create_task()` with a DB session
     - Returns created task as JSON

   - `list_tasks(owner_user_id: str, status_filter: str = "all", limit: int = 10, offset: int = 0) → dict`
     - Invokes `TaskService.get_tasks_by_owner()` with filters
     - Returns task list with count metadata

   - `update_task(owner_user_id: str, task_id: str, title: str | None, description: str | None) → dict`
     - Invokes `TaskService.update_task()` after ownership verification
     - Returns updated task as JSON

   - `delete_task(owner_user_id: str, task_id: str) → dict`
     - Invokes `TaskService.delete_task()` after ownership verification
     - Returns confirmation message

   - `complete_task(owner_user_id: str, task_id: str) → dict`
     - Invokes `TaskService.complete_task()` after ownership verification
     - Returns confirmation with timestamp

   - `incomplete_task(owner_user_id: str, task_id: str) → dict`
     - Invokes `TaskService.incomplete_task()` after ownership verification
     - Returns confirmation message

2. Each tool function:
   - Creates its own database session (stateless)
   - Validates ownership via owner_user_id parameter
   - Returns JSON-serializable results
   - Handles errors with descriptive messages

#### Milestone 2.3: MCP Server Verification

**Steps**:
1. Start the FastAPI server with MCP endpoint mounted
2. Verify the MCP endpoint responds at `/mcp`
3. Test tool listing via MCP protocol
4. Test each tool individually with direct MCP client calls

---

### Phase 3: AI Agent Layer — OpenAI Agents SDK

**Goal**: Configure the AI agent that interprets natural language and invokes MCP tools.

#### Milestone 3.1: Agent Configuration

**Steps**:
1. Install `openai-agents` Python package (add to pyproject.toml)
2. Create `apps/backend/agents/__init__.py`
3. Create `apps/backend/agents/todo_agent.py`:
   - Define system prompt for the todo assistant:
     - Persona: friendly, concise task management assistant
     - Capabilities: create, list, update, delete, complete, incomplete todos
     - Behavior rules: confirm before deleting, ask for clarification on ambiguity, politely redirect off-topic messages, paginate large task lists
     - Response format: conversational, include task titles in confirmations
   - Configure Agent with:
     - `name`: "Todo Assistant"
     - `instructions`: the system prompt
     - `model`: read from `OPENAI_MODEL` environment variable (default: "gpt-4o")
     - `mcp_servers`: list containing the MCP server connection
   - Create a factory function that returns a configured Agent connected to the MCP server

#### Milestone 3.2: Agent Runner Integration

**Steps**:
1. In `todo_agent.py`, create an async function `process_chat_message`:
   - Input: user message (string), conversation history (list of messages), owner_user_id (string)
   - Constructs the message history for the Agent (converting DB messages to SDK format)
   - Injects `owner_user_id` into tool context (so MCP tools know which user's data to access)
   - Calls `Runner.run_streamed(agent, messages)` for streaming response
   - Yields streaming events (text deltas, tool calls)
   - Returns the complete assistant response and any tool call metadata
2. Handle context window: truncate conversation history to most recent N messages (configurable via `CHATBOT_CONTEXT_WINDOW` env var, default 20)
3. Handle errors: catch OpenAI API errors and yield graceful error messages

---

### Phase 4: ChatKit Backend — Self-Hosted Server

**Goal**: Integrate ChatKit Python SDK to serve the chat protocol from FastAPI.

#### Milestone 4.1: ChatKit Server Setup

**Steps**:
1. Install `openai-chatkit` Python package (add to pyproject.toml)
2. Create `apps/backend/services/chat_service.py`:
   - Subclass `ChatKitServer` from the ChatKit Python SDK
   - Implement the `respond` method:
     - Extract user identity from request context (Better Auth session)
     - Load or create active conversation for the user
     - Save user message to database
     - Build conversation history from database (last N messages)
     - Call `process_chat_message()` from the todo agent module
     - Stream response events back to the client
     - Save assistant response to database (including tool_calls metadata)
   - Implement custom `DataStore`:
     - `create_thread()` → Create Conversation in DB
     - `get_thread()` → Load Conversation with messages from DB
     - `list_threads()` → List user's Conversations from DB
     - `delete_thread()` → Delete Conversation (cascade deletes messages)
     - `add_item()` → Save Message to DB
     - `get_items()` → Load Messages for a Conversation from DB

#### Milestone 4.2: FastAPI Integration

**Steps**:
1. Create `apps/backend/api/v1/endpoints/chat.py`:
   - Create FastAPI router for chat endpoints
   - Mount ChatKit server routes under `/api/v1/chat`
   - Add Better Auth session dependency for authentication
   - Add rate limiting (consistent with existing endpoints)
2. Update `apps/backend/main.py`:
   - Import and include chat router
   - Initialize MCP server on startup
   - Initialize ChatKit server on startup
3. Update CORS configuration to allow ChatKit-specific headers if needed

#### Milestone 4.3: Conversation Management

**Steps**:
1. Implement active conversation logic:
   - When user opens chat: load active conversation (is_active = True)
   - If no active conversation: create one
   - "New conversation" action: archive current (is_active = False), create new
2. Implement conversation title auto-generation:
   - After first assistant response, generate a short title summarizing the conversation
   - Update conversation title in database
3. Implement conversation history loading:
   - Load all messages for active conversation, ordered by created_at
   - Return in ChatKit thread item format

---

### Phase 5: Frontend — ChatKit React Integration

**Goal**: Add the chatbot UI page to the existing Next.js frontend.

#### Milestone 5.1: Dependencies and Setup

**Steps**:
1. Install `@openai/chatkit-react` npm package
2. Add ChatKit JS script tag to the application layout or chat page head
3. Configure ChatKit to point to our self-hosted backend (`/api/chat`)

#### Milestone 5.2: Chat Page

**Steps**:
1. Create `apps/frontend/app/chat/page.tsx`:
   - Protected route (requires authentication)
   - Renders the ChatKit component
   - Passes configuration: backend URL, authentication headers
   - Displays conversation thread with streaming support
2. Create `apps/frontend/components/chat/ChatInterface.tsx`:
   - Wrapper component around ChatKit's `<ChatKit />` component
   - Configures the `useChatKit` hook for our backend
   - Handles loading state while conversation history loads
   - Handles error states (AI unavailable, network errors)

#### Milestone 5.3: API Proxy Route

**Steps**:
1. Create `apps/frontend/app/api/chat/[...path]/route.ts`:
   - Proxy route that forwards ChatKit protocol requests to FastAPI backend
   - Extracts Better Auth session token from cookies
   - Converts to Authorization header for backend
   - Handles streaming response passthrough
   - Follows the same pattern as existing `/api/tasks` proxy routes

#### Milestone 5.4: Navigation and Route Protection

**Steps**:
1. Update `apps/frontend/middleware.ts`:
   - Add `/chat` to the list of protected routes
2. Update `apps/frontend/components/layout/Navbar.tsx`:
   - Add "Chat" navigation link to the navbar
   - Highlight active when on `/chat` route
3. Optionally add a chat entry point on the tasks dashboard page

---

### Phase 6: Integration Testing and Polish

**Goal**: Verify end-to-end functionality and handle edge cases.

#### Milestone 6.1: End-to-End Verification

**Steps**:
1. Test complete flow: Login → Navigate to /chat → Send message → Receive response
2. Test each todo operation via chat:
   - "Add a task called test" → verify task created in DB
   - "Show my tasks" → verify task list returned
   - "Mark test as done" → verify task completed in DB
   - "Rename test to updated test" → verify task title changed
   - "Delete updated test" → verify deletion confirmation → confirm → verify deleted
3. Test multi-turn context:
   - "Show my tasks" → "Complete the first one" → verify correct task completed
4. Test conversation persistence:
   - Send messages → close browser → reopen → verify history loaded
5. Verify data isolation:
   - Log in as User A, create tasks via chat
   - Log in as User B, "Show my tasks" → verify User A's tasks not visible

#### Milestone 6.2: Edge Case Handling

**Steps**:
1. Test empty/whitespace messages → verify helpful response
2. Test off-topic messages ("What's the weather?") → verify redirect response
3. Test ambiguous task references ("Complete the task") when multiple match → verify disambiguation
4. Test completing already-completed task → verify informative response
5. Test large task lists (20+ tasks, "Show all") → verify pagination/summary
6. Simulate AI service unavailability → verify graceful error response within 5 seconds

#### Milestone 6.3: Performance Verification

**Steps**:
1. Measure chat response time (target: under 5 seconds end-to-end)
2. Measure conversation history load time (target: under 2 seconds)
3. Test with 10+ concurrent chat users (target: no degradation)
4. Verify no memory leaks in MCP server connections
5. Verify database connection pool handles concurrent chat sessions

---

## Complexity Tracking

No constitution violations found. No complexity justifications needed.

---

## Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| ChatKit Python SDK API changes | Medium | Pin dependency version; test upgrade path |
| OpenAI API rate limits under concurrent usage | Medium | Implement per-user rate limiting; use model with higher limits |
| MCP server connection lifecycle management | Low | Use async context managers; clean up on shutdown |
| Conversation context window too small for complex interactions | Low | Make configurable via env var; tune based on testing |
| ChatKit domain allowlisting requirement | Medium | Configure in OpenAI organization settings; document setup step |
| Streaming response interruption (network issues) | Low | ChatKit handles reconnection; frontend shows error state |

---

## Dependencies (Execution Order)

```
Phase 1 (Database) ──────────────────────────────────────────┐
                                                              │
Phase 2 (MCP Server) ── depends on Phase 1 (TaskService) ───┤
                                                              │
Phase 3 (AI Agent) ── depends on Phase 2 (MCP tools) ────────┤
                                                              │
Phase 4 (ChatKit Backend) ── depends on Phase 1, 3 ──────────┤
                                                              │
Phase 5 (Frontend) ── depends on Phase 4 ─────────────────────┤
                                                              │
Phase 6 (Integration) ── depends on Phase 5 ──────────────────┘
```

**Critical Path**: Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6

**Parallelization Opportunities**:
- Phase 1 (Database) and Phase 2.1 (MCP setup) can start in parallel (MCP tools depend on DB models but setup doesn't)
- Phase 5.1-5.2 (Frontend ChatKit setup) can start once Phase 4.2 is done (doesn't need Milestone 4.3)
