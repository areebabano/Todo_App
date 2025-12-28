<!--
  SYNC IMPACT REPORT
  ==================
  Version Change: 0.0.0 → 1.0.0 (MAJOR - initial ratification)

  Modified Principles: N/A (initial creation)

  Added Sections:
  - Project Identity
  - Vision Statement
  - Core Principles (I through VIII)
  - Technology Stack
  - Development Workflow
  - Quality Gates & Deliverables
  - Non-Functional Requirements
  - Future Evolution Path
  - Governance
  - Appendices

  Removed Sections: N/A

  Templates Requiring Updates:
  - .specify/templates/plan-template.md: ✅ Compatible (Constitution Check references principles)
  - .specify/templates/spec-template.md: ✅ Compatible (requirement format aligns)
  - .specify/templates/tasks-template.md: ✅ Compatible (phase structure matches workflow)

  Follow-up TODOs: None
-->

# Smart Personal Chief of Staff Constitution

## Project Identity

| Attribute | Value |
|-----------|-------|
| **Name** | Smart Personal Chief of Staff |
| **Phase** | I - Foundation (Todo In-Memory Python Console App) |
| **Version** | 0.1.0 |
| **Type** | Command-Line Interface (CLI) Application |
| **Language** | Python 3.13+ |
| **Package Manager** | UV |

## Vision Statement

The Smart Personal Chief of Staff is a progressive task management system designed to evolve from a simple CLI application to a fully-featured cloud-native platform. Phase I establishes the architectural foundation through a clean, layered Python console application that demonstrates core task management capabilities while maintaining strict separation of concerns to enable future evolution.

**Mission**: Provide users with an intuitive, reliable, and extensible task management tool that grows with their needs—from personal todo lists to enterprise-grade distributed task orchestration.

**Phase I Goal**: Deliver a functional, well-architected CLI todo application using in-memory storage that validates the core domain model and establishes patterns for future phases.

## Core Principles

### I. Layered Architecture (NON-NEGOTIABLE)

The application MUST maintain strict separation between architectural layers:

```
models/ → storage/ → services/ → cli/ → main.py
```

**Rules**:
- Each layer MUST only depend on layers below it
- Models MUST NOT import from storage, services, or CLI
- Storage MUST NOT import from services or CLI
- Services MUST NOT import from CLI
- Dependency injection MUST be used for cross-layer communication
- No circular imports are permitted under any circumstances

**Rationale**: Clean layered architecture enables independent testing, future replacement of layers (e.g., SQLite storage), and maintains code clarity as the system grows.

### II. Domain-Driven Design

The Task domain model is the heart of the application and MUST be:

- **Pure**: No infrastructure concerns (database, CLI, file I/O) in domain models
- **Validated**: All invariants enforced at construction time via `__post_init__`
- **Serializable**: Round-trip conversion to/from dictionaries without data loss
- **Self-Documenting**: Type hints and docstrings on all public members

**Task Entity Specification**:
| Field | Type | Required | Default | Validation |
|-------|------|----------|---------|------------|
| id | UUID | Yes | uuid4() | Auto-generated |
| title | str | Yes | - | Non-empty, stripped |
| description | Optional[str] | No | None | Stripped if provided |
| status | TaskStatus | Yes | PENDING | Enum value |
| created_at | datetime | Yes | datetime.now() | Auto-generated |
| updated_at | datetime | Yes | datetime.now() | Updated on changes |

### III. CLI-First Interface

Every feature MUST be accessible via command-line interface:

- **Commands**: `add`, `list`, `update`, `delete`, `complete`, `incomplete`
- **Input**: Arguments and options via Click framework
- **Output**: Formatted display via Rich library
- **Errors**: User-friendly messages (no stack traces for expected errors)

**Rules**:
- All output goes through the display layer (never print directly in commands)
- All business logic lives in the service layer (commands are thin wrappers)
- Help text MUST be clear and complete for every command
- Exit codes MUST be meaningful (0 for success, non-zero for errors)

### IV. Explicit Dependency Injection

Services and components MUST receive their dependencies explicitly:

```python
# CORRECT
task_service = TaskService(storage=MemoryStore())

# INCORRECT
class TaskService:
    def __init__(self):
        self._storage = MemoryStore()  # Hidden dependency
```

**Rules**:
- No global state or singletons
- Factory functions for complex initialization
- Dependencies passed through constructors
- Test doubles easily injectable

**Rationale**: Explicit dependencies enable testing, make the architecture visible, and prevent hidden coupling.

### V. Type Safety and Documentation

All code MUST maintain full type coverage:

