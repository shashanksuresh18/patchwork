import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from anthropic import Anthropic, APIError
from rich.console import Console
from rich.table import Table

from patchwork.agent_cli import AgentCliError, find_agent_command, run_agent_cli
from patchwork.backends import REGISTRY
from patchwork.backends.base import BackendError
from patchwork.config import get_settings
from patchwork.models import Plan, Task, TaskStatus, ReviewDecision, slugify
from patchwork import patch as patch_module
from patchwork.patch import PatchError
from patchwork.reviewer import PatchReviewer
from patchwork.router import route_task


app = typer.Typer(name="patchwork", add_completion=False)
console = Console()
error_console = Console(stderr=True)


DEFAULT_ENV = """# Patchwork local CLI mode
PATCHWORK_USE_CLI_BACKENDS=true
PATCHWORK_CLAUDE_CLI_COMMAND=claude -p
PATCHWORK_CODEX_CLI_COMMAND=codex exec
PATCHWORK_GEMINI_CLI_COMMAND=gemini -p
PATCHWORK_AGENT_CLI_TIMEOUT=7200
PATCHWORK_DEBUG_PROMPT=false
PATCHWORK_CAVEMAN_MODE=false
PATCHWORK_USE_GRAPHIFYY=false

# Optional API mode:
# PATCHWORK_USE_CLI_BACKENDS=false
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# GOOGLE_API_KEY=
"""


DEFAULT_CONFIG = """# Patchwork project config
# Runtime settings are currently read from .env.
"""


@app.command()
def init(
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing Patchwork config files"),
    ] = False,
) -> None:
    """Create Patchwork config files in the current project."""
    plan_dir = Path(".patchwork/plans")
    plan_dir.mkdir(parents=True, exist_ok=True)

    results = [
        _write_text_if_missing(Path(".env"), DEFAULT_ENV, force),
        _write_text_if_missing(Path(".patchwork/config.toml"), DEFAULT_CONFIG, force),
    ]

    table = Table(title="Patchwork Init")
    table.add_column("Path", style="bold")
    table.add_column("Status")
    table.add_row(str(plan_dir), "[green]ready[/green]")
    for path, wrote in results:
        table.add_row(str(path), "[green]created[/green]" if wrote else "[yellow]exists[/yellow]")
    console.print(table)


@app.command()
def doctor() -> None:
    """Check local Patchwork prerequisites."""
    settings = get_settings()
    checks: list[tuple[str, bool, str]] = []

    git_path = shutil.which("git")
    checks.append(("git", git_path is not None, git_path or "not found on PATH"))
    checks.append(("git repo", _is_git_repo(), "inside a git repo" if _is_git_repo() else "not inside a git repo"))

    if settings.use_cli_backends:
        for name, command in (
            ("claude", settings.claude_cli_command),
            ("codex", settings.codex_cli_command),
            ("gemini", settings.gemini_cli_command),
        ):
            found = find_agent_command(command)
            checks.append((name, found is not None, found or f"not found for command: {command}"))
    else:
        checks.extend(
            [
                ("ANTHROPIC_API_KEY", bool(settings.anthropic_api_key), "set" if settings.anthropic_api_key else "missing"),
                ("OPENAI_API_KEY", bool(settings.openai_api_key), "set" if settings.openai_api_key else "missing"),
                ("GOOGLE_API_KEY", bool(settings.google_api_key), "set" if settings.google_api_key else "missing"),
            ]
        )

    table = Table(title="Patchwork Doctor")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    for name, ok, detail in checks:
        table.add_row(name, "[green]OK[/green]" if ok else "[red]FAIL[/red]", detail)
    console.print(table)

    if any(not ok for _, ok, _ in checks):
        raise typer.Exit(1)


