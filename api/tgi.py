import httpx
from api.config import settings


class TGIClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or str(settings.TGI_BASE_URL)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=httpx.Timeout(60.0)
            )
        return self._client

    async def health(self) -> bool:
        client = await self._get_client()
        try:
            resp = await client.get("/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def generate(self, prompt: str) -> str:
        client = await self._get_client()
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": settings.MAX_NEW_TOKENS,
                "temperature": settings.TEMPERATURE,
                "top_p": settings.TOP_P,
                # TGI usually supports 'stop' parameter for stop sequences
                "stop": settings.STOP_SEQUENCES,
            },
        }
        resp = await client.post("/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Non-streaming generate returns single JSON containing 'generated_text'
        if isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"]
        # Some TGI variants return a list with one item
        if (
            isinstance(data, list)
            and data
            and isinstance(data[0], dict)
            and "generated_text" in data[0]
        ):
            return data[0]["generated_text"]
        # Fallback: return the whole string representation
        return str(data)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
