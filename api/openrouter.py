import httpx
from api.app.config import settings


class OpenRouterClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.base_url = base_url or str(settings.OPENROUTER_BASE_URL)
        self.api_key = api_key or settings.OPENROUTER_FALLBACK_KEY
        self.model = model or settings.OPENROUTER_MODEL
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                # Optional, but recommended by OpenRouter; harmless if omitted:
                # "HTTP-Referer": "",  # e.g., your site URL
                # "X-Title": "Documentation QA Backend",
            }
            self._client = httpx.AsyncClient(
                base_url=self.base_url, headers=headers, timeout=httpx.Timeout(60.0)
            )
        return self._client

    async def generate(self, prompt: str) -> str:
        # Ensure key is present only when actually using the fallback
        assert self.api_key is not None, (
            "OPENROUTER_FALLBACK_KEY is required for fallback generation"
        )
        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "max_tokens": settings.MAX_NEW_TOKENS,
            "temperature": settings.TEMPERATURE,
            "top_p": settings.TOP_P,
            "stop": settings.STOP_SEQUENCES,
            "stream": False,
        }
        resp = await client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        data = resp.json()
        # OpenAI-compatible response shape
        return data["choices"][0]["message"]["content"]

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
