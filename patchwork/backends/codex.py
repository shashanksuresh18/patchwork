from openai import OpenAI, APIError

from patchwork.agent_cli import AgentCliError, run_agent_cli
from patchwork.backends.base import Backend, BackendError
from patchwork.models import Task, Patch
from patchwork.tracing import traced


class CodexBackend(Backend):
    name = "codex"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        use_cli: bool = True,
        cli_command: str = "codex exec",
        cli_timeout: int = 7200,
    ) -> None:
        self._use_cli = use_cli
        self._cli_command = cli_command
        self._cli_timeout = cli_timeout
        self._model = model
        self._client = None
        if self._use_cli:
            return
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for CodexBackend")
        self._client = OpenAI(api_key=api_key)

    @traced
    def generate_patch(self, task: Task, repo_context: str) -> Patch:
        user_message = f"""Task: {task.description}

Repository context:
{repo_context if repo_context else "(no context provided)"}

Generate a unified diff patch that implements this task.
"""
        if self._use_cli:
            prompt = f"{self._build_system_prompt()}\n\n{user_message}"
            try:
                raw_text = run_agent_cli(self._cli_command, prompt, self._cli_timeout)
            except AgentCliError as e:
                raise BackendError(f"task {task.id}: Codex CLI error: {e}") from e
        else:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=4096,
                    messages=[
                        {"role": "system", "content": self._build_system_prompt()},
                        {"role": "user", "content": user_message},
                    ],
                )
            except APIError as e:
                raise BackendError(f"task {task.id}: OpenAI API error: {e}") from e
            raw_text = response.choices[0].message.content

        diff_content = self._extract_diff(raw_text)
        if diff_content == "CANNOT_GENERATE" or not diff_content:
            raise BackendError(f"task {task.id}: Codex could not generate a patch")
        return Patch(task_id=task.id, content=diff_content, backend=self.name)
