from anthropic import Anthropic, APIError

from patchwork.backends.base import Backend, BackendError
from patchwork.models import Task, Patch
from patchwork.tracing import traced


class ClaudeBackend(Backend):
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for ClaudeBackend")
        self._client = Anthropic(api_key=api_key)
        self._model = model

    @traced
    def generate_patch(self, task: Task, repo_context: str) -> Patch:
        user_message = f"""Task: {task.description}

Repository context:
{repo_context if repo_context else "(no context provided)"}

Generate a unified diff patch that implements this task.
"""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=self._build_system_prompt(),
                messages=[{"role": "user", "content": user_message}],
            )
        except APIError as e:
            raise BackendError(f"task {task.id}: Anthropic API error: {e}") from e

        raw_text = response.content[0].text
        diff_content = self._extract_diff(raw_text)
        if diff_content == "CANNOT_GENERATE" or not diff_content:
            raise BackendError(f"task {task.id}: Claude could not generate a patch")
        return Patch(task_id=task.id, content=diff_content, backend=self.name)
