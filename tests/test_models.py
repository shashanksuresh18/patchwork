import pytest
from datetime import timezone

from patchwork.models import (
    Task, Patch, Plan, ReviewResult, ReviewDecision, TaskStatus, slugify
)


def test_task_default_status():
    task = Task(id="task-001", description="do something")
    assert task.status == TaskStatus.pending
    assert task.backend is None


def test_task_status_can_be_set():
    task = Task(id="task-001", description="do something")
    task.status = TaskStatus.approved
    assert task.status == TaskStatus.approved


def test_task_rejection_reason_defaults_none():
    task = Task(id="task-001", description="do something")
    assert task.rejection_reason is None


def test_patch_roundtrip():
    patch = Patch(task_id="task-001", content="--- a/foo.py\n+++ b/foo.py\n", backend="claude")
    assert Patch.model_validate_json(patch.model_dump_json()) == patch


def test_plan_roundtrip():
    plan = Plan(
        slug="add-user-auth",
        feature="Add user auth",
        tasks=[Task(id="task-001", description="do something")],
    )
    assert Plan.model_validate_json(plan.model_dump_json()) == plan


def test_plan_slug_set_by_caller():
    plan = Plan(
        slug="custom-slug",
        feature="Add user auth",
        tasks=[Task(id="task-001", description="do something")],
    )
    assert plan.slug == "custom-slug"


def test_plan_created_at_utc():
    plan = Plan(
        slug="add-user-auth",
        feature="Add user auth",
        tasks=[Task(id="task-001", description="do something")],
    )
    assert plan.created_at.tzinfo is not None


def test_review_result_approve():
    result = ReviewResult(
        task_id="task-001",
        decision=ReviewDecision.approve,
        reasoning="Looks good",
    )
    assert ReviewResult.model_validate_json(result.model_dump_json()) == result


def test_review_result_reject():
    result = ReviewResult(
        task_id="task-001",
        decision=ReviewDecision.reject,
        reasoning="Needs work",
    )
    assert ReviewResult.model_validate_json(result.model_dump_json()) == result


def test_slugify_basic():
    assert slugify("Add user auth") == "add-user-auth"


def test_slugify_special_chars():
    assert slugify("Add /api/v2 endpoint!") == "add-api-v2-endpoint"


def test_slugify_truncates():
    assert len(slugify("a" * 100)) <= 60


def test_slugify_empty():
    assert slugify("") == ""


def test_slugify_only_specials():
    assert slugify("!!!") == ""
