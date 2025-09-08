# Documentation QA Backend (LLM Wrapper over TGI)

A FastAPI backend that wraps a Hugging Face Text Generation Inference (TGI) server to review Markdown documentation for software engineers. It validates the LLM output server-side and returns a unified diff that can be safely applied.

- Accepts a JSON payload with a Markdown document.
- Prompts the model to return a strict JSON object containing proposed text replacements.
- Validates replacements in the backend: uniqueness, no edits in fenced code blocks, inline code, or URLs, and no overlapping edits.
- If valid, returns the updated document and a unified diff; otherwise, returns a `malformed_tool_call` error.
- Ships with Docker and Docker Compose to run alongside TGI.

## Architecture

- `app/main.py` — FastAPI app with `/review` and `/health`.
- `app/prompt.py` — Builds the instruction prompt sent to TGI.
- `app/tgi.py` — Async HTTP client for TGI `/generate` and `/health`.
- `app/parsing.py` — Extracts `<json>…</json>` and validates schema (Pydantic v2).
- `app/regions.py` — Detects regions: fenced code blocks, inline code, URLs.
- `app/replacements.py` — Plans/apply deterministic replacements with ambiguity/overlap checks.
- `app/diffing.py` — Unified diff generation.
- `app/models.py` — Pydantic models for request/response and schema the model must follow.
- `app/config.py` — Settings via environment variables.
- `app/linter.py` — LanguageTool-based grammatical/punctuation linter.

## API

- `GET /health` — returns `{ status, tgi, tgi_base_url }` where `tgi` indicates connectivity.
- `POST /review` — body:

```json
{
  "doc": "# My README...\n..."
}
```

On success (200):

```json
{
  "version": "1.0",
  "diff": "--- doc_before.md\n+++ doc_after.md\n@@ ...",
  "updated_doc": "# My README... (updated)",
  "llm_review": {
    "version": "1.0",
    "issues": [
      {
        "id": "abc123",
        "rule": "concise-wording",
        "message": "Prefer 'use' over 'utilize'",
        "severity": "warning",
        "replace_text": "utilize",
        "replace_with": "use"
      }
    ]
  },
  "lint_issues": [
    {
      "id": "UPPERCASE_SENTENCE_START:0",
      "rule": "UPPERCASE_SENTENCE_START",
      "message": "This sentence does not start with an uppercase letter.",
      "severity": "warning",
      "start": 0,
      "end": 5
    }
  ]
}
```

On error (422):

```json
{
  "detail": {
    "error": "malformed_tool_call",
    "reason": "Replacement text is ambiguous (occurs 2 times) for issue 'abc123'."
  }
}
```

## Prompt Contract (what the model sees)

The backend sends a system-style instruction asking for a JSON-only response within `<json>…</json>` matching:

```ts
type Severity = "info" | "warning" | "error";
type Issue = {
  id: string;
  rule: string;
  message: string;
  severity: Severity;
  replace_text: string;
  replace_with: string;
  replacement?: string;
  replacements?: { label: string; text: string }[];
};

type ReviewResponse = { version: string; issues: Issue[] };
```

Code-edit policy: if the document contains a significant proportion of fenced code (configurable), the model may edit code blocks to add concise comments, fix formatting, and add code-fence language labels (e.g., ```py). Inline code and URLs remain off-limits. The model is instructed not to duplicate issues already reported by the linter. The backend also filters duplicates by span.

## Running with Docker Compose (two services)

Prerequisites: Docker and docker-compose.

1. Export your HF token (required to download the model weights):

```bash
export HF_TOKEN=hf_xxx
```

1. Start TGI + backend:

```bash
docker compose up --build
```

- Backend is exposed at `http://localhost:8000`.
- TGI is available to the backend at `http://tgi:80` inside the compose network.

1. Health check:

```bash
curl -s http://localhost:8000/health | jq
```

1. Run a review:

```bash
curl -s http://localhost:8000/review \
  -H 'Content-Type: application/json' \
  -d '{"doc": "Use this to utilize the API.```\ncode\n``` Do not just simply overcomplicate."}' | jq
```

## Local Dev (without Docker)

Python 3.11 recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You still need a running TGI server. Example (GPU assumed; see TGI docs for CPU or vLLM):

```bash
export HF_TOKEN=hf_xxx
MODEL_ID=meta-llama/Llama-3.1-8B-Instruct
# Warning: downloads multiple GB of weights
docker run --gpus all --shm-size 2g -e HF_TOKEN -p 8080:80 \
  -v $(pwd)/data:/data ghcr.io/huggingface/text-generation-inference:3.3.5 \
  --model-id $MODEL_ID
```

Then set the backend to talk to your local TGI:

```bash
export TGI_BASE_URL=http://localhost:8080
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Deploy to Vercel (Python-only)

- Prerequisites: Vercel account and the Vercel CLI installed (`npm i -g vercel`).
- Files included for Vercel:
  - `api/index.py` — imports `app` from `app.main` for ASGI.
  - `vercel.json` — configures the Python runtime and routes all paths to `api/index.py`. It also disables the LanguageTool linter on Vercel, where Java is not available by default.

- Configure environment variables (Dashboard or CLI):
  - `ENABLE_LINTER=false` — already set in `vercel.json` for Vercel.
  - `TGI_BASE_URL=<https URL of your ML inference>` — optional until you bring ML online. Without a reachable TGI, `/review` will return an error; `/health` will show `tgi: false`.

- Deploy:

  ```bash
  vercel login
  vercel link
  vercel deploy --prod
  ```

- Local dev via Vercel:

  ```bash
  vercel dev
  ```

  This uses the `devCommand` in `vercel.json` to run `uvicorn` on port 3000.

- Notes and limits on Vercel Serverless:
  - No long-running background processes (e.g., autossh daemons) inside serverless functions.
  - Cold starts and execution timeouts apply; long TGI generations may time out on free plans.
  - For private ML backends, prefer exposing HTTPS with auth or a managed reverse tunnel. Persistent SSH tunnels are not supported in serverless.

- Future “autossh” plan:
  - If you need a tunnel, run it on the ML host (initiated from the ML side), not on Vercel. Then set `TGI_BASE_URL` to the public endpoint exposed by that tunnel.

## Notes

- The backend validates the LLM output server-side to ensure deterministic edits only when safe:
  - Each `replace_text` must appear exactly once outside forbidden regions (or inside fenced code if code edits are enabled).
  - No overlapping edits.
  - Otherwise, `422 malformed_tool_call` is returned with an explanation.
- Adjust generation params in `app/config.py` or via env vars.
- Default model is controlled via the `MODEL_ID` environment variable (defaults to `meta-llama/Llama-3.1-8B-Instruct`).
- When in dev, don't forget to `source .env`.

### Settings of interest

- `CODE_EDIT_THRESHOLD_RATIO` — if the fraction of characters inside fenced code blocks >= this ratio (default 0.15), allow code edits.
- `ENABLE_LINTER` — enable LanguageTool linter (default true). Requires Java (already installed in Dockerfile).
- `LINTER_LANGUAGE` — LanguageTool language code (default `en-US`).

## License

MIT
