import google.genai as genai

from patchwork.backends.base import Backend, BackendError
from patchwork.models import Task, Patch
from patchwork.tracing import traced


class GeminiBackend(Backend):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro") -> None:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required for GeminiBackend")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @traced
    def generate_patch(self, task: Task, repo_context: str) -> Patch:
        user_message = f"""Task: {task.description}

Repository context:
{repo_context if repo_context else "(no context provided)"}

Generate a unified diff patch that implements this task.
"""
        full_prompt = f"{self._build_system_prompt()}\n\n{user_message}"
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=full_prompt,
            )
        except Exception as e:
            raise BackendError(f"task {task.id}: Gemini API error: {e}") from e

        raw_text = response.text
        diff_content = self._extract_diff(raw_text)
        if diff_content == "CANNOT_GENERATE" or not diff_content:
            raise BackendError(f"task {task.id}: Gemini could not generate a patch")
        return Patch(task_id=task.id, content=diff_content, backend=self.name)
