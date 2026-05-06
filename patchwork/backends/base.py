from abc import ABC, abstractmethod

from patchwork.config import get_settings
from patchwork.models import Task, Patch


class BackendError(Exception):
    """Raised when a backend fails to generate a usable patch."""
    pass


class Backend(ABC):
    name: str

    @abstractmethod
    def generate_patch(self, task: Task, repo_context: str, error_feedback: str | None = None) -> Patch:
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
        base_prompt = """You are a coding assistant that generates unified diff patches.

Rules:
1. Output ONLY a valid unified diff. No explanations, no markdown fences, no commentary.
2. The diff must start with "--- a/" on the first non-empty line.
3. Use standard unified diff format: --- a/<file>, +++ b/<file>, @@ hunks.
4. The patch must be directly applicable with `git apply`.
5. If creating a new file, use /dev/null as the source: --- /dev/null
6. Do not include binary files.
7. If you cannot generate a valid patch for this task, output exactly: CANNOT_GENERATE
"""
        if get_settings().caveman_mode:
            base_prompt += """
8. CAVEMAN MODE ENABLED: Do not use pleasantries, greetings, or conversational filler. Output the absolute minimum text required. Do not explain your code. Output ONLY the raw patch.
"""
        return base_prompt

    def _extract_diff(self, raw_response: str) -> str:
        """Strip markdown fences from raw_response and return clean diff text."""
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
