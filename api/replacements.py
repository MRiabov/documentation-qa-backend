from dataclasses import dataclass
from typing import List, Tuple

from api.app.models import Issue
from api.app.errors import MalformedToolCall
from api.app.regions import (
    forbidden_spans,
    spans_intersect,
    fenced_code_spans,
    inline_code_spans,
    url_spans,
)


@dataclass(frozen=True)
class ReplacementPlan:
    start: int
    end: int
    replacement: str
    issue_id: str


Span = Tuple[int, int]


def _intersects_any(span: Span, spans: List[Span]) -> bool:
    for s in spans:
        if spans_intersect(span, s):
            return True
    return False


def _find_allowed_occurrences(doc: str, needle: str, blocked: List[Span]) -> List[int]:
    positions: List[int] = []
    start = 0
    L = len(needle)
    while True:
        idx = doc.find(needle, start)
        if idx == -1:
            break
        span = (idx, idx + L)
        if not _intersects_any(span, blocked):
            positions.append(idx)
        start = idx + 1
    return positions


def plan_replacements(doc: str, issues: List[Issue], *, allow_code_edits: bool = False) -> List[ReplacementPlan]:
    if allow_code_edits:
        # Allow edits inside fenced code, but still block inline code and URLs
        fences = fenced_code_spans(doc)
        blocked = inline_code_spans(doc, fences) + url_spans(doc)
    else:
        blocked = forbidden_spans(doc)
    plans: List[ReplacementPlan] = []

    for issue in issues:
        needle = issue.replace_text
        positions = _find_allowed_occurrences(doc, needle, blocked)
        if len(positions) == 0:
            raise MalformedToolCall(
                f"Replacement text not found outside forbidden regions for issue '{issue.id}'."
            )
        if len(positions) > 1:
            raise MalformedToolCall(
                f"Replacement text is ambiguous (occurs {len(positions)} times) for issue '{issue.id}'."
            )
        start = positions[0]
        end = start + len(needle)
        plans.append(ReplacementPlan(start=start, end=end, replacement=issue.replace_with, issue_id=issue.id))

    # Ensure no overlapping edits
    plans_sorted = sorted(plans, key=lambda p: (p.start, p.end))
    for prev, curr in zip(plans_sorted, plans_sorted[1:]):
        if curr.start < prev.end:
            raise MalformedToolCall(
                f"Overlapping edits between issues '{prev.issue_id}' and '{curr.issue_id}'."
            )

    return plans_sorted


def apply_plans(doc: str, plans: List[ReplacementPlan]) -> str:
    if not plans:
        return doc
    parts: List[str] = []
    cursor = 0
    for p in plans:
        parts.append(doc[cursor:p.start])
        parts.append(p.replacement)
        cursor = p.end
    parts.append(doc[cursor:])
    return "".join(parts)
