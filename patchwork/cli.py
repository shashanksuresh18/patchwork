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

from patchwork.agent_cli import AgentCliError, run_agent_cli
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


@app.command()
def plan(feature: Annotated[str, typer.Argument(help="Feature description")]) -> None:
    settings = get_settings()
    if not settings.use_cli_backends and not settings.anthropic_api_key:
        error_console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
        raise typer.Exit(1)
    planner_system = """\
You are a software architect. Your job is to decompose a feature request into a list of 3 to 7 discrete, atomic coding tasks.

Rules:
1. Each task must be independently implementable as a single code change.
2. Order tasks by dependency - earlier tasks must not depend on later ones.
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
    user_message = f"Feature: {feature}"
    if settings.use_cli_backends:
        try:
            raw = run_agent_cli(
                settings.claude_cli_command,
                f"{planner_system}\n\n{user_message}",
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
        or not 3 <= len(task_dicts) <= 7
        or not all(isinstance(d, dict) and "description" in d for d in task_dicts)
    ):
        console.print("[red]Planner returned invalid task list[/red]")
        raise typer.Exit(1)

    tasks = [
        Task(id=f"task-{i+1:03d}", description=d["description"])
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

    for task in plan_obj.tasks:
        console.print(f"\n[bold]Task {task.id}[/bold]: {task.description}")
        task.backend = route_task(task)
        console.print(f"  → routing to [cyan]{task.backend}[/cyan]")
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
        cli_command_map = {
            "claude": settings.claude_cli_command,
            "codex": settings.codex_cli_command,
            "gemini": settings.gemini_cli_command,
        }
        api_key = key_map.get(task.backend)
        model = model_map.get(task.backend, "")
        cli_command = cli_command_map.get(task.backend, "")
        if not settings.use_cli_backends and not api_key:
            task.status = TaskStatus.failed
            task.rejection_reason = f"API key not set for {task.backend}"
            continue
        backend_cls = REGISTRY[task.backend]
        backend = backend_cls(
            api_key=api_key,
            model=model,
            use_cli=settings.use_cli_backends,
            cli_command=cli_command,
            cli_timeout=settings.agent_cli_timeout,
        )
        task.status = TaskStatus.running
        try:
            generated_patch = backend.generate_patch(task, repo_context)
        except BackendError as e:
            task.status = TaskStatus.failed
            task.rejection_reason = str(e)
            console.print(f"  [red]✗ Generation failed[/red]: {e}")
            continue
        except Exception as e:
            task.status = TaskStatus.failed
            task.rejection_reason = f"Unexpected error: {e}"
            console.print(f"  [red]✗ Unexpected error[/red]: {e}")
            raise
        try:
            review_result = reviewer.review(generated_patch, task)
        except Exception as e:
            task.status = TaskStatus.failed
            task.rejection_reason = f"Review error: {e}"
            console.print(f"  [red]✗ Review error[/red]: {e}")
            continue
        if review_result.decision == ReviewDecision.approve:
            try:
                patch_module.validate_patch(generated_patch)
                patch_module.apply_patch(generated_patch)
                task.status = TaskStatus.approved
                console.print("  [green]✓ Applied[/green]")
            except PatchError as e:
                task.status = TaskStatus.rejected
                task.rejection_reason = str(e)
                console.print(f"  [red]✗ Patch error[/red]: {e}")
        else:
            task.status = TaskStatus.rejected
            task.rejection_reason = review_result.reasoning
            console.print(f"  [yellow]✗ Rejected[/yellow]: {review_result.reasoning[:80]}")

    plan_file.write_text(plan_obj.model_dump_json(indent=2), encoding="utf-8")
    _print_summary(plan_obj)


def _get_repo_context() -> str:
    """Return lightweight repo context string for backends. Returns '' on failure."""
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
