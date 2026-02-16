# Tasks: Todo AI Chatbot (Phase III)

**Input**: Design documents from `/specs/002-todo-ai-chatbot/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api-contracts.md

**Tests**: Not explicitly requested in spec. Manual E2E verification included per user story checkpoint.

**Organization**: Tasks grouped by user story. US1 (P1) builds the full end-to-end pipeline as the MVP. Subsequent stories add MCP tools incrementally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `apps/backend/`
- **Frontend**: `apps/frontend/`
- **Database**: `db/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install all new dependencies and configure environment variables

- [X] T001 [P] Add Python backend dependencies (`openai-agents`, `openai-chatkit`, `fastmcp`, `mcp`) to `pyproject.toml` and install via UV
- [X] T002 [P] Add frontend dependency `@openai/chatkit-react` to `apps/frontend/package.json` and install via npm
- [X] T003 Add new environment variables (`OPENAI_API_KEY`, `OPENAI_MODEL`, `CHATBOT_CONTEXT_WINDOW`) to `.env` and document in `.env.example`

---

## Phase 2: Foundational — Database Layer (Blocking Prerequisites)

**Purpose**: Create Conversation and Message tables required by all user stories

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Create Conversation SQLModel in `db/models/conversation_model.py` with fields: id (UUID PK), owner_user_id (String, indexed), title (Optional String, max 200), is_active (Boolean, default True), created_at (DateTime, auto-set), updated_at (DateTime, auto-set). Add indexes: owner_user_id, composite (owner_user_id + is_active)
- [X] T005 [P] Create Message SQLModel in `db/models/message_model.py` with fields: id (UUID PK), conversation_id (UUID FK → Conversation.id, cascade delete), role (String, enum user/assistant), content (Text, required), tool_calls (JSON, optional), created_at (DateTime, auto-set). Add indexes: conversation_id, composite (conversation_id + created_at)
- [X] T006 Update `db/models/__init__.py` to export Conversation and Message models
- [X] T007 Generate and run Alembic migration for Conversation and Message tables against Neon PostgreSQL. Verify tables created with correct schema, indexes, and foreign key cascade constraints

**Checkpoint**: Database layer ready — Conversation and Message tables exist with proper indexes and relationships

---

## Phase 3: User Story 1 — Natural Language Task Creation (Priority: P1) MVP

**Goal**: Build the complete end-to-end chatbot pipeline. An authenticated user can open the chat interface, type a natural language message to create a task, and receive confirmation. This is the MVP — the full pipeline (MCP server, Agent, ChatKit server, Frontend) is built here.

**Independent Test**: Log in, navigate to `/chat`, type "Add a task called buy groceries", verify task appears in chatbot response AND in the existing `/tasks` dashboard.

### MCP Server (US1)

- [X] T008 [US1] Create MCP package with `apps/backend/mcp/__init__.py`
- [X] T009 [US1] Create FastMCP server instance in `apps/backend/mcp/server.py`: instantiate FastMCP with name "Todo Tools", configure Streamable HTTP transport for mounting within FastAPI
- [X] T010 [US1] Implement `create_task` MCP tool in `apps/backend/mcp/tools.py`: decorated with `@mcp.tool`, accepts `owner_user_id` (str), `title` (str), `description` (str, optional). Creates its own DB session, invokes `TaskService.create_task()`, returns JSON with created task details (id, title, description, is_completed, created_at). Include docstring for tool description
- [X] T011 [US1] Mount MCP server as sub-application at `/mcp` endpoint in `apps/backend/main.py`. Add startup/shutdown lifecycle for MCP server

### AI Agent (US1)

- [X] T012 [US1] Create agents package with `apps/backend/agents/__init__.py`
- [X] T013 [US1] Create Todo Agent configuration in `apps/backend/agents/todo_agent.py`: define system prompt (friendly task assistant persona; capabilities: create, list, update, delete, complete, incomplete; behavior rules: confirm before deleting, ask for clarification on ambiguity, redirect off-topic messages, include task titles in confirmations). Configure Agent with name "Todo Assistant", model from `OPENAI_MODEL` env var (default "gpt-4o"), `mcp_servers` pointing to `MCPServerStreamableHttp` at localhost MCP endpoint
- [X] T014 [US1] Implement `process_chat_message` async function in `apps/backend/agents/todo_agent.py`: accepts user_message (str), conversation_history (list of message dicts), owner_user_id (str). Truncates history to most recent N messages (from `CHATBOT_CONTEXT_WINDOW` env var, default 20). Converts DB messages to SDK format. Injects owner_user_id into messages so tools receive it. Calls `Runner.run_streamed()`. Yields streaming events (text deltas, tool calls). Catches OpenAI API errors and yields graceful error message

