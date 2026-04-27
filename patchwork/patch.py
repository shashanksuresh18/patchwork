import os
import subprocess
import tempfile
from pathlib import Path

from patchwork.models import Patch


class PatchError(Exception):
    """Raised when patch validation or application fails."""
    pass


def validate_patch(patch: Patch) -> None:
    """Run git apply --check. Raises PatchError if patch cannot be applied."""
    if not patch.content.strip():
        raise PatchError(f"task {patch.task_id}: patch content is empty")
    tmp_path = _write_temp_patch(patch.content)
    try:
        result = subprocess.run(["git", "apply", "--check", str(tmp_path)], capture_output=True, text=True)
        if result.returncode != 0:
            raise PatchError(f"task {patch.task_id}: git apply --check failed: {result.stderr.strip()}")
    finally:
        os.unlink(tmp_path)


def apply_patch(patch: Patch) -> None:
    """Apply the patch via git apply. Call validate_patch first."""
    tmp_path = _write_temp_patch(patch.content)
    try:
        result = subprocess.run(["git", "apply", str(tmp_path)], capture_output=True, text=True)
        if result.returncode != 0:
            raise PatchError(f"task {patch.task_id}: git apply failed: {result.stderr.strip()}")
    finally:
        os.unlink(tmp_path)


def _write_temp_patch(content: str) -> Path:
    """Write patch content to a named temp file and return its Path."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)
