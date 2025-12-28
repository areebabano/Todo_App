# Smart Personal Chief of Staff

A command-line task management application built with Python, Click, and Rich.

## Features

- Create, list, update, and delete tasks
- Mark tasks as complete or incomplete
- Rich formatted table output with color-coded status
- Clean layered architecture (models, storage, services, CLI)

## Requirements

- Python 3.13+
- UV package manager

## Installation

### 1. Install UV (if not already installed)

**Windows (PowerShell):**
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd Todo_App

# Sync dependencies
uv sync
```

## Usage

### Add a Task

```bash
# Add a task with just a title
uv run chief add "Buy groceries"

# Add a task with a description
uv run chief add "Write report" -d "Quarterly sales report for Q4"
```

### List Tasks

```bash
uv run chief list
```

Output:
```
┌──────────┬────────────┬──────────────────────┬────────────────────────────────┐
│  Status  │ ID         │ Title                │ Description                    │
├──────────┼────────────┼──────────────────────┼────────────────────────────────┤
│   [ ]    │ a1b2c3d4   │ Buy groceries        │                                │
│   [✓]    │ e5f6g7h8   │ Write report         │ Quarterly sales report for Q4  │
└──────────┴────────────┴──────────────────────┴────────────────────────────────┘
```

### Complete a Task

```bash
uv run chief complete <task-id>
```

### Mark Task as Incomplete

```bash
uv run chief incomplete <task-id>
```

### Update a Task

```bash
# Update title
uv run chief update <task-id> -t "New title"

# Update description
uv run chief update <task-id> -d "New description"

# Update both
uv run chief update <task-id> -t "New title" -d "New description"
```

### Delete a Task

```bash
uv run chief delete <task-id>
```

### Help

```bash
# Show all commands
uv run chief --help

# Show help for a specific command
uv run chief add --help
```

## WSL2 Setup (Windows)

If you're running this on Windows using WSL2:

1. **Install WSL2:**
   ```powershell
   wsl --install
   ```

2. **Install Python 3.13+ in WSL:**
   ```bash
   sudo apt update
   sudo apt install python3.13 python3.13-venv
   ```

3. **Install UV in WSL:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

4. **Navigate to project directory:**
   ```bash
   cd /mnt/c/path/to/Todo_App
   ```

5. **Run the application:**
   ```bash
   uv sync
   uv run chief --help
   ```

## Project Structure

```
Todo_App/
├── src/
│   └── chief_of_staff/
│       ├── __init__.py
│       ├── main.py              # Entry point
│       ├── models/
│       │   ├── __init__.py
│       │   └── task.py          # Task dataclass
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── exceptions.py    # Storage exceptions
│       │   └── memory_store.py  # In-memory storage
│       ├── services/
│       │   ├── __init__.py
│       │   ├── exceptions.py    # Service exceptions
│       │   └── task_service.py  # Business logic
│       └── cli/
│           ├── __init__.py
│           ├── display.py       # Rich display functions
│           └── commands.py      # Click CLI commands
├── tests/
├── pyproject.toml
├── uv.lock
└── README.md
```

## Architecture

The application follows a clean layered architecture:

1. **Models Layer** (`models/`): Domain entities and validation
2. **Storage Layer** (`storage/`): Data persistence (in-memory for Phase I)
3. **Service Layer** (`services/`): Business logic and exception translation
4. **CLI Layer** (`cli/`): User interface with Click and Rich

Each layer only depends on layers below it, enabling easy testing and future extensions.

## Development

### Running Tests

```bash
uv run pytest
```

### Code Style

The project follows PEP 8 guidelines with type hints throughout.

## License

MIT License
