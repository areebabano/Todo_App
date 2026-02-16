---
id: PHR-002-004
title: implement-mcp-server-agent
stage: green
date: 2026-02-13
surface: claude-code
model: claude-opus-4-6
feature: 002-todo-ai-chatbot
branch: 002-todo-ai-chatbot
user: developer
command: /sp.implement
labels: [green, phase-iii, mcp, fastmcp, openai-agents, todo-agent, implementation]
links:
  spec: specs/002-todo-ai-chatbot/spec.md
  ticket: ""
  adr: ""
  pr: ""
files:
  - apps/backend/mcp/__init__.py
  - apps/backend/mcp/server.py
  - apps/backend/mcp/tools.py
  - apps/backend/agents/__init__.py
  - apps/backend/agents/todo_agent.py
  - apps/backend/main.py
tests:
  - Module import validation (all imports succeed)
  - MCP tool registration verified (create_task registered)
  - Agent configuration verified (name, model, mcp_servers)
  - FastAPI route /mcp mounted and accessible
---

## Prompt

Implement tasks T008 through T014

Follow the Phase III approved specification and plan.

Rules:
- Production-grade code
- Proper folder structure
- Follow FastAPI best practices
- Use SQLModel
- No shortcuts
- Include type hints
- Include docstrings

Return:
- Full file code
- Explanation of what was implemented
- How to test it

## Response snapshot

Implemented 7 tasks (T008-T014) covering the MCP Server layer and AI Agent layer for US1 MVP:

### MCP Server (T008-T011)
- **T008**: Created `apps/backend/mcp/__init__.py` — MCP package with docstring
- **T009**: Created `apps/backend/mcp/server.py` — FastMCP("Todo Tools") instance with auto-import of tools module
- **T010**: Created `apps/backend/mcp/tools.py` — `create_task` MCP tool using `@mcp.tool()` decorator, creates own DB session, calls `TaskService.create_task()`, returns JSON string
- **T011**: Updated `apps/backend/main.py` — mounted MCP server at `/mcp` via `mcp.http_app()` (Starlette ASGI sub-app)

### AI Agent (T012-T014)
- **T012**: Created `apps/backend/agents/__init__.py` — agents package with docstring
- **T013**: Created `apps/backend/agents/todo_agent.py` — Agent config with system prompt (persona, capabilities, behaviour rules), model from OPENAI_MODEL env var, MCPServerStreamableHttp transport with params dict
- **T014**: Implemented `process_chat_message()` async generator in same file — truncates history to context window, injects owner_user_id as system note, runs Agent via `Runner.run_streamed()`, yields text_delta/tool_call/tool_output/done/error events

### Key Implementation Details
- FastMCP `http_app()` returns StarletteWithLifespan ASGI app
- MCPServerStreamableHttp takes `params={"url": "..."}` not `url="..."` directly
- MCP tools return JSON strings (not dicts) per FastMCP convention
- Agent system prompt instructs AI to always pass owner_user_id to tool calls
- Context window truncation configured via CHATBOT_CONTEXT_WINDOW env var (default 20)

### Validation
- All module imports succeed with dotenv loaded
- MCP tool `create_task` registered on server
- Agent creates with correct name, model, and 1 MCP server
- FastAPI app includes `/mcp` in routes

## Outcome

- Impact: MCP server and AI Agent layers fully implemented for US1 MVP pipeline
- Tests: Module import validation, tool registration, agent config, route mounting
- Files: 5 new files, 1 modified (main.py)
- Next prompts: /sp.implement T015-T018 (ChatKit Backend Server)
- Reflection: The MCPServerStreamableHttp API changed — takes params dict, not url kwarg. Discovered via runtime validation. Always validate library APIs against installed version before implementation.

## Evaluation notes (flywheel)

- Failure modes observed: MCPServerStreamableHttp constructor API mismatch (url kwarg vs params dict)
- Graders run and results (PASS/FAIL): Import validation PASS, tool registration PASS, agent config PASS, route mounting PASS
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
