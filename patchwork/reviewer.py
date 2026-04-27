import re

from anthropic import Anthropic, APIError

from patchwork.models import Task, Patch, ReviewResult, ReviewDecision
from patchwork.tracing import traced


REVIEWER_SYSTEM_PROMPT = """\
You are a senior software engineer performing a code review on a generated diff patch.

Your job is to determine whether the patch correctly and safely implements the given task.

Review criteria:
1. Correctness: Does the patch implement exactly what the task asks for?
2. Safety: Does the patch introduce security vulnerabilities? (SQL injection, XSS, path traversal, hardcoded secrets, etc.)
3. Completeness: Does the patch leave obvious work unfinished?
4. Validity: Is the unified diff syntactically valid with proper --- +++ @@ headers?
5. Scope: Does the patch make changes beyond what the task requires?

Respond using EXACTLY this format - no deviations, no preamble, no trailing text:

DECISION: APPROVE
REASONING: <one to three sentences explaining the decision>

or:

DECISION: REJECT
REASONING: <one to three sentences explaining specifically what is wrong and must be fixed>
"""


class PatchReviewer:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for PatchReviewer")
        self._client = Anthropic(api_key=api_key)
        self._model = model

    @traced
    def review(self, patch: Patch, task: Task) -> ReviewResult:
        user_message = f"""Task description: {task.description}

Generated patch:
{patch.content}
"""
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=REVIEWER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
        except APIError as e:
            return ReviewResult(
                task_id=patch.task_id,
                decision=ReviewDecision.reject,
                reasoning=f"Reviewer API error: {e}",
            )

        raw_text = response.content[0].text
        return self._parse_response(raw_text, patch.task_id)

    def _parse_response(self, raw: str, task_id: str) -> ReviewResult:
        decision_match = re.search(r"DECISION:\s*(APPROVE|REJECT)", raw, re.IGNORECASE)
        if not decision_match:
            return ReviewResult(
                task_id=task_id,
                decision=ReviewDecision.reject,
                reasoning="Unparseable reviewer response",
            )
        decision_str = decision_match.group(1).upper()
        decision = ReviewDecision.approve if decision_str == "APPROVE" else ReviewDecision.reject
        reasoning_match = re.search(r"REASONING:\s*(.+)", raw, re.IGNORECASE | re.DOTALL)
        reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
        return ReviewResult(task_id=task_id, decision=decision, reasoning=reasoning)
