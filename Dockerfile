# syntax=docker/dockerfile:1
FROM ghcr.io/huggingface/text-generation-inference:latest

# System environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    HUGGINGFACE_HUB_CACHE=/data \
    HF_HUB_ENABLE_HF_TRANSFER=1

WORKDIR /app

# Install system deps and Python (Java required for language-tool-python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    openjdk-17-jre-headless \
    python3 \
    python3-pip \
    curl \
    # Add Cloudflare apt repo and install cloudflared (official method)
    #as from docs: https://pkg.cloudflare.com/index.html#debian-any
    && mkdir -p --mode=0755 /usr/share/keyrings \
    && curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg -o /usr/share/keyrings/cloudflare-main.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' > /etc/apt/sources.list.d/cloudflared.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends cloudflared \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Copy entrypoint
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Persist model cache between restarts
VOLUME ["/data"]

# Expose only the backend API
EXPOSE 8000

# Start both TGI and the FastAPI server
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

