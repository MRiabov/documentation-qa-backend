from __future__ import annotations

from typing import List

from proselint.tools import lint as proselint_lint

from api.models import LintIssue, Severity


def _to_severity(sev: str) -> Severity:
    s = (sev or "").lower()
    if s == "error":
        return Severity.error
    if s == "warning":
        return Severity.warning
    # proselint may return "suggestion"; map to info by default
    return Severity.info


def lint_doc(doc: str, language: str) -> List[LintIssue]:
    # proselint supports English; enforce expected locale
    assert language.lower().startswith("en"), "proselint supports English only"

    suggestions = proselint_lint(doc)
    issues: List[LintIssue] = []
    for s in suggestions:
        # Tuple format: (check, message, line, column, start, end, extent, severity, replacements)
        check, message, _line, _col, start, end, _extent, severity, _repls = s
        # Ensure indices are within the document bounds
        assert 0 <= start <= end <= len(doc)
        issues.append(
            LintIssue(
                id=f"{check}:{start}",
                rule=check,
                message=message,
                severity=_to_severity(severity),
                start=start,
                end=end,
            )
        )
    return issues
