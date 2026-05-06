import re

from patchwork.models import Task


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


def route_task(task: Task) -> str:
    """Return backend name: 'gemini', 'codex', or 'claude'."""
    if task.backend:
        return task.backend

    words = set(re.split(r"[\s,./;:!?()\[\]{}\"']+", task.description.lower()))
    words.discard("")
    if words & FRONTEND_KEYWORDS:
        return "gemini"
    if words & BACKEND_KEYWORDS:
        return "codex"
    return "claude"
