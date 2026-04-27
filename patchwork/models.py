from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"


class Task(BaseModel):
    id: str
    description: str
    backend: str | None = None
    status: TaskStatus = TaskStatus.pending
    rejection_reason: str | None = None


class Patch(BaseModel):
    task_id: str
    content: str
    backend: str


class ReviewDecision(str, Enum):
    approve = "approve"
    reject = "reject"


class ReviewResult(BaseModel):
    task_id: str
    decision: ReviewDecision
    reasoning: str


class Plan(BaseModel):
    slug: str
    feature: str
    tasks: list[Task]
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug, max 60 characters."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = text.strip()
    text = re.sub(r"\s+", "-", text)
    return text[:60]