### ChatKit Backend Server (US1)

- [X] T015 [US1] Create ChatKit DataStore implementation in `apps/backend/services/chat_service.py`: subclass or implement the ChatKit `DataStore` interface backed by SQLModel. Implement methods: `create_thread()` → create Conversation in DB, `get_thread()` → load Conversation with messages, `list_threads()` → list user's Conversations, `delete_thread()` → delete Conversation (cascade), `add_item()` → save Message to DB, `get_items()` → load Messages ordered by created_at. All operations filter by owner_user_id
- [X] T016 [US1] Create ChatKit server subclass in `apps/backend/services/chat_service.py`: subclass `ChatKitServer`, implement `respond` method that: extracts user identity from request context, loads or creates active conversation for user, saves user message to DB, builds conversation history from DB, calls `process_chat_message()` from todo_agent module, streams response events back to client, saves assistant response to DB including tool_calls metadata
- [X] T017 [US1] Create chat endpoint router in `apps/backend/api/v1/endpoints/chat.py`: create FastAPI router, mount ChatKit server routes under `/api/v1/chat`, add Better Auth session dependency for authentication, add rate limiting consistent with existing endpoints
- [X] T018 [US1] Update `apps/backend/main.py`: import and include chat router, initialize ChatKit server on startup with DataStore instance, update CORS if needed for ChatKit headers

### Frontend (US1)

- [X] T019 [US1] Create ChatKit wrapper component in `apps/frontend/components/chat/ChatInterface.tsx`: wraps ChatKit's `<ChatKit />` React component, configures `useChatKit` hook pointing to `/api/chat` backend, handles loading state while conversation loads, handles error states (AI unavailable, network errors)
- [X] T020 [US1] Create chat page in `apps/frontend/app/chat/page.tsx`: protected route requiring authentication, renders ChatInterface component, adds ChatKit JS script tag (from OpenAI CDN), passes configuration for self-hosted backend URL and authentication
- [X] T021 [US1] Create API proxy route in `apps/frontend/app/api/chat/route.ts`: proxy that forwards ChatKit protocol requests to FastAPI backend at `NEXT_PUBLIC_API_BASE_URL`, extracts Better Auth session token from cookies, converts to Authorization header, handles streaming response passthrough. Follow the same pattern as existing `apps/frontend/lib/api-proxy.ts`
- [X] T022 [US1] Update `apps/frontend/middleware.ts`: add `/chat` to the list of protected routes (alongside `/tasks`, `/profile`)
- [X] T023 [US1] Update `apps/frontend/components/layout/Sidebar.tsx`: add "Chat" navigation link to the sidebar, highlight active when on `/chat` route

**Checkpoint**: Full end-to-end pipeline working. User can log in, navigate to `/chat`, type "Add a task called buy groceries", see confirmation, and verify task in `/tasks` dashboard. This is the MVP.

---

## Phase 4: User Story 2 — Conversational Task Listing and Filtering (Priority: P1)

**Goal**: Users can ask the chatbot to list their tasks with optional status filtering (all, active, completed).

**Independent Test**: Create tasks via dashboard, then in chat type "Show my tasks", "Show completed tasks", "What do I still need to do?" and verify correct results.

### Implementation for User Story 2

- [X] T024 [US2] Add `list_tasks` MCP tool in `apps/backend/mcp/tools.py`: accepts `owner_user_id` (str), `status_filter` (str, default "all", options: "all"/"active"/"completed"), `limit` (int, default 10), `offset` (int, default 0). Creates DB session, queries tasks with filter, returns JSON array of task objects with total count metadata. Include descriptive docstring
- [ ] T025 [US2] Verify end-to-end: log in, navigate to `/chat`, type "Show me my tasks" and verify task list displayed. Test "Show completed tasks" and "What do I still need to do?" filters. Test empty task list message

**Checkpoint**: US1 (create) and US2 (list/filter) both work independently via chat

---

## Phase 5: User Story 3 — Mark Task Complete via Chat (Priority: P2)

**Goal**: Users can mark tasks as complete or incomplete through natural language commands.

**Independent Test**: Create a task, then type "Mark buy groceries as done" in chat, verify task status changes in DB and dashboard.

### Implementation for User Story 3

