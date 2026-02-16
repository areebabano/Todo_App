---
id: PHR-002-002
title: todo-ai-chatbot-plan
stage: plan
date: 2026-02-13
surface: claude-code
model: claude-opus-4-6
feature: 002-todo-ai-chatbot
branch: 002-todo-ai-chatbot
user: developer
command: /sp.plan
labels: [plan, phase-iii, ai-chatbot, mcp, openai-agents, chatkit, architecture]
links:
  spec: specs/002-todo-ai-chatbot/spec.md
  ticket: ""
  adr: ""
  pr: ""
files:
  - specs/002-todo-ai-chatbot/plan.md
  - specs/002-todo-ai-chatbot/research.md
  - specs/002-todo-ai-chatbot/data-model.md
  - specs/002-todo-ai-chatbot/quickstart.md
  - specs/002-todo-ai-chatbot/contracts/api-contracts.md
tests:
  - N/A (planning phase, no tests)
---

## Prompt

Based on the approved Phase III specification above:

Generate a detailed implementation plan.

Rules:
- Break into Phases
- Break each phase into milestones
- Each milestone into actionable engineering steps
- No coding yet
- No pseudocode
- Clear logical order

Include:
- Project structure design
- Database setup steps
- MCP server setup steps
- Agent setup steps
- FastAPI integration steps
- Chat endpoint workflow
- Frontend integration with ChatKit
- Authentication integration with Better Auth
- Deployment considerations

Output Format:
Phase -> Milestone -> Step-by-step tasks

This must be production-ready and suitable for execution by Claude Code.

## Response snapshot

Generated a comprehensive implementation plan for Phase III: Todo AI Chatbot at `specs/002-todo-ai-chatbot/plan.md`, along with supporting artifacts:

**Research (research.md)** — 5 research decisions:
- R1: ChatKit Python SDK (self-hosted) for backend, `@openai/chatkit-react` for frontend
- R2: OpenAI Agents SDK `Agent` + `Runner.run_streamed()` for AI orchestration
- R3: FastMCP with Streamable HTTP transport, mounted within FastAPI
- R4: ChatKit `DataStore` interface backed by SQLModel + Neon PostgreSQL
- R5: Reuse existing Better Auth session-based authentication

**Data Model (data-model.md)** — 2 new entities:
- Conversation: UUID PK, owner_user_id, title, is_active, timestamps
- Message: UUID PK, conversation_id FK, role, content, tool_calls JSON, created_at
- Task entity: unchanged from Phase II

**API Contracts (contracts/api-contracts.md)** — 2 API surfaces:
- ChatKit Protocol Endpoints: thread CRUD + streaming message response (5 endpoints)
- MCP Tool Definitions: 6 stateless tools (create, list, update, delete, complete, incomplete)

**Implementation Plan (plan.md)** — 6 phases, 17 milestones:
- Phase 1: Database Layer (2 milestones — models + migration)
- Phase 2: MCP Server (3 milestones — setup + tools + verification)
- Phase 3: AI Agent Layer (2 milestones — config + runner)
- Phase 4: ChatKit Backend (3 milestones — server + FastAPI + conversation mgmt)
- Phase 5: Frontend (4 milestones — setup + page + proxy + navigation)
- Phase 6: Integration Testing (3 milestones — E2E + edge cases + performance)

**Constitution Check**: All 14 principles PASS. No violations.

**Quickstart (quickstart.md)**: New dependencies, env vars, project structure additions, dev workflow.

## Outcome

- ✅ Impact: Complete implementation plan with all supporting artifacts ready for task generation
- 🧪 Tests: N/A (planning phase)
- 📁 Files: plan.md, research.md, data-model.md, quickstart.md, contracts/api-contracts.md
- 🔁 Next prompts: /sp.tasks (generate implementation tasks from plan)
- 🧠 Reflection: Research phase confirmed all technology choices are viable. ChatKit Python SDK self-hosted mode is the key architectural decision — it provides the server-side protocol bridge while allowing custom AI pipeline via Agents SDK + MCP. Constitution check passed cleanly with no violations.

## Evaluation notes (flywheel)

- Failure modes observed: WebFetch 403 on platform.openai.com docs (worked around via other sources)
- Graders run and results (PASS/FAIL): Constitution check PASS (14/14 principles)
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
