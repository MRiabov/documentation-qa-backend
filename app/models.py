from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class ReplacementOption(BaseModel):
    label: str
    text: str


class Issue(BaseModel):
    id: str
    rule: str
    message: str
    severity: Severity

    # Deterministic replacement contract
    replace_text: str = Field(..., description="Exact text to find in the document")
    replace_with: str = Field(..., description="Exact text to replace with")

    # Optional fields the model may include
    replacement: Optional[str] = None
    replacements: Optional[List[ReplacementOption]] = None


class ReviewResponse(BaseModel):
    version: str
    issues: List[Issue]


class ReviewRequest(BaseModel):
    doc: str


class LintIssue(BaseModel):
    id: str
    rule: str
    message: str
    severity: Severity
    start: int
    end: int


class ReviewApplyResponse(BaseModel):
    version: str
    diff: str
    updated_doc: str
    model_review: ReviewResponse
    lint_issues: List[LintIssue]
