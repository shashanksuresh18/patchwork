from patchwork.backends.claude import ClaudeBackend
from patchwork.backends.codex import CodexBackend
from patchwork.backends.gemini import GeminiBackend

REGISTRY: dict[str, type] = {
    "claude": ClaudeBackend,
    "codex": CodexBackend,
    "gemini": GeminiBackend,
}
