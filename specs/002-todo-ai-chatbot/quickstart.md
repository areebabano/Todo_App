# Quickstart: Todo AI Chatbot (Phase III)

**Branch**: `002-todo-ai-chatbot` | **Date**: 2026-02-13

## Prerequisites

- Phase II application fully operational (Next.js frontend, FastAPI backend, Neon PostgreSQL)
- Python 3.11+ with UV package manager
- Node.js 18+ with npm
- OpenAI API key with access to GPT-4o or equivalent
- Neon PostgreSQL database (same as Phase II)

## New Dependencies

### Backend (Python)

| Package | Purpose |
|---|---|
| `openai-agents` | OpenAI Agents SDK for AI orchestration |
| `openai-chatkit` | ChatKit Python SDK for self-hosted chat server |
| `mcp` | Official MCP SDK |
| `fastmcp` | FastMCP for defining MCP tools |

### Frontend (npm)

| Package | Purpose |
|---|---|
| `@openai/chatkit-react` | ChatKit React component and hook |

## New Environment Variables

| Variable | Description | Example |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key for LLM access | `sk-...` |
| `OPENAI_MODEL` | Model to use for the chatbot agent | `gpt-4o` |
| `MCP_SERVER_PORT` | Port for the MCP server (if separate) | `8001` |
| `CHATBOT_CONTEXT_WINDOW` | Number of recent messages to include in AI context | `20` |

## New Project Structure (additions only)

```
apps/
├── backend/
│   ├── api/v1/
│   │   └── endpoints/
│   │       └── chat.py            # ChatKit server endpoint mounting
│   ├── services/
│   │   └── chat_service.py        # ChatKit server implementation
│   ├── mcp/
│   │   ├── server.py              # FastMCP server with todo tools
│   │   └── tools.py               # MCP tool definitions
│   └── agents/
│       └── todo_agent.py          # OpenAI Agents SDK agent config
├── frontend/
│   ├── app/
│   │   └── chat/
│   │       └── page.tsx           # Chatbot page
│   ├── components/
│   │   └── chat/
│   │       └── ChatInterface.tsx  # ChatKit wrapper component
│   └── app/api/
│       └── chat/
│           └── [...path]/
│               └── route.ts       # Proxy route for ChatKit protocol
db/
└── models/
    ├── conversation_model.py      # Conversation SQLModel
    └── message_model.py           # Message SQLModel
```

## Development Workflow

1. Install new backend dependencies
2. Install new frontend dependencies
3. Run database migration for new tables (Conversation, Message)
4. Start backend (FastAPI + MCP server + ChatKit server)
5. Start frontend (Next.js with ChatKit component)
6. Navigate to `/chat` to use the chatbot

## Verification Steps

1. **Auth**: Log in via existing login page, navigate to `/chat`
2. **Chat**: Type "Show me my tasks" — should list existing tasks
3. **Create**: Type "Add a task called test chatbot" — should create and confirm
4. **Complete**: Type "Mark test chatbot as done" — should complete the task
5. **Verify**: Navigate to `/tasks` dashboard — task should appear with correct status
