import pytest

from patchwork.models import Task
from patchwork.router import route_task


def test_routes_ui_to_gemini():
    task = Task(id="task-001", description="add a button component to the UI")
    assert route_task(task) == "gemini"


def test_routes_react_to_gemini():
    task = Task(id="task-001", description="create a React modal for login")
    assert route_task(task) == "gemini"


def test_routes_css_to_gemini():
    task = Task(id="task-001", description="update tailwind css styles for header")
    assert route_task(task) == "gemini"


def test_routes_api_to_codex():
    task = Task(id="task-001", description="add a REST api endpoint for users")
    assert route_task(task) == "codex"


def test_routes_database_to_codex():
    task = Task(id="task-001", description="write sql migration for posts table")
    assert route_task(task) == "codex"


def test_routes_auth_to_codex():
    task = Task(id="task-001", description="implement jwt auth middleware")
    assert route_task(task) == "codex"


def test_routes_refactor_to_claude():
    task = Task(id="task-001", description="refactor the router module")
    assert route_task(task) == "claude"


def test_routes_docs_to_claude():
    task = Task(id="task-001", description="write documentation for the module")
    assert route_task(task) == "claude"


def test_routes_empty_to_claude():
    task = Task(id="task-001", description="")
    assert route_task(task) == "claude"


def test_frontend_wins_over_backend():
    task = Task(id="task-001", description="add React frontend for the api endpoint")
    assert route_task(task) == "gemini"