@app.command()
def plan(feature: Annotated[str, typer.Argument(help="Feature description")]) -> None:
    settings = get_settings()
    if not settings.use_cli_backends and not settings.anthropic_api_key:
        error_console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        raise typer.Exit(1)
    planner_system = """\
You are a software architect. Your job is to decompose a feature request into a list of discrete, atomic coding tasks.

Rules:
1. Each task must be independently implementable as a single code change.
2. Each description must be one sentence, action-oriented, and specific.
3. For each task, assign the best backend:
   - 'claude': architecture, refactoring, cross-cutting concerns, docs
   - 'codex': API, database, auth, backend, server
   - 'gemini': UI, React, CSS, frontend, components
4. List which files will likely be affected by each task.
5. Identify dependencies between tasks using their IDs.
6. Output ONLY a JSON array. No preamble, no explanation, no markdown fences.

Output format (exactly):
[
  {
    "id": "task-001",
    "description": "...",
    "backend": "claude|codex|gemini",
    "files_affected": ["file1.py", "file2.py"],
    "depends_on": []
  }
]
"""
    user_message = f"Feature: {feature}"
    referenced_context = _get_referenced_file_context(feature)
    if referenced_context:
        user_message = f"{user_message}\n\nReferenced local files:\n{referenced_context}"
    if settings.use_cli_backends:
        cli_prompt = f"""Decompose this exact feature request into implementation tasks.

{user_message}

Instructions:
{planner_system}
"""
        if settings.debug_prompt:
            debug_path = Path(".patchwork/debug-last-prompt.txt")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            debug_path.write_text(cli_prompt, encoding="utf-8")
            console.print(f"[yellow]Debug prompt saved:[/yellow] {debug_path}")
        try:
            raw = run_agent_cli(
                settings.claude_cli_command,
                cli_prompt,
                settings.agent_cli_timeout,
            )
        except AgentCliError as e:
            console.print(f"[red]Planner CLI error: {e}[/red]")
            raise typer.Exit(1) from e
    else:
        client = Anthropic(api_key=settings.anthropic_api_key)
        try:
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=2048,
                system=planner_system,
                messages=[{"role": "user", "content": user_message}],
            )
        except APIError as e:
            console.print(f"[red]Planner API error: {e}[/red]")
            raise typer.Exit(1) from e
        raw = response.content[0].text
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        console.print(f"[red]Failed to parse plan. Raw response:\n{raw}[/red]")
        raise typer.Exit(1)
    try:
        task_dicts = json.loads(match.group(0))
    except json.JSONDecodeError:
        console.print(f"[red]Failed to parse plan. Raw response:\n{raw}[/red]")
        raise typer.Exit(1)
    if (
        not isinstance(task_dicts, list)
        or not all(isinstance(d, dict) and "description" in d for d in task_dicts)
    ):
        console.print("[red]Planner returned invalid task list[/red]")
        raise typer.Exit(1)

    tasks = [
        Task(
            id=d.get("id", f"task-{i+1:03d}"),
            description=d["description"],
            backend=d.get("backend"),
            files_affected=d.get("files_affected", []),
            depends_on=d.get("depends_on", []),
        )
        for i, d in enumerate(task_dicts)
    ]
    slug = slugify(feature)
    if not slug:
        console.print("[red]Could not slugify feature name[/red]")
        raise typer.Exit(1)
    plan_obj = Plan(slug=slug, feature=feature, tasks=tasks)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    settings.plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = settings.plan_dir / f"{slug}-{timestamp}.json"
    plan_file.write_text(plan_obj.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"[green]Plan saved:[/green] {plan_file}")

    table = Table()
    table.add_column("Task")
    table.add_column("Description")
    for task in tasks:
        table.add_row(task.id, task.description)
    console.print(table)


