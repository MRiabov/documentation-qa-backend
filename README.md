# Documentation QA Backend (LLM Wrapper over TGI)

A FastAPI backend that wraps a Hugging Face Text Generation Inference (TGI) server to review Markdown documentation for software engineers. It validates the LLM output server-side and returns a unified diff that can be safely applied.

- Accepts a JSON payload with a Markdown document.
- Prompts the model to return a strict JSON object containing proposed text replacements.
- Validates replacements in the backend: uniqueness, no edits in fenced code blocks, inline code, or URLs, and no overlapping edits.
- If valid, returns the updated document and a unified diff; otherwise, returns a `malformed_tool_call` error.
- Ships as a single Docker image that runs TGI and the backend together.

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
  "model_review": {
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

## Running as a single monolithic image (TGI + Backend)

For GPU providers that accept a single container image (no Docker-in-Docker), use the monolithic image. It starts the TGI server and the FastAPI backend in the same container.

Build:

```bash
docker build -t documentation-qa-monolith:latest .
```

Run (GPU, large shared memory recommended):

```bash
export HF_TOKEN=hf_xxx             # required to download model weights
docker run --gpus all \
  --shm-size 2g \
  -e HF_TOKEN \
  -e MODEL_ID=meta-llama/Llama-3.1-8B-Instruct \
  -e MAX_TOTAL_TOKENS=8192 \
  -e WAITING_SERVED_RATE=2 \
  -e QUANTIZE=bitsandbytes-nf4 \
  -p 8000:8000 \
  -v $(pwd)/data:/data \
  documentation-qa-monolith:latest
```

The backend will be available at `http://localhost:8000`. Internally, it talks to TGI at `http://127.0.0.1:80` as managed by the container entrypoint.

Environment variables:

- `HF_TOKEN` — Hugging Face token to pull the model.
- `MODEL_ID` — Model to serve (default `meta-llama/Llama-3.1-8B-Instruct`).
- `MAX_TOTAL_TOKENS`, `WAITING_SERVED_RATE`, `QUANTIZE` — passed to TGI.
- `HUGGINGFACE_HUB_CACHE=/data` — set in the image, mount a volume to persist downloads.

Health check:

```bash
curl -s http://localhost:8000/health | jq
```

### Additional Notes

- If your provider injects the GPU runtime automatically, you typically only need to supply the image and the environment variables above.
- Make sure to grant at least ~2 GB shared memory if using flash attention or quantized models (TGI often benefits from larger `/dev/shm`).

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

## Notes

- The backend validates the LLM output server-side to ensure deterministic edits only when safe:
  - Each `replace_text` must appear exactly once outside forbidden regions (or inside fenced code if code edits are enabled).
  - No overlapping edits.
  - Otherwise, `422 malformed_tool_call` is returned with an explanation.
- Adjust generation params in `app/config.py` or via env vars.
- Default model is controlled via the `MODEL_ID` environment variable (defaults to `meta-llama/Llama-3.1-8B-Instruct`).

### Settings of interest

- `CODE_EDIT_THRESHOLD_RATIO` — if the fraction of characters inside fenced code blocks >= this ratio (default 0.15), allow code edits.
- `ENABLE_LINTER` — enable LanguageTool linter (default true). Requires Java (already installed in Dockerfile).
- `LINTER_LANGUAGE` — LanguageTool language code (default `en-US`).

## License

MIT
