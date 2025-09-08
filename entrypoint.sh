#!/usr/bin/env bash
set -euo pipefail

# Defaults (overridable via env)
: "${MODEL_ID:=meta-llama/Llama-3.1-8B-Instruct}"
: "${MAX_TOTAL_TOKENS:=8192}"
: "${WAITING_SERVED_RATE:=2}"
: "${QUANTIZE:=bitsandbytes-nf4}"
: "${TGI_PORT:=80}"

# Always start TGI server in background and point backend to it locally
echo "[entrypoint] Starting TGI with model: ${MODEL_ID}"
text-generation-launcher \
  --model-id "${MODEL_ID}" \
  --max-total-tokens "${MAX_TOTAL_TOKENS}" \
  --waiting-served-rate "${WAITING_SERVED_RATE}" \
  --quantize "${QUANTIZE}" \
  --port "${TGI_PORT}" &
TGI_PID=$!

# Wait for TGI to become healthy (fail hard if not)
TGI_URL="http://127.0.0.1:${TGI_PORT}"
export TGI_BASE_URL="${TGI_URL}"
echo "[entrypoint] Waiting for TGI health at ${TGI_URL}/health ..."
for i in $(seq 1 120); do
  if curl -sf "${TGI_URL}/health" >/dev/null; then
    echo "[entrypoint] TGI is healthy."
    break
  fi
  sleep 1
  if ! kill -0 "$TGI_PID" 2>/dev/null; then
    echo "[entrypoint] TGI process exited unexpectedly." >&2
    exit 1
  fi
done

# Ensure TGI is healthy after waiting window
if ! curl -sf "${TGI_URL}/health" >/dev/null; then
  echo "[entrypoint] TGI failed to become healthy within the timeout window." >&2
  exit 1
fi

# Cloudflare Tunnel is mandatory: assert a token exists and start it
TOKEN="${CLOUDFLARED_TOKEN:-${TUNNEL_TOKEN:-}}"
: "${TOKEN:?CLOUDFLARED_TOKEN or TUNNEL_TOKEN must be set for mandatory Cloudflare Tunnel}"
echo "[entrypoint] Starting Cloudflare Tunnel (cloudflared) ..."
cloudflared --no-autoupdate tunnel run --token "${TOKEN}" &

# Start the FastAPI backend in foreground
echo "[entrypoint] Starting backend on port ${PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