@app.command(name="exec")
def exec_plan(plan_file: Annotated[Path, typer.Argument(help="Path to plan JSON")]) -> None:
    plan_file = plan_file.resolve()
    if not plan_file.exists():
        console.print(f"[red]Plan file not found: {plan_file}[/red]")
        raise typer.Exit(1)
    plan_obj = Plan.model_validate_json(plan_file.read_text(encoding="utf-8"))
    settings = get_settings()
    if not settings.use_cli_backends and not settings.anthropic_api_key:
        error_console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        raise typer.Exit(1)
    
    reviewer = PatchReviewer(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
        use_cli=settings.use_cli_backends,
        cli_command=settings.claude_cli_command,
        cli_timeout=settings.agent_cli_timeout,
    )
    repo_context = _get_repo_context()

    def _make_backend(backend_name: str):
        """Create a backend instance by name."""
        backend_cls = REGISTRY[backend_name]
        return backend_cls(
            api_key={
                "claude": settings.anthropic_api_key,
                "codex": settings.openai_api_key,
                "gemini": settings.google_api_key,
            }.get(backend_name),
            model={
                "claude": settings.claude_model,
                "codex": settings.openai_model,
                "gemini": settings.gemini_model,
            }.get(backend_name, ""),
            use_cli=settings.use_cli_backends,
            cli_command={
                "claude": settings.claude_cli_command,
                "codex": settings.codex_cli_command,
                "gemini": settings.gemini_cli_command,
            }.get(backend_name, ""),
            cli_timeout=settings.agent_cli_timeout,
        )

    def run_task(task: Task) -> None:
        console.print(f"\n[bold]Task {task.id}[/bold]: {task.description}")
        primary_backend = route_task(task)
        
        # Build fallback chain: primary → others
        all_backends = ["claude", "gemini", "codex"]
        fallback_chain = [primary_backend] + [b for b in all_backends if b != primary_backend]

        for backend_name in fallback_chain:
            task.backend = backend_name
            console.print(f"  → routing to [cyan]{backend_name}[/cyan]")
            backend = _make_backend(backend_name)

            error_feedback = None
            for attempt in range(settings.max_retries + 1):
                if attempt > 0:
                    console.print(f"  [yellow]↺ Retry {attempt}/{settings.max_retries}[/yellow]")
                
                task.status = TaskStatus.running
                try:
                    generated_patch = backend.generate_patch(task, repo_context, error_feedback)
                    review_result = reviewer.review(generated_patch, task)
                    
                    if review_result.decision == ReviewDecision.approve:
                        patch_module.validate_patch(generated_patch)
                        patch_module.apply_patch(generated_patch)
                        task.status = TaskStatus.approved
                        console.print("  [green]✓ Applied[/green]")
                        return
                    else:
                        error_feedback = f"Review rejected: {review_result.reasoning}"
                        console.print(f"  [yellow]✗ Rejected[/yellow]: {review_result.reasoning[:80]}")
                except (BackendError, PatchError, Exception) as e:
                    error_feedback = str(e)
                    console.print(f"  [red]✗ Attempt failed[/red]: {e}")
            
            # All retries exhausted for this backend — try fallback
            if backend_name != fallback_chain[-1]:
                console.print(f"  [yellow]⤳ Falling back from {backend_name}...[/yellow]")
        
        task.status = TaskStatus.failed
        task.rejection_reason = error_feedback

    # Parallel scheduler with dependency tracking
    with ThreadPoolExecutor(max_workers=4) as executor:
        while True:
            # Find tasks that are pending and have all dependencies approved
            ready_tasks = []
            for t in plan_obj.tasks:
                if t.status != TaskStatus.pending:
                    continue
                deps_ok = True
                for dep_id in t.depends_on:
                    dep_task = next((x for x in plan_obj.tasks if x.id == dep_id), None)
                    if not dep_task or dep_task.status != TaskStatus.approved:
                        deps_ok = False
                        break
                if deps_ok:
                    ready_tasks.append(t)
            
            if not ready_tasks:
                # Check if any tasks are still running or if we are stuck
                if any(t.status == TaskStatus.running for t in plan_obj.tasks):
                    import time
                    time.sleep(1)
                    continue
                break

            # Run ready tasks in parallel
            futures = {executor.submit(run_task, t): t for t in ready_tasks}
            for future in as_completed(futures):
                future.result() # Wait for batch to finish (or handle results as they come)

    plan_file.write_text(plan_obj.model_dump_json(indent=2), encoding="utf-8")
    _print_summary(plan_obj)


def _get_repo_context() -> str:
    """Return lightweight repo context string for backends. Returns '' on failure."""
    if get_settings().use_graphifyy:
        try:
            result = subprocess.run(["graphify"], capture_output=True, text=True)
            if result.returncode == 0:
                return f"=== Knowledge Graph Context ===\n{result.stdout}\n"
            else:
                error_console.print(f"[yellow]graphifyy failed: {result.stderr.strip()}. Falling back to git.[/yellow]")
        except Exception as e:
            error_console.print(f"[yellow]graphifyy execution error: {e}. Falling back to git.[/yellow]")

    try:
        result = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
        if result.returncode == 0:
            file_list = "\n".join(result.stdout.splitlines()[:100])
        else:
            file_list = ""
        result = subprocess.run(["git", "log", "--oneline", "-10"], capture_output=True, text=True)
        if result.returncode == 0:
            recent_log = result.stdout.strip()
        else:
            recent_log = ""
        if not file_list and not recent_log:
            return ""
        return f"""=== Tracked files (first 100) ===
{file_list}

=== Recent git log ===
{recent_log}
"""
    except Exception:
        return ""


def _get_referenced_file_context(text: str) -> str:
    paths = re.findall(r"[\w./\\-]+\.(?:md|txt)", text, flags=re.IGNORECASE)
    chunks = []
    for raw_path in paths[:5]:
        path = Path(raw_path)
        if not path.exists() or not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        chunks.append(f"--- {path} ---\n{content[:12000]}")
    return "\n\n".join(chunks)


def _is_git_repo() -> bool:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
    except Exception:
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _write_text_if_missing(path: Path, content: str, force: bool) -> tuple[Path, bool]:
    if path.exists() and not force:
        return path, False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path, True


def _print_summary(plan_obj: Plan) -> None:
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
            task.backend or "-",
            f"[{style}]{task.status.value}[/{style}]",
            note,
        )

    console.print(table)
