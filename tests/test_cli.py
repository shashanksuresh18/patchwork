from pathlib import Path

from typer.testing import CliRunner

from patchwork.cli import _get_referenced_file_context, app
from patchwork.config import get_settings


runner = CliRunner()


def test_init_creates_default_files():
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert Path(".env").exists()
        assert Path(".patchwork/plans").is_dir()
        assert Path(".patchwork/config.toml").exists()
        assert "PATCHWORK_USE_CLI_BACKENDS=true" in Path(".env").read_text(encoding="utf-8")


def test_init_does_not_overwrite_existing_env_without_force():
    with runner.isolated_filesystem():
        Path(".env").write_text("KEEP_ME=true\n", encoding="utf-8")

        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert Path(".env").read_text(encoding="utf-8") == "KEEP_ME=true\n"


def test_doctor_passes_when_cli_tools_are_found(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr("patchwork.cli.shutil.which", lambda name: f"/usr/bin/{name}" if name == "git" else None)
    monkeypatch.setattr("patchwork.cli._is_git_repo", lambda: True)
    monkeypatch.setattr("patchwork.cli.find_agent_command", lambda command: f"/usr/bin/{command.split()[0]}")

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Patchwork Doctor" in result.output


def test_doctor_fails_when_cli_tool_is_missing(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setattr("patchwork.cli.shutil.which", lambda name: f"/usr/bin/{name}" if name == "git" else None)
    monkeypatch.setattr("patchwork.cli._is_git_repo", lambda: True)
    monkeypatch.setattr("patchwork.cli.find_agent_command", lambda command: None if command.startswith("gemini") else "/usr/bin/tool")

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "gemini" in result.output


def test_referenced_file_context_includes_markdown_file():
    with runner.isolated_filesystem():
        Path("PROMPT1.md").write_text("Build the app\n", encoding="utf-8")

        context = _get_referenced_file_context("Read PROMPT1.md and plan it")

        assert "--- PROMPT1.md ---" in context
        assert "Build the app" in context


def test_plan_puts_feature_first_for_cli(monkeypatch):
    get_settings.cache_clear()
    captured = {}

    def fake_run_agent_cli(command, prompt, timeout, system_prompt=None, prompt_via_stdin=True):
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["prompt_via_stdin"] = prompt_via_stdin
        return '[{"id": "x", "description": "One"}, {"id": "y", "description": "Two"}, {"id": "z", "description": "Three"}]'

    monkeypatch.setattr("patchwork.cli.run_agent_cli", fake_run_agent_cli)

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["plan", "Build the thing"])

        assert result.exit_code == 0
        assert captured["prompt"].startswith("Decompose this exact feature request")
        assert "Feature: Build the thing" in captured["prompt"]
        assert "decompose a feature request" in captured["prompt"]
        assert captured["system_prompt"] is None
        assert captured["prompt_via_stdin"] is True


def test_plan_writes_debug_prompt_when_enabled(monkeypatch):
    get_settings.cache_clear()

    def fake_run_agent_cli(command, prompt, timeout, system_prompt=None, prompt_via_stdin=True):
        return '[{"id": "x", "description": "One"}, {"id": "y", "description": "Two"}, {"id": "z", "description": "Three"}]'

    monkeypatch.setattr("patchwork.cli.run_agent_cli", fake_run_agent_cli)

    with runner.isolated_filesystem():
        Path(".env").write_text("PATCHWORK_DEBUG_PROMPT=true\n", encoding="utf-8")
        result = runner.invoke(app, ["plan", "Build the thing"])

        assert result.exit_code == 0
        debug_path = Path(".patchwork/debug-last-prompt.txt")
        assert debug_path.exists()
        assert "Feature: Build the thing" in debug_path.read_text(encoding="utf-8")
