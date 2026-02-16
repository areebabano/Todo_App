# Data Model: Todo AI Chatbot (Phase III)

**Branch**: `002-todo-ai-chatbot` | **Date**: 2026-02-13

## Entities

### Task (EXISTING — No Changes)

The existing `tasks` table from Phase II is reused without modification. MCP tools interact with tasks through the existing `TaskService`.

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, auto-generated | Unique identifier |
| title | String | Required, 1-100 chars, indexed | Task title |
| description | String | Optional, max 500 chars | Task description |
| is_completed | Boolean | Default: False, indexed | Completion status |
| owner_user_id | String | Required, indexed | Owner user reference |
| created_at | DateTime | Auto-set, indexed | Creation timestamp |
| updated_at | DateTime | Auto-set | Last update timestamp |
| completed_at | DateTime | Optional | When task was completed |

**Indexes**: owner_user_id, is_completed, (owner_user_id + is_completed composite), created_at

---

### Conversation (NEW)

Represents a chat session between a user and the AI assistant.

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, auto-generated | Unique identifier |
| owner_user_id | String | Required, indexed | Owner user reference (FK to Better Auth users) |
| title | String | Optional, max 200 chars | Auto-generated conversation title |
| is_active | Boolean | Default: True, indexed | Whether this is the current active conversation |
| created_at | DateTime | Auto-set | When conversation was started |
| updated_at | DateTime | Auto-set | Last activity timestamp |

**Indexes**: owner_user_id, (owner_user_id + is_active composite)

**Relationships**:
- One Conversation → Many Messages (cascade delete)
- One User → Many Conversations (but only one active at a time)

**State Transitions**:
- `active` → `archived`: When user starts a new conversation, the previous one is archived (is_active = False)
- A user can have at most one conversation with `is_active = True`

---

### Message (NEW)

An individual message within a conversation.

| Field | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, auto-generated | Unique identifier |
| conversation_id | UUID | Required, FK → Conversation.id, indexed | Parent conversation |
| role | String | Required, enum: "user" / "assistant" | Message sender role |
| content | Text | Required | Message text content |
| tool_calls | JSON | Optional | Metadata about MCP tools invoked (tool name, parameters, result summary) |
| created_at | DateTime | Auto-set, indexed | When message was sent |

**Indexes**: conversation_id, (conversation_id + created_at composite for ordered retrieval)

**Relationships**:
- Many Messages → One Conversation
- Messages are ordered by `created_at` within a conversation

**Validation Rules**:
- `content` must not be empty or whitespace-only
- `role` must be one of "user" or "assistant"
- `conversation_id` must reference an existing conversation owned by the same user

---

## Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   User       │       │  Conversation    │       │   Message    │
│ (Better Auth)│ 1───* │                  │ 1───* │              │
│              │       │ id               │       │ id           │
│ id           │       │ owner_user_id    │       │ conversation │
│ email        │       │ title            │       │ role         │
│ name         │       │ is_active        │       │ content      │
│              │       │ created_at       │       │ tool_calls   │
│              │       │ updated_at       │       │ created_at   │
└──────────────┘       └──────────────────┘       └──────────────┘
                              │
                              │ (user also owns)
                              │
                       ┌──────────────┐
                       │    Task      │
                       │ (EXISTING)   │
                       │              │
                       │ id           │
                       │ title        │
                       │ description  │
                       │ is_completed │
                       │ owner_user_id│
                       │ created_at   │
                       │ updated_at   │
                       │ completed_at │
                       └──────────────┘
```

## Data Isolation Rules

1. All Conversation queries MUST filter by `owner_user_id = :current_user_id`
2. All Message queries MUST join through a Conversation owned by the current user
3. All MCP tool invocations MUST receive `owner_user_id` and pass it to TaskService
4. No cross-user conversation or task access permitted

## ChatKit DataStore Mapping

The ChatKit Python SDK requires a `DataStore` implementation. The mapping to our entities:

| ChatKit Concept | Our Entity | Notes |
|---|---|---|
| Thread | Conversation | ChatKit "threads" map to our conversations |
| Thread Item | Message | ChatKit "items" map to our messages |
| Attachment | N/A | Not needed for Phase III (text-only chat) |

The DataStore implementation bridges ChatKit's storage interface to our SQLModel-backed Conversation and Message tables.
