from fastapi import FastAPI, HTTPException

from .models import ReviewRequest, ReviewApplyResponse
from .prompt import build_prompt
from .tgi import TGIClient
from .parsing import parse_review_response
from .replacements import plan_replacements, apply_plans
from .diffing import unified_diff
from .errors import MalformedToolCall
from .config import settings
from .regions import fenced_code_spans, inline_code_spans, url_spans, forbidden_spans
from .linter import lint_doc

app = FastAPI(title="Documentation QA Backend", version="0.1.0")
_tgi = TGIClient()


@app.on_event("shutdown")
async def _shutdown():
    await _tgi.aclose()


@app.get("/health")
async def health():
    tgi_ok = await _tgi.health()
    return {"status": "ok", "tgi": tgi_ok, "tgi_base_url": str(settings.TGI_BASE_URL)}


@app.post("/review", response_model=ReviewApplyResponse)
async def review(req: ReviewRequest):
    # Decide whether to allow code edits based on fenced-code density
    fences = fenced_code_spans(req.doc)
    code_ratio = (sum(e - s for s, e in fences) / len(req.doc)) if req.doc else 0.0
    allow_code_edits = code_ratio >= settings.CODE_EDIT_THRESHOLD_RATIO

    # Lint document using LanguageTool
    lint_issues = []
    if settings.ENABLE_LINTER:
        lint_issues = lint_doc(req.doc, settings.LINTER_LANGUAGE)

    # Precompute blocked spans depending on code policy
    if allow_code_edits:
        blocked = inline_code_spans(req.doc, fences) + url_spans(req.doc)
    else:
        blocked = forbidden_spans(req.doc)

    def find_allowed_occurrences(needle: str) -> list[int]:
        positions: list[int] = []
        start = 0
        L = len(needle)
        while True:
            idx = req.doc.find(needle, start)
            if idx == -1:
                break
            span = (idx, idx + L)
            if not any(span[0] < b[1] and b[0] < span[1] for b in blocked):
                positions.append(idx)
            start = idx + 1
        return positions

    # Build lint spans for duplicate filtering
    lint_spans = [(li.start, li.end) for li in lint_issues]

    attempts = settings.RETRIES_ON_MALFORMED + 1
    feedback: str | None = None
    last_error: str | None = None
    for _ in range(attempts):
        try:
            prompt = build_prompt(
                req.doc,
                feedback=feedback,
                allow_code_edits=allow_code_edits,
                lint_issues=[li.model_dump() for li in lint_issues] if lint_issues else None,
            )
            raw = await _tgi.generate(prompt)
            review = parse_review_response(raw)

            # Filter out model issues that duplicate linter spans when uniquely locatable
            filtered_issues = []
            for issue in review.issues:
                positions = find_allowed_occurrences(issue.replace_text)
                if len(positions) == 1:
                    s = positions[0]
                    span = (s, s + len(issue.replace_text))
                    if any(span[0] < ls[1] and ls[0] < span[1] for ls in lint_spans):
                        # skip duplicate of linter
                        continue
                filtered_issues.append(issue)

            review.issues = filtered_issues

            plans = plan_replacements(
                req.doc,
                review.issues,
                allow_code_edits=allow_code_edits,
            )
            updated = apply_plans(req.doc, plans)
            diff = unified_diff(req.doc, updated)
            return ReviewApplyResponse(
                version=review.version,
                diff=diff,
                updated_doc=updated,
                model_review=review,
                lint_issues=lint_issues,
            )
        except MalformedToolCall as e:
            last_error = e.reason
            feedback = e.reason
            continue

    raise HTTPException(status_code=422, detail={"error": "malformed_tool_call", "reason": last_error or "unknown"})
