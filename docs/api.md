# Documentation QA Backend — API Specification (v0.1.0)

This document describes the REST API provided by the backend in `app/main.py`. Models are defined in `app/models.py`.

- Framework: FastAPI
- Content type: `application/json`
- Authentication: None
- Errors: JSON body; standard HTTP status codes

Useful links when the server is running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI schema: http://localhost:8000/openapi.json

## Base URL

- Local development: `http://localhost:8000`

## Endpoints

### GET /health

Checks service health and connectivity to the TGI model backend.

- Response 200 OK
  - Body:
    - `status`: "ok"
    - `tgi`: boolean (true if TGI responds 200 to `/health`)
    - `tgi_base_url`: string (configured TGI base URL)

Example request:

```bash
curl -s http://localhost:8000/health
```

Example response:

```json
{
  "status": "ok",
  "tgi": true,
  "tgi_base_url": "http://tgi:80"
}
```

---

### POST /review

Runs a documentation review over a provided document string, returning:
- A unified diff of suggested changes
- The updated document
- The structured model review details
- Lint issues from the built-in linter

- Request body: `ReviewRequest`
- Response 200 OK: `ReviewApplyResponse`
- Error 422 Unprocessable Entity: malformed tool output (see example below)
- Error 500 Internal Server Error: upstream TGI error or unexpected failure

Example request:

```bash
curl -s -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "doc": "This is teh example with a url http://example.com and a code block ```py\nprint( 1 )\n```"
  }'
```

Example success response (truncated):

```json
{
  "version": "x.y.z",
  "diff": "--- original\n+++ updated\n@@\n-This is teh example\n+This is the example\n",
  "updated_doc": "This is the example with a url http://example.com and a code block ```py\nprint(1)\n```",
  "model_review": {
    "version": "x.y.z",
    "issues": [
      {
        "id": "spelling_teh",
        "rule": "spelling",
        "message": "Fix 'teh' to 'the'",
        "severity": "warning",
        "replace_text": "teh",
        "replace_with": "the",
        "replacement": null,
        "replacements": null
      }
    ]
  },
  "lint_issues": [
    {
      "id": "LT123",
      "rule": "WHITESPACE_RULE",
      "message": "Unnecessary whitespace",
      "severity": "info",
      "start": 42,
      "end": 43
    }
  ]
}
```

Example error response (422):

```json
{
  "detail": {
    "error": "malformed_tool_call",
    "reason": "explanation of why the model output could not be applied"
  }
}
```

## Data Models

All types adhere to Pydantic models in `app/models.py`.

### Severity (enum)
- `"info" | "warning" | "error"`

### ReplacementOption
- `label`: string
- `text`: string

### Issue
- `id`: string
- `rule`: string
- `message`: string
- `severity`: `Severity`
- `replace_text`: string (exact text to find in the document)
- `replace_with`: string (exact text to replace with)
- `replacement`: string | null (optional)
- `replacements`: `ReplacementOption[]` | null (optional)

### ReviewResponse
- `version`: string
- `issues`: `Issue[]`

### ReviewRequest
- `doc`: string

### LintIssue
- `id`: string
- `rule`: string
- `message`: string
- `severity`: `Severity`
- `start`: number (character index in original doc)
- `end`: number (character index in original doc)

### ReviewApplyResponse
- `version`: string
- `diff`: string (unified diff between original and updated)
- `updated_doc`: string
- `model_review`: `ReviewResponse`
- `lint_issues`: `LintIssue[]`

## Frontend Integration Notes

- The service returns both AI model suggestions and linter findings:
  - `model_review.issues`: issues from the model with deterministic replacements (`replace_text` -> `replace_with`).
  - `lint_issues`: issues from the linter (LanguageTool), already applied/considered during generation and for duplicate filtering.
- The backend filters model issues that duplicate linter findings when they can be uniquely located.
- The unified `diff` is standard unified diff text; display as-is or compute patches client-side.
- `updated_doc` is the original document with all accepted deterministic replacements applied.
- No pagination; process is per-document.
- Latency depends on model inference (TGI). The service uses a 60s upstream HTTP timeout to TGI.

## Example Usage (JavaScript)

Fetch health:

```ts
async function checkHealth() {
  const res = await fetch("http://localhost:8000/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}
```

Submit document for review:

```ts
type Severity = "info" | "warning" | "error";

type ReplacementOption = {
  label: string;
  text: string;
};

type Issue = {
  id: string;
  rule: string;
  message: string;
  severity: Severity;
  replace_text: string;
  replace_with: string;
  replacement?: string | null;
  replacements?: ReplacementOption[] | null;
};

type ReviewResponse = {
  version: string;
  issues: Issue[];
};

type LintIssue = {
  id: string;
  rule: string;
  message: string;
  severity: Severity;
  start: number;
  end: number;
};

type ReviewApplyResponse = {
  version: string;
  diff: string;
  updated_doc: string;
  model_review: ReviewResponse;
  lint_issues: LintIssue[];
};

async function reviewDoc(doc: string): Promise<ReviewApplyResponse> {
  const res = await fetch("http://localhost:8000/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc }),
  });
  if (res.status === 422) {
    const body = await res.json();
    throw new Error(`Malformed tool call: ${body.detail?.reason ?? "unknown"}`);
  }
  if (!res.ok) {
    throw new Error(`Server error: ${res.status}`);
  }
  return res.json();
}
```

## Configuration

Configuration is defined in `app/config.py` and can be overridden via environment variables (`.env` file is supported):

- `TGI_BASE_URL`: Base URL to TGI, e.g., `http://tgi:80` (default when using docker-compose)
- `MAX_NEW_TOKENS`, `TEMPERATURE`, `TOP_P`, `STOP_SEQUENCES`: Generation parameters
- `RETRIES_ON_MALFORMED`: Number of extra attempts when model output is malformed
- `CODE_EDIT_THRESHOLD_RATIO`: If fraction of characters in fenced code >= threshold, code edits are allowed
- `ENABLE_LINTER`, `LINTER_LANGUAGE`: Linter toggles
- `HOST`, `PORT`: Server bind (defaults `0.0.0.0:8000`)

## Changelog

- v0.1.0: Initial API