- [X] T026 [P] [US3] Add `complete_task` MCP tool in `apps/backend/mcp/tools.py`: accepts `owner_user_id` (str), `task_id` (str). Creates DB session, invokes `TaskService.complete_task()` with ownership verification. Returns confirmation with task title and completion timestamp. Handles errors: task not found, not owned, already completed
- [X] T027 [P] [US3] Add `incomplete_task` MCP tool in `apps/backend/mcp/tools.py`: accepts `owner_user_id` (str), `task_id` (str). Creates DB session, invokes `TaskService.incomplete_task()` with ownership verification. Returns confirmation with task title. Handles errors: task not found, not owned, already incomplete
- [ ] T028 [US3] Verify end-to-end: create task via chat, type "Mark it as done", verify completion. Test with ambiguous task reference (multiple matches) — agent should ask which one. Test completing already-completed task

**Checkpoint**: US1, US2, US3 all work. Users can create, list, and complete tasks via chat

---

## Phase 6: User Story 4 — Update Task via Chat (Priority: P2)

**Goal**: Users can update task titles and descriptions through natural language.

**Independent Test**: Create a task, type "Rename buy groceries to buy organic groceries" in chat, verify title updated in DB.

### Implementation for User Story 4

- [X] T029 [US4] Add `update_task` MCP tool in `apps/backend/mcp/tools.py`: accepts `owner_user_id` (str), `task_id` (str), `title` (str, optional), `description` (str, optional). Creates DB session, invokes `TaskService.update_task()` with ownership verification. Returns JSON with updated task details. Handles errors: task not found, not owned, validation failures
- [ ] T030 [US4] Verify end-to-end: create task, type "Rename buy groceries to buy organic groceries", verify title change. Test "Add a description to buy groceries: get milk and eggs", verify description update

**Checkpoint**: US1-US4 all work. Full create/list/complete/update via chat

---

## Phase 7: User Story 5 — Delete Task via Chat (Priority: P2)

**Goal**: Users can delete tasks with confirmation through natural language.

**Independent Test**: Create a task, type "Delete buy groceries", confirm when prompted, verify task removed from DB.

### Implementation for User Story 5

- [X] T031 [US5] Add `delete_task` MCP tool in `apps/backend/mcp/tools.py`: accepts `owner_user_id` (str), `task_id` (str). Creates DB session, invokes `TaskService.delete_task()` with ownership verification. Returns confirmation message with deleted task title. Handles errors: task not found, not owned
- [ ] T032 [US5] Verify end-to-end: create task, type "Delete buy groceries", verify agent asks for confirmation. Confirm deletion, verify task removed. Test declining deletion — task should remain

**Checkpoint**: All CRUD operations (US1-US5) work via chat. Full feature parity with Phase II dashboard

---

## Phase 8: User Story 6 — Multi-Turn Conversation Context (Priority: P3)

**Goal**: The chatbot resolves contextual references across messages (e.g., "the first one", "it", "that task").

**Independent Test**: Type "Show my tasks", then "Complete the first one" — verify the correct task is completed based on the previous listing.

### Implementation for User Story 6

- [X] T033 [US6] Verify and tune context window behavior in `apps/backend/agents/todo_agent.py`: ensure conversation history is correctly passed to `Runner.run_streamed()` so the agent has context from previous messages. Verify the context window truncation (default 20 messages) works correctly. Adjust system prompt if needed to instruct the agent on resolving contextual references
- [ ] T034 [US6] Verify end-to-end: type "Show my tasks" then "Complete the first one" — verify correct task completed. Type "Create a task for groceries" then "Add a description to it" — verify description added to the just-created task. Start new conversation, type "Complete it" — verify agent asks for clarification

**Checkpoint**: Multi-turn conversations resolve contextual references correctly

---

## Phase 9: User Story 7 — Conversation History Persistence (Priority: P3)

**Goal**: Conversation history persists across browser sessions. Users see previous messages when returning to the chatbot.

**Independent Test**: Have a conversation, close browser, reopen, navigate to `/chat` — verify previous messages are displayed.

### Implementation for User Story 7

- [X] T035 [US7] Implement active conversation management in `apps/backend/services/chat_service.py`: when user opens chat, load active conversation (is_active=True) with all messages ordered by created_at. If no active conversation exists, create one. Implement "new conversation" logic: archive current conversation (is_active=False), create new active one
- [X] T036 [US7] Implement conversation title auto-generation in `apps/backend/services/chat_service.py`: after first assistant response in a new conversation, generate a short title summarizing the topic (e.g., use a lightweight agent call or extract from the first user message). Update conversation title in database
- [ ] T037 [US7] Verify end-to-end: have a conversation, close browser tab, reopen and navigate to `/chat` — verify previous messages displayed. Verify conversation title appears. Start a new conversation — verify old one is archived

**Checkpoint**: Conversation persistence works. All 7 user stories functional

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Edge case handling, error resilience, security hardening, performance verification