- **Type Hints**: Every function parameter and return type annotated
- **Docstrings**: Google-style on all public functions and classes
- **Validation**: Runtime validation at boundaries (CLI input, deserialization)

**Standard Format**:
```python
def create_task(
    self, title: str, description: Optional[str] = None
) -> Task:
    """Create a new task with validation.

    Args:
        title: Task title (required, non-empty).
        description: Optional task description.

    Returns:
        The created Task instance.

    Raises:
        ValidationError: If title is empty.
    """
```

### VI. Error Handling Strategy

Errors MUST be handled at appropriate layers:

| Layer | Error Type | Handling |
|-------|------------|----------|
| Models | ValueError | Raise on invalid data |
| Storage | TaskNotFoundException | Raise when task not found |
| Services | ValidationError, TaskNotFoundError | Wrap storage errors, add context |
| CLI | Click exceptions | Display user-friendly messages |

**Rules**:
- Fail fast at validation boundaries
- Never silently swallow exceptions
- Log errors appropriately for debugging
- User-facing errors MUST be actionable

### VII. Cross-Platform Compatibility

All code MUST work on Linux, macOS, and Windows/WSL2:

- Use `pathlib.Path` for all file operations
- Use UTF-8 encoding for all text files
- Avoid shell-specific commands
- Test Unicode handling (Rich handles this)
- No platform-specific dependencies

### VIII. Simplicity and YAGNI

Start simple, add complexity only when needed:

- No premature optimization
- No features beyond Phase I specification
- No abstractions without concrete use cases
- Prefer standard library over external dependencies
- Only two runtime dependencies allowed: `rich` and `click`

**Rationale**: Phase I is a foundation—complexity can be added in later phases when requirements are clearer.

## Technology Stack

### Required (Phase I)

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.13+ | Core runtime |
| Package Manager | UV | Latest | Dependency management |
| CLI Framework | Click | Latest | Command parsing |
| Terminal UI | Rich | Latest | Formatted output |
| Storage | In-Memory Dict | N/A | Phase I persistence |

### Prohibited (Phase I)

- Database libraries (SQLite, PostgreSQL, etc.)
- Web frameworks (FastAPI, Flask, etc.)
- Async libraries (asyncio, aiohttp, etc.)
- External API clients
- Additional runtime dependencies beyond click/rich

## Development Workflow

### Phase 1: Specification Creation

1. User describes feature requirements
2. Run `/sp.specify` to generate feature specification
3. Run `/sp.clarify` to identify gaps and ambiguities
4. Iterate until spec is complete and unambiguous

**Output**: `specs/<feature>/spec.md`

### Phase 2: Plan Generation

1. Run `/sp.plan` to generate implementation plan
2. Verify constitution compliance (Architecture, Dependencies)
3. Review technical context and project structure
4. Run `/sp.tasks` to generate implementation tasks

**Output**: `specs/<feature>/plan.md`, `specs/<feature>/tasks.md`

### Phase 3: Implementation

1. Execute tasks in dependency order
2. Use appropriate agents (ModelAgent, StorageAgent, ServiceAgent, CLICommandAgent)
3. Validate each layer before proceeding to next
4. Commit after each logical unit of work

**Agents**:
- ProjectFoundationAgent: Project setup
- ModelAgent: Domain models
- StorageAgent: Persistence layer
- ServiceAgent: Business logic
- DisplayAgent: Output formatting
- CLICommandAgent: Command definitions
- MainEntryAgent: Application wiring
- DocumentationAgent: README and guides

### Phase 4: Validation

1. Run all CLI commands to verify functionality
2. Test error cases and edge conditions
3. Verify cross-platform compatibility
4. Generate documentation
5. Run `/sp.analyze` for consistency check

**Output**: Working application, README.md, validation report

## Quality Gates & Deliverables

### Specification Approval Checklist

- [ ] All functional requirements have acceptance criteria
- [ ] User stories are prioritized and independently testable
- [ ] Edge cases are documented
- [ ] Success criteria are measurable
- [ ] No NEEDS_CLARIFICATION markers remain

### Implementation Completion Criteria

- [ ] All CLI commands functional (add, list, update, delete, complete, incomplete)
- [ ] Task CRUD operations working through service layer
- [ ] Display formatting renders correctly on all platforms
- [ ] Error messages are user-friendly (no stack traces)
- [ ] Help text complete for all commands
- [ ] Round-trip serialization verified
- [ ] Application starts and runs without errors

### Repository Structure Requirements

