from __future__ import annotations

from functools import lru_cache
from typing import List

import language_tool_python as lt

from api.models import LintIssue, Severity


@lru_cache(maxsize=1)
def _get_tool(lang: str) -> lt.LanguageTool:
    return lt.LanguageTool(lang)


def _to_severity(issue_type: str) -> Severity:
    t = (issue_type or "").lower()
    if "misspelling" in t or "typographical" in t:
        return Severity.warning
    if "grammar" in t:
        return Severity.error
    if "punctuation" in t:
        return Severity.warning
    return Severity.info


def lint_doc(doc: str, language: str) -> List[LintIssue]:
    tool = _get_tool(language)
    matches = tool.check(doc)
    issues: List[LintIssue] = []
    for m in matches:
        start = m.offset
        end = m.offset + m.errorLength
        # Ensure indices are sensible; rely on language-tool offsets being correct
        if start < 0 or end < 0 or end < start or end > len(doc):
            continue
        issues.append(
            LintIssue(
                id=f"{m.ruleId}:{start}",
                rule=m.ruleId,
                message=m.message,
                severity=_to_severity(getattr(m, "ruleIssueType", "")),
                start=start,
                end=end,
            )
        )
    return issues