- [ ] T038 [P] Verify data isolation: log in as User A, create tasks and have a conversation. Log in as User B, type "Show my tasks" — verify User A's tasks are NOT visible. Verify User B cannot see User A's conversation history
- [ ] T039 [P] Test edge cases in chat: send empty/whitespace message (expect helpful prompt), send off-topic message like "What's the weather?" (expect polite redirect), test ambiguous task references with multiple matches (expect disambiguation), test completing already-completed task (expect informative response)
- [ ] T040 Test AI service unavailability handling: configure invalid `OPENAI_API_KEY` or unreachable endpoint, send a chat message, verify graceful error response within 5 seconds. Restore valid config
- [ ] T041 Test large task list handling: create 20+ tasks, type "Show all my tasks" — verify the agent paginates or summarizes rather than dumping all tasks at once
- [ ] T042 Measure performance: verify chat response time under 5 seconds end-to-end, verify conversation history load time under 2 seconds, verify no memory leaks in MCP server connections after multiple conversations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational DB)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 - MVP)**: Depends on Phase 2 — builds full pipeline
- **Phase 4 (US2)**: Depends on Phase 3 (pipeline must exist to add tools)
- **Phase 5-7 (US3-US5)**: Depend on Phase 3 — can run in parallel with each other
- **Phase 8 (US6)**: Depends on Phase 3 — context is provided by existing pipeline
- **Phase 9 (US7)**: Depends on Phase 3 — persistence is provided by DataStore
- **Phase 10 (Polish)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: Builds the full pipeline — all other stories depend on it
- **US2 (P1)**: Depends on US1 pipeline. Adds list_tasks tool
- **US3 (P2)**: Depends on US1 pipeline. Adds complete/incomplete tools. Can run in parallel with US4, US5
- **US4 (P2)**: Depends on US1 pipeline. Adds update_task tool. Can run in parallel with US3, US5
- **US5 (P2)**: Depends on US1 pipeline. Adds delete_task tool. Can run in parallel with US3, US4
- **US6 (P3)**: Depends on US1 pipeline. No new tools — tunes context handling
- **US7 (P3)**: Depends on US1 pipeline. Enhances DataStore and conversation management

### Within Each User Story

- MCP tool definition before end-to-end verification
- Backend before frontend (for US1 only — subsequent stories don't add frontend)

### Parallel Opportunities

```
Phase 1: T001 || T002 (backend deps || frontend deps)
Phase 2: T004 || T005 (Conversation model || Message model)
Phase 3 (US1): T008-T011 (MCP) → T012-T014 (Agent) → T015-T018 (ChatKit) → T019-T023 (Frontend)
Phase 5 (US3): T026 || T027 (complete_task || incomplete_task tools)
After Phase 3: US3 || US4 || US5 can run in parallel
After Phase 3: US6 || US7 can run in parallel
Phase 10: T038 || T039 (isolation || edge cases)
```

---

## Parallel Example: After US1 MVP Complete

```bash
# These three user stories can launch in parallel since they only add MCP tools:
Agent A: "Add complete_task MCP tool in apps/backend/mcp/tools.py" (US3)
Agent B: "Add update_task MCP tool in apps/backend/mcp/tools.py" (US4)
Agent C: "Add delete_task MCP tool in apps/backend/mcp/tools.py" (US5)

# Note: All three modify the same file (tools.py) so in practice,
# execute sequentially to avoid merge conflicts, or split into separate files
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Database (T004-T007)
3. Complete Phase 3: US1 — Full Pipeline (T008-T023)
4. **STOP and VALIDATE**: Create a task via chat, verify it works end-to-end
5. This is a demoable MVP — user can create tasks via natural language

### Incremental Delivery

1. Setup + DB → Foundation ready
2. US1 (Create) → **MVP Demo** — full pipeline working
3. US2 (List) → Users can see tasks via chat
4. US3+US4+US5 (Complete/Update/Delete) → Full CRUD parity with dashboard
5. US6 (Context) → Conversational experience improved
6. US7 (Persistence) → Sessions persist across visits
7. Polish → Production-ready

### Suggested Execution Order (Single Developer)

```
T001-T003 (Setup)
T004-T007 (DB)
T008-T023 (US1 — MVP, largest phase)
T024-T025 (US2 — List)
T026-T028 (US3 — Complete)
T029-T030 (US4 — Update)
T031-T032 (US5 — Delete)
T033-T034 (US6 — Context)
T035-T037 (US7 — Persistence)
T038-T042 (Polish)
```

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US1 is the largest phase because it builds the entire pipeline (MCP + Agent + ChatKit + Frontend)
- US2-US7 are small phases because they add tools or tune behavior incrementally
- All MCP tools are stateless — they receive `owner_user_id` as a parameter
- The system prompt in T013 is critical — it defines the agent's behavior for ALL user stories
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently
