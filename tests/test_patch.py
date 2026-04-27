import os
import pytest
from unittest.mock import patch, MagicMock, call

from patchwork.models import Patch
from patchwork.patch import validate_patch, apply_patch, PatchError, _write_temp_patch


VALID_PATCH = Patch(
    task_id="task-001",
    content="--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n",
    backend="claude",
)


def test_validate_empty_content_raises():
    empty_patch = Patch(task_id="task-001", content="", backend="claude")
    with patch("subprocess.run") as mock_run:
        with pytest.raises(PatchError):
            validate_patch(empty_patch)
    mock_run.assert_not_called()


def test_validate_whitespace_content_raises():
    empty_patch = Patch(task_id="task-001", content="  \n\t", backend="claude")
    with patch("subprocess.run") as mock_run:
        with pytest.raises(PatchError):
            validate_patch(empty_patch)
    mock_run.assert_not_called()


def test_validate_calls_git_apply_check():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        validate_patch(VALID_PATCH)
    args = mock_run.call_args[0][0]
    assert "git" in args
    assert "--check" in args


def test_validate_raises_on_nonzero_exit():
    mock_result = MagicMock(returncode=1, stderr="bad patch")
    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(PatchError, match="bad patch"):
            validate_patch(VALID_PATCH)


def test_apply_calls_git_apply_no_check():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        apply_patch(VALID_PATCH)
    args = mock_run.call_args[0][0]
    assert args[0:2] == ["git", "apply"]
    assert "--check" not in args


def test_apply_raises_on_failure():
    mock_result = MagicMock(returncode=1, stderr="bad patch")
    with patch("subprocess.run", return_value=mock_result):
        with pytest.raises(PatchError):
            apply_patch(VALID_PATCH)


def test_tempfile_deleted_on_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result), patch("os.unlink") as mock_unlink:
        validate_patch(VALID_PATCH)
    mock_unlink.assert_called_once()


def test_tempfile_deleted_on_failure():
    mock_result = MagicMock(returncode=1, stderr="bad patch")
    with patch("subprocess.run", return_value=mock_result), patch("os.unlink") as mock_unlink:
        with pytest.raises(PatchError):
            validate_patch(VALID_PATCH)
    mock_unlink.assert_called_once()
