# BUILD_PLAN.md — Patchwork

> Design authority: all decisions recorded here are final for the MVP. The implementer writes code, not architecture. Zero ambiguity.

---

## 0. Overview

**Patchwork** is an observability-first orchestrator for AI coding assistants. It routes coding tasks to the most appropriate backend (Claude, Codex, Gemini), traces every model call with Langfuse, and gates patches via `git apply --check` before they touch code.

### Data flow

```
patchwork plan "<feature>"
  └─ Claude decomposes feature → 3-7 Task objects
  └─ Plan saved to .patchwork/plans/<slug>-<timestamp>.json

patchwork exec <plan.json>
  └─ for each Task:
       ├─ router.route_task(task) → backend name
       ├─ backend.generate_patch(task, repo_context) → Patch
       ├─ reviewer.review(patch, task) → ReviewResult
       ├─ if APPROVE: validate_patch(patch) → apply_patch(patch)
       └─ if REJECT:  task.status = rejected, log reason
  └─ rich summary table printed to stdout
```

### Design decisions (immutable for MVP)

1. No async. All backends are synchronous. Reason: simpler error handling, no event loop complexity.
2. No memory. Each `exec` starts fresh. Stubs provided in §9.
3. No eval gate. Patches are accepted/rejected by Claude reviewer only.
4. No UI. CLI only.
5. Patches are unified diffs. Backends must emit raw diff text — no markdown fences.
6. `git apply --check` is the gatekeeper. If it fails, the patch is rejected regardless of review decision.
7. Langfuse tracing is opt-in: works if `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, silently no-ops otherwise.
8. Routing is purely keyword-based (v0). No LLM routing.
9. Frontend check wins over backend check when a task description contains both sets of keywords (known v0 limitation).

---

## 1. Root-Level Files

### 1.1 `pyproject.toml`

Copy verbatim:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "patchwork"
version = "0.1.0"
description = "Observability-first orchestrator for AI coding assistants"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.30.0",
    "openai>=1.35.0",
    "google-genai>=0.7.0",
    "langfuse>=2.30.0",
    "typer[all]>=0.12.0",
    "rich>=13.7.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
patchwork = "patchwork.cli:app"

[tool.uv]
dev-dependencies = [
    "pytest>=8.2.0",
    "pytest-mock>=3.14.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
```

Notes:
- `typer[all]` pulls in `rich` automatically; we also pin `rich` directly for explicit console use.
- No async pytest needed — all backends are synchronous.
- `google-genai` is the package name for Google's new Gemini SDK (not `google-generativeai`).
- `hatchling` is the build backend; no `setup.py` needed.

---

### 1.2 `.env.example`

Copy verbatim:

```
# === AI Backend Keys ===
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...

# === Langfuse Observability (optional — omit both to disable tracing) ===
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com

# === Patchwork Settings ===
PATCHWORK_DEFAULT_BACKEND=claude
PATCHWORK_PLAN_DIR=.patchwork/plans
PATCHWORK_CLAUDE_MODEL=claude-sonnet-4-6
PATCHWORK_OPENAI_MODEL=gpt-4o
PATCHWORK_GEMINI_MODEL=gemini-1.5-pro
```

---

### 1.3 `.gitignore`

Copy verbatim:

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
*.egg

# Environment
.env
.env.local

# Patchwork runtime state
.patchwork/

# IDE
.vscode/
.idea/
*.swp

# Testing
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
```

---

### 1.4 `README.md`

Copy verbatim:

```markdown
# Patchwork

> Observability-first orchestrator for AI coding assistants — routes tasks across Claude, Codex,
> and Gemini, traces every model call with Langfuse, and gates patches before they touch code.

## Quick start

```bash
# Install with uv
uv pip install -e .

# Copy env template
cp .env.example .env
# Edit .env with your API keys

# Plan a feature
patchwork plan "add a /health endpoint to the FastAPI app"

# Execute the plan
patchwork exec .patchwork/plans/add-a-health-endpoint-20250101-120000.json
```

## How it works

1. **Plan**: Claude decomposes a feature into 3–7 tasks and saves a JSON plan.
2. **Route**: Each task is routed to the best backend based on keywords.
3. **Generate**: The assigned backend produces a unified diff patch.
4. **Review**: Claude inspects the patch and approves or rejects it.
5. **Apply**: Approved patches are validated with `git apply --check` then applied.
6. **Observe**: Every model call is traced in Langfuse (optional).

## Routing rules

| Keywords | Backend |
|---|---|
| ui, component, react, css, tailwind, frontend, jsx, tsx | Gemini |
| api, database, sql, fastapi, auth, backend, server, endpoint | Codex |
| *(everything else)* | Claude |

## Requirements

- Python 3.11+
- `git` on PATH
- API keys for the backends you want to use

## Project structure

```
patchwork/
├── cli.py           # typer CLI: plan, exec
├── config.py        # pydantic-settings config
├── models.py        # Task, Patch, Plan, ReviewResult
├── router.py        # keyword-based backend routing
├── reviewer.py      # Claude patch reviewer
├── patch.py         # git apply --check + apply
├── tracing.py       # Langfuse @traced / no-op
└── backends/
    ├── base.py      # Backend ABC
    ├── claude.py    # Anthropic backend
    ├── codex.py     # OpenAI backend
    └── gemini.py    # Google Gemini backend
```

## Inspiration