```
project_root/
├── models/
│   ├── __init__.py
│   └── task.py
├── storage/
│   ├── __init__.py
│   ├── exceptions.py
│   └── memory_store.py
├── services/
│   ├── __init__.py
│   ├── exceptions.py
│   └── task_service.py
├── cli/
│   ├── __init__.py
│   ├── commands.py
│   └── display.py
├── tests/
│   └── __init__.py
├── specs/
│   └── <feature>/
├── history/
│   └── prompts/
├── .specify/
│   ├── memory/
│   │   └── constitution.md
│   └── templates/
├── main.py
├── pyproject.toml
├── README.md
└── .gitignore
```

### Documentation Requirements

- [ ] README.md with project description and features
- [ ] Installation instructions (UV-based)
- [ ] Usage examples for all commands
- [ ] Troubleshooting section
- [ ] WSL2-specific notes if applicable

## Non-Functional Requirements

### Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Application startup | < 1 second | Time to first prompt |
| Add task operation | < 100ms | Command completion |
| List all tasks | < 100ms | Display rendered |
| Any single operation | < 100ms | User-perceived latency |

### Usability

- Commands follow intuitive naming (add, list, complete, delete)
- Error messages explain what went wrong and how to fix it
- Help text (`--help`) is comprehensive and accurate
- Output formatting is clean and readable
- Consistent behavior across all platforms

### Maintainability

- Code follows PEP8 style guidelines
- All public interfaces have docstrings
- Type hints on all functions and methods
- Separation of concerns strictly enforced
- No code duplication across layers
- Single responsibility per module

### Reliability

- Application never crashes on valid input
- Invalid input produces clear error messages
- Data integrity maintained (no partial updates)
- Graceful handling of edge cases

## Future Evolution Path

### Phase II: Persistent Storage

- Replace MemoryStore with SQLite implementation
- Add data migration framework
- Implement backup/restore functionality
- Storage abstraction proves layered architecture value

### Phase III: Web API

- Add FastAPI REST endpoints
- Implement authentication/authorization
- Deploy as containerized service
- CLI becomes API client option

### Phase IV: Distributed System

- Event-driven architecture (message queues)
- Multi-user support
- Real-time synchronization
- Horizontal scaling capability

### Phase V: Cloud-Native

- Kubernetes deployment
- Service mesh integration
- Observability stack (metrics, tracing, logging)
- Multi-region support

### Phase VI: AI Integration

- Natural language task creation
- Smart task prioritization
- Predictive scheduling
- Voice interface option

## Governance

### Constitution Authority

This constitution is the authoritative source for all architectural and process decisions in the Smart Personal Chief of Staff project. All implementation work MUST comply with these principles.

### Amendment Process

1. **Proposal**: Document proposed change with rationale
2. **Impact Analysis**: Identify affected components and templates
3. **Review**: Evaluate against project goals and future phases
4. **Approval**: Explicit acceptance required before implementation
5. **Migration**: Update all affected artifacts
6. **Version**: Increment constitution version per semantic rules

### Version Policy

- **MAJOR**: Backward-incompatible changes to principles or architecture
- **MINOR**: New principles or expanded guidance
- **PATCH**: Clarifications, typos, non-semantic refinements

### Compliance Verification

- All PRs MUST reference relevant constitution principles
- Architecture violations MUST be justified in writing
- Exceptions require explicit documentation and approval
- Regular audits against constitution compliance recommended

## Appendices

### Appendix A: Command Reference

```bash
# Add a new task
python main.py add "Buy groceries"
python main.py add "Call mom" -d "Wish her happy birthday"

# List all tasks
python main.py list

# Update a task
python main.py update <task-id> -t "New title"
python main.py update <task-id> -d "New description"
python main.py update <task-id> -t "New title" -d "New description"

# Delete a task
python main.py delete <task-id>

# Mark task complete
python main.py complete <task-id>

# Mark task incomplete
python main.py incomplete <task-id>

# Show help
python main.py --help
python main.py add --help
```

### Appendix B: Task Fields

```python
@dataclass
class Task:
    title: str                              # Required, non-empty
    description: Optional[str] = None       # Optional
    id: UUID = field(default_factory=uuid4) # Auto-generated
    status: TaskStatus = TaskStatus.PENDING # Default: pending
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
```

### Appendix C: Error Messages

| Scenario | Message Format |
|----------|----------------|
| Empty title | "Title cannot be empty" |
| Task not found | "Task not found: {task_id}" |
| Invalid command | Click's built-in error handling |
| Missing argument | Click's built-in error handling |

---

**Version**: 1.0.0 | **Ratified**: 2025-12-28 | **Last Amended**: 2025-12-28