Architecture inspired by [ccg-workflow](https://github.com/ccg-workflow/ccg-workflow).

## License

MIT — see [LICENSE](LICENSE).
```

---

### 1.5 `LICENSE`

Copy verbatim:

```
MIT License

Copyright (c) 2025 Patchwork Contributors

Portions inspired by ccg-workflow (https://github.com/ccg-workflow/ccg-workflow).

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. Source Files

Each section follows:
- **Purpose** — one sentence
- **Imports** — exact import list
- **Public interface** — exact signatures
- **Internal logic** — step-by-step prose
- **Pseudocode** — non-obvious logic only
- **Edge cases** — what can go wrong and how to handle it

---

### 2.1 `patchwork/__init__.py`

**Purpose**: Package marker that exposes the version string.

**Content** (exact, nothing else):

```python
__version__ = "0.1.0"
```

No imports. No `__all__`. No init logic.

---

### 2.2 `patchwork/config.py`

**Purpose**: Single source of truth for all runtime configuration, loaded from environment variables and `.env` file via pydantic-settings.

**Imports**:

```python
from functools import lru_cache
from pathlib import Path
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
```

**Public interface**:

```python
class Settings(BaseSettings):
    model_config: SettingsConfigDict

    # Third-party keys (no PATCHWORK_ prefix in env)
    anthropic_api_key: str | None
    openai_api_key: str | None
    google_api_key: str | None
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str

    # Patchwork-specific (PATCHWORK_* prefix in env)
    claude_model: str
    openai_model: str
    gemini_model: str
    plan_dir: Path
    default_backend: str


def get_settings() -> Settings:
    """Return cached Settings singleton."""
    ...
```

**Internal logic**:

`Settings`:

Set `model_config` as a class variable:
```python
model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    populate_by_name=True,
)
```

Declare fields with explicit `validation_alias` using `AliasChoices` so both the env var name and the Python attribute name work:

```python
anthropic_api_key: str | None = Field(
    default=None,
    validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
)
openai_api_key: str | None = Field(
    default=None,
    validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
)
google_api_key: str | None = Field(
    default=None,
    validation_alias=AliasChoices("GOOGLE_API_KEY", "google_api_key"),
)
langfuse_public_key: str | None = Field(
    default=None,
    validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY", "langfuse_public_key"),
)
langfuse_secret_key: str | None = Field(
    default=None,
    validation_alias=AliasChoices("LANGFUSE_SECRET_KEY", "langfuse_secret_key"),
)
langfuse_host: str = Field(
    default="https://cloud.langfuse.com",
    validation_alias=AliasChoices("LANGFUSE_HOST", "langfuse_host"),
)
claude_model: str = Field(
    default="claude-sonnet-4-6",
    validation_alias=AliasChoices("PATCHWORK_CLAUDE_MODEL", "claude_model"),
)
openai_model: str = Field(
    default="gpt-4o",
    validation_alias=AliasChoices("PATCHWORK_OPENAI_MODEL", "openai_model"),
)
gemini_model: str = Field(
    default="gemini-1.5-pro",
    validation_alias=AliasChoices("PATCHWORK_GEMINI_MODEL", "gemini_model"),
)
plan_dir: Path = Field(
    default=Path(".patchwork/plans"),
    validation_alias=AliasChoices("PATCHWORK_PLAN_DIR", "plan_dir"),
)
default_backend: str = Field(
    default="claude",
    validation_alias=AliasChoices("PATCHWORK_DEFAULT_BACKEND", "default_backend"),
)
```

`get_settings()`:
```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Decorated with `@lru_cache` (no parentheses — Python 3.8+ supports this). `Settings()` is instantiated once; subsequent calls return the cached instance.

**Edge cases**:
- If `.env` is missing, pydantic-settings logs a warning and reads from the environment only. This is fine — do not raise an error.
- If a required API key is `None` at the time a backend is constructed, the backend `__init__` must raise `ValueError` with a message like `"ANTHROPIC_API_KEY is not set. Add it to .env"`. Config itself does not validate presence.
- `plan_dir` is a `Path`. Callers must call `settings.plan_dir.mkdir(parents=True, exist_ok=True)` before writing.

---

### 2.3 `patchwork/models.py`

**Purpose**: Defines core data types — Task, Patch, Plan, ReviewResult — as Pydantic v2 models that serialize cleanly to/from JSON.

**Imports**:

```python
from __future__ import annotations
import re
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
```

**Public interface**:

```python
class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"


class Task(BaseModel):
    id: str
    description: str
    backend: str | None = None
    status: TaskStatus = TaskStatus.pending
    rejection_reason: str | None = None


class Patch(BaseModel):
    task_id: str
    content: str
    backend: str


class ReviewDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class ReviewResult(BaseModel):
    task_id: str
    decision: ReviewDecision
    reasoning: str


class Plan(BaseModel):
    slug: str
    feature: str
    tasks: list[Task]
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug, max 60 characters."""
    ...
```

**Internal logic**:

`Task`:
- `id`: set by the planner as `"task-001"`, `"task-002"`, etc. Not auto-generated by the model.
- `backend`: `None` until `route_task()` runs during `exec`. Updated in place.
- `status`: transitions `pending → running → approved | rejected | failed`.
- `rejection_reason`: set when `status` becomes `rejected` or `failed`.

`Patch`:
- `content`: raw unified diff string. Must start with `--- ` on first non-empty line. No markdown.
- `backend`: name of the backend that generated this patch (for trace correlation).

`ReviewResult`:
- `decision`: `"approve"` or `"reject"` — stored as string enum for clean JSON output.

`Plan`:
- `slug`: derived from `feature` via `slugify()`. Caller sets this explicitly.
- `created_at`: always UTC. Use `datetime.now(timezone.utc)`, never `datetime.utcnow()`.
- Serialization: use `plan.model_dump_json(indent=2)` to write, `Plan.model_validate_json(text)` to read.

`slugify(text)`:
1. Lowercase the input.
2. `re.sub(r"[^a-z0-9\s]", " ", text)` — replace non-alphanumeric non-space chars with space.
3. `.strip()` — remove leading/trailing whitespace.
4. `re.sub(r"\s+", "-", text)` — collapse runs of whitespace to single hyphen.
5. Return `text[:60]`.

Full implementation (pseudocode format for clarity):
```
def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = text.strip()
    text = re.sub(r"\s+", "-", text)
    return text[:60]
```

**Edge cases**:
- `slugify("")` returns `""`. CLI must check for empty slug and raise before saving.
- `slugify("!!!")` returns `""` after stripping. Same handling.
- `Patch.content` may be empty if a backend fails. `validate_patch()` catches this immediately.

---

### 2.4 `patchwork/tracing.py`

**Purpose**: Provides the `traced` decorator that wraps functions with Langfuse observability, with a transparent no-op fallback when keys are absent.

**Imports**:

```python
from __future__ import annotations
import os
from functools import wraps
from typing import Callable
```

**Public interface**:

```python
traced: Callable  # module-level; either langfuse observe or _noop_decorator

def _noop_decorator(func: Callable) -> Callable: ...
def _make_tracer() -> Callable: ...
```

**Internal logic**:

`_noop_decorator(func)`:
1. Apply `@wraps(func)` to preserve `__name__`, `__doc__`, `__module__`.
2. Define `wrapper(*args, **kwargs)` that calls and returns `func(*args, **kwargs)`.
3. Return `wrapper`.

`_make_tracer()`:
1. Read `pub = os.getenv("LANGFUSE_PUBLIC_KEY")`.
2. Read `sec = os.getenv("LANGFUSE_SECRET_KEY")`.
3. If both are truthy strings:
   - `try: from langfuse.decorators import observe; return observe`
   - `except ImportError: pass`
4. Return `_noop_decorator`.

Module-level assignment (runs at import time):
```python
traced = _make_tracer()
```

Why at import time: env vars don't change during runtime. Resolving once avoids per-call overhead and makes the decorator transparent — callers use `@traced` without knowing which implementation is active.

**Full implementation**:

```python
from __future__ import annotations
import os
from functools import wraps
from typing import Callable


def _noop_decorator(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def _make_tracer() -> Callable:
    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    if pub and sec:
        try:
            from langfuse.decorators import observe
            return observe
        except ImportError:
            pass
    return _noop_decorator


traced = _make_tracer()
```

This is the complete file. Write it exactly as shown.

**Edge cases**:
- Langfuse installed but keys not set → `_noop_decorator` used. No crash.
- Keys set but langfuse not installed → `ImportError` caught, `_noop_decorator` used. No crash.
- `traced` is always callable as a decorator. Callers never check whether tracing is active.

---

### 2.5 `patchwork/backends/__init__.py`

**Purpose**: Package marker and backend registry mapping backend names to their classes.

**Content** (exact):

```python
from patchwork.backends.claude import ClaudeBackend
from patchwork.backends.codex import CodexBackend
from patchwork.backends.gemini import GeminiBackend

REGISTRY: dict[str, type] = {
    "claude": ClaudeBackend,
    "codex": CodexBackend,
    "gemini": GeminiBackend,
}
```

The CLI imports `REGISTRY` to instantiate backends by name string.

---

### 2.6 `patchwork/backends/base.py`

**Purpose**: Abstract base class that all backends must implement, enforcing a consistent interface and providing shared helpers.

**Imports**:

```python
from abc import ABC, abstractmethod
from patchwork.models import Task, Patch
```

**Public interface**:

```python
class BackendError(Exception):
    """Raised when a backend fails to generate a usable patch."""
    pass


class Backend(ABC):
    name: str  # class variable — set in each subclass as name = "claude" etc.

    @abstractmethod
    def generate_patch(self, task: Task, repo_context: str) -> Patch:
        """Generate a unified diff patch for the given task.

        Args:
            task: The task to implement.
            repo_context: Relevant repository context (file listing, git log).

        Returns:
            Patch with raw unified diff content.

        Raises:
            BackendError: if the API call fails or returns no usable diff.
        """
        ...

    def _build_system_prompt(self) -> str:
        """Return the system prompt for patch generation. Shared by all backends."""
        ...

    def _extract_diff(self, raw_response: str) -> str:
        """Strip markdown fences from raw_response and return clean diff text."""
        ...
```

**Internal logic**:

`_build_system_prompt()` — return this exact string (copy verbatim into the method body):

```
You are a coding assistant that generates unified diff patches.

Rules:
1. Output ONLY a valid unified diff. No explanations, no markdown fences, no commentary.
2. The diff must start with "--- a/" on the first non-empty line.
3. Use standard unified diff format: --- a/<file>, +++ b/<file>, @@ hunks.
4. The patch must be directly applicable with `git apply`.
5. If creating a new file, use /dev/null as the source: --- /dev/null
6. Do not include binary files.
7. If you cannot generate a valid patch for this task, output exactly: CANNOT_GENERATE
```

`_extract_diff(raw_response)`:
1. Strip leading/trailing whitespace from `raw_response`.
2. If the result starts with ` ``` ` (with or without a language specifier on the same line):
   - Split into lines.
   - Skip the first line (the opening fence).
   - Find the last line that is exactly ` ``` ` (stripped) — that is the closing fence index.
   - Join all lines between opening and closing fences.
   - Strip the result.
3. Return the cleaned string.

Pseudocode:
```
def _extract_diff(self, raw_response: str) -> str:
    text = raw_response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start = 1
        end = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end = i
                break
        text = "\n".join(lines[start:end]).strip()
    return text
```

**Edge cases**:
- `BackendError` messages must include the task ID: `BackendError(f"task {task.id}: <reason>")`.
- `raw_response` may contain a double-fence (triple-backtick opening without language tag, then triple-backtick closing). The loop scanning from the end handles this correctly.

---

### 2.7 `patchwork/backends/claude.py`

**Purpose**: Backend using Anthropic's Claude API (claude-sonnet-4-6 default) to generate unified diff patches.

**Imports**:

```python
from anthropic import Anthropic, APIError
from patchwork.backends.base import Backend, BackendError
from patchwork.models import Task, Patch
from patchwork.tracing import traced
```

**Public interface**:

```python
class ClaudeBackend(Backend):
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None: ...

    @traced
    def generate_patch(self, task: Task, repo_context: str) -> Patch: ...
```

**Internal logic**:

`__init__(api_key, model)`:
1. If `not api_key`: raise `ValueError("ANTHROPIC_API_KEY is required for ClaudeBackend")`.
2. `self._client = Anthropic(api_key=api_key)`.
3. `self._model = model`.

`generate_patch(task, repo_context)`:
1. Build user message:
   ```
   Task: {task.description}

   Repository context:
   {repo_context if repo_context else "(no context provided)"}

   Generate a unified diff patch that implements this task.
   ```
2. Call:
   ```python
   response = self._client.messages.create(
       model=self._model,
       max_tokens=4096,
       system=self._build_system_prompt(),
       messages=[{"role": "user", "content": user_message}],
   )
   ```
3. Extract `raw_text = response.content[0].text`.
4. `diff_content = self._extract_diff(raw_text)`.
5. If `diff_content == "CANNOT_GENERATE"` or not `diff_content`: raise `BackendError(f"task {task.id}: Claude could not generate a patch")`.
6. Return `Patch(task_id=task.id, content=diff_content, backend=self.name)`.

Wrap the `messages.create` call:
```python
try:
    response = self._client.messages.create(...)
except APIError as e:
    raise BackendError(f"task {task.id}: Anthropic API error: {e}") from e
```

---

### 2.8 `patchwork/backends/codex.py`

**Purpose**: Backend using OpenAI's GPT-4o API to generate unified diff patches, intended for backend/database/API tasks.

**Imports**:

```python
from openai import OpenAI, APIError
from patchwork.backends.base import Backend, BackendError
from patchwork.models import Task, Patch
from patchwork.tracing import traced
```

**Public interface**:

```python
class CodexBackend(Backend):
    name = "codex"

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None: ...

    @traced
    def generate_patch(self, task: Task, repo_context: str) -> Patch: ...
```

**Internal logic**:

`__init__(api_key, model)`:
1. If `not api_key`: raise `ValueError("OPENAI_API_KEY is required for CodexBackend")`.
2. `self._client = OpenAI(api_key=api_key)`.
3. `self._model = model`.

`generate_patch(task, repo_context)`:
1. Build user message (same format as ClaudeBackend — see §2.7).
2. Call:
   ```python
   response = self._client.chat.completions.create(
       model=self._model,
       max_tokens=4096,
       messages=[
           {"role": "system", "content": self._build_system_prompt()},
           {"role": "user", "content": user_message},
       ],
   )
   ```
3. Extract `raw_text = response.choices[0].message.content`.
4. `diff_content = self._extract_diff(raw_text)`.
5. If empty or `"CANNOT_GENERATE"`: raise `BackendError(f"task {task.id}: Codex could not generate a patch")`.
6. Return `Patch(task_id=task.id, content=diff_content, backend=self.name)`.

Wrap in `try/except openai.APIError as e: raise BackendError(...) from e`.

---

### 2.9 `patchwork/backends/gemini.py`

**Purpose**: Backend using Google's Gemini API to generate unified diff patches, intended for frontend/UI tasks.

**Imports**:

```python
import google.genai as genai
from patchwork.backends.base import Backend, BackendError
from patchwork.models import Task, Patch
from patchwork.tracing import traced
```

**Public interface**:

```python
class GeminiBackend(Backend):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro") -> None: ...

    @traced
    def generate_patch(self, task: Task, repo_context: str) -> Patch: ...
```

**Internal logic**:

`__init__(api_key, model)`:
1. If `not api_key`: raise `ValueError("GOOGLE_API_KEY is required for GeminiBackend")`.
2. `self._client = genai.Client(api_key=api_key)`.
3. `self._model = model`.

`generate_patch(task, repo_context)`:
1. Build user message (same format as ClaudeBackend).
2. Prepend system prompt to user message, since Gemini's `generate_content` does not have a separate system role in all configurations:
   ```python
   full_prompt = f"{self._build_system_prompt()}\n\n{user_message}"
   ```
3. Call:
   ```python
   response = self._client.models.generate_content(
       model=self._model,
       contents=full_prompt,
   )
   ```
4. Extract `raw_text = response.text`.
5. `diff_content = self._extract_diff(raw_text)`.
6. If empty or `"CANNOT_GENERATE"`: raise `BackendError(f"task {task.id}: Gemini could not generate a patch")`.
7. Return `Patch(task_id=task.id, content=diff_content, backend=self.name)`.

Wrap in `try/except Exception as e: raise BackendError(f"task {task.id}: Gemini API error: {e}") from e`.

**Note**: Use `genai.Client(api_key=...)`. Do not use `genai.configure()` — that is the older pattern from `google-generativeai`. This file uses `google-genai` (the new package).

---

### 2.10 `patchwork/router.py`

**Purpose**: Routes a Task to the appropriate backend name by matching keywords in the task description.

**Imports**:

```python
import re
from patchwork.models import Task
```

**Public interface**:

```python
FRONTEND_KEYWORDS: frozenset[str]
BACKEND_KEYWORDS: frozenset[str]

def route_task(task: Task) -> str:
    """Return backend name: 'gemini', 'codex', or 'claude'."""
    ...
```

**Internal logic**:

Module-level constants:

```python
FRONTEND_KEYWORDS: frozenset[str] = frozenset({
    "ui", "component", "react", "css", "tailwind", "frontend",
    "html", "jsx", "tsx", "vue", "svelte", "style", "stylesheet",
    "button", "modal", "form", "page", "layout",
})

BACKEND_KEYWORDS: frozenset[str] = frozenset({
    "api", "database", "sql", "fastapi", "auth", "backend", "server",
    "endpoint", "route", "middleware", "orm", "migration", "schema",
    "postgres", "mysql", "sqlite", "redis", "celery", "worker",
    "authentication", "authorization", "jwt", "token",
})
```

`route_task(task)`:
1. Tokenize: `words = set(re.split(r"[\s,./;:!?()\[\]{}\"']+", task.description.lower()))`.
2. `words.discard("")`.
3. If `words & FRONTEND_KEYWORDS`: return `"gemini"`.
4. Elif `words & BACKEND_KEYWORDS`: return `"codex"`.
5. Else: return `"claude"`.

**Design decision**: Frontend check runs before backend check. A task with both kinds of keywords routes to Gemini. This is a known v0 limitation.

**Edge cases**:
- Empty description → no matches → returns `"claude"`.
- Single-word description → works correctly.

---

### 2.11 `patchwork/reviewer.py`

**Purpose**: Uses Claude to review a generated patch against its task description and return an approve/reject decision with reasoning.

**Imports**:

```python
import re
from anthropic import Anthropic, APIError
from patchwork.models import Task, Patch, ReviewResult, ReviewDecision
from patchwork.tracing import traced
```

**Public interface**:

```python
REVIEWER_SYSTEM_PROMPT: str  # module-level constant — see §5 for exact text

class PatchReviewer:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None: ...

    @traced
    def review(self, patch: Patch, task: Task) -> ReviewResult: ...

    def _parse_response(self, raw: str, task_id: str) -> ReviewResult: ...
```

**Internal logic**:

`__init__(api_key, model)`:
1. If `not api_key`: raise `ValueError("ANTHROPIC_API_KEY is required for PatchReviewer")`.
2. `self._client = Anthropic(api_key=api_key)`.
3. `self._model = model`.

`review(patch, task)`:
1. Build user message:
   ```
   Task description: {task.description}

   Generated patch:
   {patch.content}
   ```
2. Call:
   ```python
   response = self._client.messages.create(
       model=self._model,
       max_tokens=1024,
       system=REVIEWER_SYSTEM_PROMPT,
       messages=[{"role": "user", "content": user_message}],
   )
   ```
3. `raw_text = response.content[0].text`.
4. Return `self._parse_response(raw_text, patch.task_id)`.

Wrap in:
```python
try:
    response = self._client.messages.create(...)
except APIError as e:
    return ReviewResult(
        task_id=patch.task_id,
        decision=ReviewDecision.reject,
        reasoning=f"Reviewer API error: {e}",
    )
```
Do not raise on API error — a failed review counts as a rejection.

`_parse_response(raw, task_id)`:
1. `decision_match = re.search(r"DECISION:\s*(APPROVE|REJECT)", raw, re.IGNORECASE)`.
2. If no match: return `ReviewResult(task_id=task_id, decision=ReviewDecision.reject, reasoning="Unparseable reviewer response")`.
3. `decision_str = decision_match.group(1).upper()`.
4. `decision = ReviewDecision.approve if decision_str == "APPROVE" else ReviewDecision.reject`.
5. `reasoning_match = re.search(r"REASONING:\s*(.+)", raw, re.IGNORECASE | re.DOTALL)`.
6. `reasoning = reasoning_match.group(1).strip() if reasoning_match else ""`.
7. Return `ReviewResult(task_id=task_id, decision=decision, reasoning=reasoning)`.

---

### 2.12 `patchwork/patch.py`

**Purpose**: Validates and applies unified diff patches using `git apply`, acting as the final gatekeeper before any patch modifies the working tree.

**Imports**:

```python
import os
import subprocess
import tempfile
from pathlib import Path
from patchwork.models import Patch
```

**Public interface**:

```python
class PatchError(Exception):
    """Raised when patch validation or application fails."""
    pass


def validate_patch(patch: Patch) -> None:
    """Run git apply --check. Raises PatchError if patch cannot be applied."""
    ...


def apply_patch(patch: Patch) -> None:
    """Apply the patch via git apply. Call validate_patch first."""
    ...


def _write_temp_patch(content: str) -> Path:
    """Write patch content to a named temp file and return its Path."""
    ...
```

**Internal logic**:

`_write_temp_patch(content)`:
1. `tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8")`.
2. `tmp.write(content)`.
3. `tmp.close()`.
4. Return `Path(tmp.name)`.

`validate_patch(patch)`:
1. If `not patch.content.strip()`: raise `PatchError(f"task {patch.task_id}: patch content is empty")`.
2. `tmp_path = _write_temp_patch(patch.content)`.
3. `try:`
4.   `result = subprocess.run(["git", "apply", "--check", str(tmp_path)], capture_output=True, text=True)`.
5.   If `result.returncode != 0`: raise `PatchError(f"task {patch.task_id}: git apply --check failed: {result.stderr.strip()}")`.
6. `finally: os.unlink(tmp_path)`.

`apply_patch(patch)`:
1. `tmp_path = _write_temp_patch(patch.content)`.
2. `try:`
3.   `result = subprocess.run(["git", "apply", str(tmp_path)], capture_output=True, text=True)`.
4.   If `result.returncode != 0`: raise `PatchError(f"task {patch.task_id}: git apply failed: {result.stderr.strip()}")`.
5. `finally: os.unlink(tmp_path)`.

**Edge cases**:
- `git` not on PATH → `FileNotFoundError` from `subprocess.run`. Let it propagate — user must have git installed.
- Not in a git repo → `git apply` exits 128, stderr says "not a git repository". Becomes a `PatchError`.
- Race condition (patch validates then fails on apply due to concurrent changes) → `PatchError` from `apply_patch`. Expected behavior.
- Temp file cleanup: `finally` block guarantees deletion even on error.

---

### 2.13 `patchwork/cli.py`

**Purpose**: Entry-point CLI with two commands — `plan` (decomposes a feature into tasks and saves JSON) and `exec` (routes, generates, reviews, and applies patches).

**Imports**:

```python
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from anthropic import Anthropic, APIError
from rich.console import Console
from rich.table import Table

from patchwork.backends import REGISTRY
from patchwork.backends.base import BackendError
from patchwork.config import get_settings
from patchwork.models import Plan, Task, TaskStatus, ReviewDecision, slugify
from patchwork import patch as patch_module
from patchwork.patch import PatchError
from patchwork.reviewer import PatchReviewer
from patchwork.router import route_task
from patchwork.tracing import traced
```

**Public interface**:

```python
app: typer.Typer  # module-level

@app.command()
def plan(feature: Annotated[str, typer.Argument(help="Feature description")]) -> None: ...

@app.command(name="exec")
def exec_plan(plan_file: Annotated[Path, typer.Argument(help="Path to plan JSON")]) -> None: ...
```

Module-level initialization:
```python
app = typer.Typer(name="patchwork", add_completion=False)
console = Console()
```

---

**`plan` command — internal logic**:

1. `settings = get_settings()`.
2. If `not settings.anthropic_api_key`: `console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]"); raise typer.Exit(1)`.
3. `client = Anthropic(api_key=settings.anthropic_api_key)`.
4. Build `planner_system` (see §6 for exact text).
5. `user_message = f"Feature: {feature}"`.
6. Call:
   ```python
   response = client.messages.create(
       model=settings.claude_model,
       max_tokens=2048,
       system=planner_system,
       messages=[{"role": "user", "content": user_message}],
   )
   ```
7. `raw = response.content[0].text`.
8. Parse JSON:
   - `match = re.search(r"\[.*\]", raw, re.DOTALL)`.
   - If no match: `console.print(f"[red]Failed to parse plan. Raw response:\n{raw}[/red]"); raise typer.Exit(1)`.
   - `task_dicts = json.loads(match.group(0))`.
9. Validate:
   - Must be a `list`.
   - Length between 3 and 7 inclusive.
   - Each item is a `dict` with a `"description"` key.
   - If validation fails: print error and `raise typer.Exit(1)`.
10. Build `Task` objects, overriding IDs to canonical format:
    ```python
    tasks = [
        Task(id=f"task-{i+1:03d}", description=d["description"])
        for i, d in enumerate(task_dicts)
    ]
    ```
11. `slug = slugify(feature)`.
12. If not `slug`: `console.print("[red]Could not slugify feature name[/red]"); raise typer.Exit(1)`.
13. `plan_obj = Plan(slug=slug, feature=feature, tasks=tasks)`.
14. `timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")`.
15. `settings.plan_dir.mkdir(parents=True, exist_ok=True)`.
16. `plan_file = settings.plan_dir / f"{slug}-{timestamp}.json"`.
17. `plan_file.write_text(plan_obj.model_dump_json(indent=2), encoding="utf-8")`.
18. `console.print(f"[green]Plan saved:[/green] {plan_file}")`.
19. Print a Rich table:
    - Columns: "Task", "Description"
    - One row per task.

---

**`exec_plan` command — internal logic**:

1. `plan_file = plan_file.resolve()`.
2. If `not plan_file.exists()`: `console.print(f"[red]Plan file not found: {plan_file}[/red]"); raise typer.Exit(1)`.
3. `plan_obj = Plan.model_validate_json(plan_file.read_text(encoding="utf-8"))`.
4. `settings = get_settings()`.
5. If `not settings.anthropic_api_key`: print error and exit 1.
6. `reviewer = PatchReviewer(api_key=settings.anthropic_api_key, model=settings.claude_model)`.
7. `repo_context = _get_repo_context()`.
8. For each `task` in `plan_obj.tasks`:
   a. `console.print(f"\n[bold]Task {task.id}[/bold]: {task.description}")`.
   b. `task.backend = route_task(task)`.
   c. `console.print(f"  → routing to [cyan]{task.backend}[/cyan]")`.
   d. Determine API key:
      ```python
      key_map = {
          "claude": settings.anthropic_api_key,
          "codex": settings.openai_api_key,
          "gemini": settings.google_api_key,
      }
      model_map = {
          "claude": settings.claude_model,
          "codex": settings.openai_model,
          "gemini": settings.gemini_model,
      }
      api_key = key_map.get(task.backend)
      model = model_map.get(task.backend, "")
      ```
   e. If `not api_key`: `task.status = TaskStatus.failed; task.rejection_reason = f"API key not set for {task.backend}"; continue`.
   f. `backend_cls = REGISTRY[task.backend]`.
   g. `backend = backend_cls(api_key=api_key, model=model)`.
   h. `task.status = TaskStatus.running`.
   i. Try:
      ```python
      generated_patch = backend.generate_patch(task, repo_context)
      ```
      Except `(BackendError, Exception) as e`:
      ```python
      task.status = TaskStatus.failed
      task.rejection_reason = str(e)
      console.print(f"  [red]✗ Generation failed[/red]: {e}")
      continue
      ```
   j. Try:
      ```python
      review_result = reviewer.review(generated_patch, task)
      ```
      Except `Exception as e`:
      ```python
      task.status = TaskStatus.failed
      task.rejection_reason = f"Review error: {e}"
      console.print(f"  [red]✗ Review error[/red]: {e}")
      continue
      ```
   k. If `review_result.decision == ReviewDecision.approve`:
      ```python
      try:
          patch_module.validate_patch(generated_patch)
          patch_module.apply_patch(generated_patch)
          task.status = TaskStatus.approved
          console.print("  [green]✓ Applied[/green]")
      except PatchError as e:
          task.status = TaskStatus.rejected
          task.rejection_reason = str(e)
          console.print(f"  [red]✗ Patch error[/red]: {e}")
      ```
   l. Else (`reject`):
      ```python
      task.status = TaskStatus.rejected
      task.rejection_reason = review_result.reasoning
      console.print(f"  [yellow]✗ Rejected[/yellow]: {review_result.reasoning[:80]}")
      ```
9. Write updated plan back to disk: `plan_file.write_text(plan_obj.model_dump_json(indent=2), encoding="utf-8")`.
10. Print summary table (see below).

---

**`_get_repo_context()` helper** (module-level private function in `cli.py`):

```python
def _get_repo_context() -> str:
    """Return lightweight repo context string for backends. Returns '' on failure."""
    ...
```

Internal logic:
1. Run `subprocess.run(["git", "ls-files"], capture_output=True, text=True)`.
2. If exit code 0: `file_list = "\n".join(result.stdout.splitlines()[:100])`. Else: `file_list = ""`.
3. Run `subprocess.run(["git", "log", "--oneline", "-10"], capture_output=True, text=True)`.
4. If exit code 0: `recent_log = result.stdout.strip()`. Else: `recent_log = ""`.
5. If both empty: return `""`.
6. Return:
   ```
   === Tracked files (first 100) ===
   {file_list}

   === Recent git log ===
   {recent_log}
   ```
Wrap the entire function in `try/except Exception: return ""`.

---

**Summary table** (called at end of `exec_plan`):

```python
STATUS_STYLES = {
    TaskStatus.approved: "green",
    TaskStatus.rejected: "yellow",
    TaskStatus.failed: "red",
    TaskStatus.pending: "dim",
    TaskStatus.running: "blue",
}

table = Table(title="Patchwork Execution Summary")
table.add_column("Task", style="bold")
table.add_column("Backend")
table.add_column("Status")
table.add_column("Note")

for task in plan_obj.tasks:
    style = STATUS_STYLES.get(task.status, "")
    note = (task.rejection_reason or "")[:60]
    table.add_row(
        task.id,
        task.backend or "—",
        f"[{style}]{task.status.value}[/{style}]",
        note,
    )

console.print(table)
```

---

## 3. Test Files

### 3.1 `tests/__init__.py`

Empty file. Required for pytest test discovery.

---

### 3.2 `tests/test_models.py`

**Purpose**: Verify Pydantic models serialize/deserialize correctly and `slugify` behaves as specified.

**Imports**:

```python
import pytest
from datetime import timezone
from patchwork.models import (
    Task, Patch, Plan, ReviewResult, ReviewDecision, TaskStatus, slugify
)
```

**Test cases**:

| Test name | What it verifies |
|---|---|
| `test_task_default_status` | New `Task` has `status=TaskStatus.pending` and `backend=None` |
| `test_task_status_can_be_set` | Setting `task.status = TaskStatus.approved` is accepted by the model |
| `test_task_rejection_reason_defaults_none` | `task.rejection_reason` is `None` by default |
| `test_patch_roundtrip` | `Patch.model_dump_json()` → `Patch.model_validate_json()` produces equal object |
| `test_plan_roundtrip` | `Plan.model_dump_json()` → `Plan.model_validate_json()` produces equal object |
| `test_plan_slug_set_by_caller` | `Plan.slug` is set by caller, not auto-generated |
| `test_plan_created_at_utc` | `plan.created_at.tzinfo` is not `None` (timezone-aware) |
| `test_review_result_approve` | `ReviewResult(decision=ReviewDecision.approve, ...)` round-trips |
| `test_review_result_reject` | `ReviewResult(decision=ReviewDecision.reject, ...)` round-trips |
| `test_slugify_basic` | `slugify("Add user auth")` == `"add-user-auth"` |
| `test_slugify_special_chars` | `slugify("Add /api/v2 endpoint!")` == `"add-api-v2-endpoint"` |
| `test_slugify_truncates` | Input of 100 chars produces output of max 60 chars |
| `test_slugify_empty` | `slugify("")` returns `""` |
| `test_slugify_only_specials` | `slugify("!!!")` returns `""` |

Implementation pattern:
```python
def test_task_default_status():
    task = Task(id="task-001", description="do something")
    assert task.status == TaskStatus.pending
    assert task.backend is None

def test_slugify_basic():
    assert slugify("Add user auth") == "add-user-auth"
```

---

### 3.3 `tests/test_router.py`

**Purpose**: Verify keyword-based routing returns the correct backend for various task descriptions.

**Imports**:

```python
import pytest
from patchwork.models import Task
from patchwork.router import route_task
```

**Test cases**:

| Test name | Input description | Expected |
|---|---|---|
| `test_routes_ui_to_gemini` | `"add a button component to the UI"` | `"gemini"` |
| `test_routes_react_to_gemini` | `"create a React modal for login"` | `"gemini"` |
| `test_routes_css_to_gemini` | `"update tailwind css styles for header"` | `"gemini"` |
| `test_routes_api_to_codex` | `"add a REST api endpoint for users"` | `"codex"` |
| `test_routes_database_to_codex` | `"write sql migration for posts table"` | `"codex"` |
| `test_routes_auth_to_codex` | `"implement jwt auth middleware"` | `"codex"` |
| `test_routes_refactor_to_claude` | `"refactor the router module"` | `"claude"` |
| `test_routes_docs_to_claude` | `"write documentation for the module"` | `"claude"` |
| `test_routes_empty_to_claude` | `""` | `"claude"` |
| `test_frontend_wins_over_backend` | `"add React frontend for the api endpoint"` | `"gemini"` |

Implementation pattern:
```python
def test_routes_ui_to_gemini():
    task = Task(id="task-001", description="add a button component to the UI")
    assert route_task(task) == "gemini"
```

---

### 3.4 `tests/test_patch.py`

**Purpose**: Verify patch validation and application, including error handling and temp file cleanup.

**Imports**:

```python
import os
import pytest
from unittest.mock import patch, MagicMock, call
from patchwork.models import Patch
from patchwork.patch import validate_patch, apply_patch, PatchError, _write_temp_patch
```

**Test cases**:

| Test name | What it verifies |
|---|---|
| `test_validate_empty_content_raises` | `validate_patch(Patch(content="", ...))` raises `PatchError` without calling subprocess |
| `test_validate_whitespace_content_raises` | `validate_patch(Patch(content="  \n\t", ...))` raises `PatchError` without calling subprocess |
| `test_validate_calls_git_apply_check` | When `subprocess.run` returns rc=0, no exception raised; `git apply --check` was called |
| `test_validate_raises_on_nonzero_exit` | When `subprocess.run` returns rc=1, `PatchError` is raised containing stderr text |
| `test_apply_calls_git_apply_no_check` | `apply_patch` calls `subprocess.run` with `["git", "apply", ...]` (no `--check`) |
| `test_apply_raises_on_failure` | When `subprocess.run` returns rc=1, `PatchError` is raised |
| `test_tempfile_deleted_on_success` | After successful `validate_patch`, `os.unlink` was called with the temp path |
| `test_tempfile_deleted_on_failure` | After failed `validate_patch`, `os.unlink` is still called (finally block) |

Implementation pattern for mocked subprocess test:
```python
VALID_PATCH = Patch(
    task_id="task-001",
    content="--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n",
    backend="claude",
)

def test_validate_calls_git_apply_check():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        validate_patch(VALID_PATCH)
    args = mock_run.call_args[0][0]
    assert "git" in args
    assert "--check" in args
```

For cleanup tests, mock both `subprocess.run` and `os.unlink`:
```python
def test_tempfile_deleted_on_failure():
    mock_result = MagicMock(returncode=1, stderr="bad patch")
    with patch("subprocess.run", return_value=mock_result), \
         patch("os.unlink") as mock_unlink:
        with pytest.raises(PatchError):
            validate_patch(VALID_PATCH)
    mock_unlink.assert_called_once()
```

---

## 4. Example Files

### 4.1 `examples/hello_feature.md`

Copy verbatim:

```markdown
# Example: Hello Feature

This example walks through using Patchwork to add a `/hello` endpoint to a minimal FastAPI app.

## Setup

```bash
mkdir demo && cd demo && git init
printf 'from fastapi import FastAPI\napp = FastAPI()\n' > main.py
git add main.py && git commit -m "initial"

uv pip install -e /path/to/patchwork
cp /path/to/patchwork/.env.example .env
# Edit .env — add your ANTHROPIC_API_KEY at minimum
```

## Step 1: Plan

```bash
patchwork plan "add a /hello endpoint that returns {\"message\": \"hello world\"}"
```

Expected output:
```
Plan saved: .patchwork/plans/add-a-hello-endpoint-20250101-120000.json
 Task      Description
 ───────────────────────────────────────────────────────────────
 task-001  Add GET /hello route returning {"message": "hello world"}
 task-002  Add pytest test for the /hello route
```

## Step 2: Execute

```bash
patchwork exec .patchwork/plans/add-a-hello-endpoint-20250101-120000.json
```

Expected output:
```
Task task-001: Add GET /hello route returning {"message": "hello world"}
  → routing to codex
  ✓ Applied

Task task-002: Add pytest test for the /hello route
  → routing to codex
  ✓ Applied

╭──────────────────────────────────────────────────────╮
│           Patchwork Execution Summary                │
├──────────┬─────────┬──────────┬──────────────────────┤
│ Task     │ Backend │ Status   │ Note                 │
├──────────┼─────────┼──────────┼──────────────────────┤
│ task-001 │ codex   │ approved │                      │
│ task-002 │ codex   │ approved │                      │
╰──────────┴─────────┴──────────┴──────────────────────╯
```

## Step 3: Verify

```bash
git diff HEAD~1    # review the applied patches
uvicorn main:app --reload
curl http://localhost:8000/hello
# {"message": "hello world"}
```

## Troubleshooting

**"API key not set"** — Edit `.env` and add the missing key for the routed backend.

**"git apply --check failed"** — The model didn't have enough context. Try running `exec` again, or add more detail to the task description in the plan JSON before re-running.

**"Rejected: ..."** — Claude's reviewer found an issue. Read the reasoning. Fix the plan JSON's task description to be more precise, then re-run `exec`.
```

---

## 5. Reviewer Prompt Template

Stored as `REVIEWER_SYSTEM_PROMPT` in `patchwork/reviewer.py`. Copy verbatim:

```python
REVIEWER_SYSTEM_PROMPT = """\
You are a senior software engineer performing a code review on a generated diff patch.

Your job is to determine whether the patch correctly and safely implements the given task.

Review criteria:
1. Correctness: Does the patch implement exactly what the task asks for?
2. Safety: Does the patch introduce security vulnerabilities? (SQL injection, XSS, path traversal, hardcoded secrets, etc.)
3. Completeness: Does the patch leave obvious work unfinished?
4. Validity: Is the unified diff syntactically valid with proper --- +++ @@ headers?
5. Scope: Does the patch make changes beyond what the task requires?

Respond using EXACTLY this format — no deviations, no preamble, no trailing text:

DECISION: APPROVE
REASONING: <one to three sentences explaining the decision>

or:

DECISION: REJECT
REASONING: <one to three sentences explaining specifically what is wrong and must be fixed>
"""
```

---

## 6. Planner Prompt Template

Defined inline in the `plan` command function body in `cli.py` — not a module-level constant. Copy verbatim into `planner_system` local variable:

```python
planner_system = """\
You are a software architect. Your job is to decompose a feature request into a list of 3 to 7 discrete, atomic coding tasks.

Rules:
1. Each task must be independently implementable as a single code change.
2. Order tasks by dependency — earlier tasks must not depend on later ones.
3. Each description must be one sentence, action-oriented, and specific enough for a junior developer to implement without clarifying questions.
4. Do not include testing tasks unless the feature request explicitly asks for tests.
5. Do not include documentation tasks unless explicitly requested.
6. Output ONLY a JSON array. No preamble, no explanation, no markdown fences.

Output format (exactly):
[
  {"id": "task-001", "description": "..."},
  {"id": "task-002", "description": "..."}
]
"""
```

**Parsing strategy** in `plan` command (step 8):
1. `match = re.search(r"\[.*\]", raw, re.DOTALL)` — greedily find the outermost array.
2. If no match → print `raw` + error message → `raise typer.Exit(1)`.
3. `task_dicts = json.loads(match.group(0))` wrapped in `try/except json.JSONDecodeError`.
4. Validate: `isinstance(task_dicts, list)` and `3 <= len(task_dicts) <= 7` and each element has `"description"`.
5. **Always override** `"id"` values to `"task-001"`, `"task-002"`, etc. Do not trust the model's IDs.

---

## 7. Integration Walkthrough

### `patchwork plan "add health endpoint"`

```
CLI: plan command
  │
  ├── get_settings() ────────────────────────────► Settings (reads .env)
  ├── Anthropic(api_key=settings.anthropic_api_key)
  ├── client.messages.create(system=planner_system, user="Feature: add health endpoint")
  │       └── [@traced — Langfuse span if configured]
  ├── re.search → json.loads → validate 3-7 tasks
  ├── slugify("add health endpoint") → "add-health-endpoint"
  ├── Plan(slug=..., feature=..., tasks=[Task("task-001", ...), ...])
  └── plan_file.write_text(plan.model_dump_json(indent=2))
        → .patchwork/plans/add-health-endpoint-20250101-120000.json
```

### `patchwork exec <plan.json>`

```
CLI: exec_plan command
  │
  ├── Plan.model_validate_json(file.read_text())
  ├── PatchReviewer(api_key=..., model=settings.claude_model)
  ├── _get_repo_context() ──────────────────────► git ls-files + git log --oneline -10
  │
  └── for each task:
        ├── route_task(task) ─────────────────────► "codex" | "gemini" | "claude"
        ├── REGISTRY[backend](api_key=..., model=...)
        ├── backend.generate_patch(task, repo_context)
        │       └── [@traced — Langfuse span: name="generate_patch"]
        │       └── returns Patch(task_id, content, backend)
        ├── reviewer.review(patch, task)
        │       └── [@traced — Langfuse span: name="review"]
        │       └── returns ReviewResult(decision, reasoning)
        ├── if APPROVE:
        │     ├── validate_patch(patch) ──────────► subprocess: git apply --check
        │     └── apply_patch(patch) ─────────────► subprocess: git apply
        └── if REJECT:
              └── task.status = rejected
                  task.rejection_reason = review_result.reasoning
```

---

## 8. File Creation Order

Implement in this order to avoid circular import errors:

1. `patchwork/__init__.py`
2. `patchwork/models.py`
3. `patchwork/tracing.py`
4. `patchwork/config.py`
5. `patchwork/backends/base.py`
6. `patchwork/backends/claude.py`
7. `patchwork/backends/codex.py`
8. `patchwork/backends/gemini.py`
9. `patchwork/backends/__init__.py` ← imports 6-8, so write last in backends/
10. `patchwork/router.py`
11. `patchwork/patch.py`
12. `patchwork/reviewer.py`
13. `patchwork/cli.py`
14. `tests/__init__.py`
15. `tests/test_models.py`
16. `tests/test_router.py`
17. `tests/test_patch.py`
18. `examples/hello_feature.md`
19. Root files: `pyproject.toml`, `.env.example`, `.gitignore`, `README.md`, `LICENSE`

---

## 9. MVP Stubs

These are out of scope for MVP. Create them as stubs so future implementers know the hook points. Do not call them from anywhere else in the codebase.

**`patchwork/memory.py`** — content:
```python
class MemoryStore:
    """Stub — not implemented in MVP."""

    def add(self, task_id: str, patch_content: str) -> None:
        raise NotImplementedError("MemoryStore not implemented in MVP")

    def query(self, description: str) -> list[str]:
        raise NotImplementedError("MemoryStore not implemented in MVP")
```

**`patchwork/eval.py`** — content:
```python
class EvalGate:
    """Stub — not implemented in MVP."""

    def evaluate(self, patch_content: str) -> bool:
        raise NotImplementedError("EvalGate not implemented in MVP")
```

---

Plan complete. BUILD_PLAN.md is ready for Codex.
