"""
Groq API client wrapper with rate limiting and structured JSON output.
"""
import json
import time
import httpx
from typing import Optional

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


async def call_groq(
    messages: list[dict],
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    json_mode: bool = True,
) -> dict | str:
    """
    Make an async call to the Groq API.
    Returns parsed JSON dict if json_mode=True, else raw string.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    GROQ_API_URL, headers=headers, json=payload
                )

                if response.status_code == 429:
                    # Rate limited — wait and retry
                    retry_after = float(
                        response.headers.get("retry-after", RETRY_DELAY * (attempt + 1))
                    )
                    await _async_sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]

                if json_mode:
                    return json.loads(content)
                return content

        except (httpx.HTTPStatusError, httpx.RequestError, json.JSONDecodeError) as e:
            if isinstance(e, httpx.HTTPStatusError):
                error_body = e.response.text
                last_error = f"{e} - Response body: {error_body}"
            else:
                last_error = e
                
            if attempt < MAX_RETRIES - 1:
                await _async_sleep(RETRY_DELAY * (attempt + 1))

    raise RuntimeError(f"Groq API call failed after {MAX_RETRIES} retries: {last_error}")


async def _async_sleep(seconds: float):
    """Async-compatible sleep."""
    import asyncio
    await asyncio.sleep(seconds)


async def validate_api_key(api_key: str) -> bool:
    """Quick validation that the API key works."""
    try:
        result = await call_groq(
            messages=[{"role": "user", "content": "Say 'ok' in JSON: {\"status\": \"ok\"}"}],
            api_key=api_key,
            max_tokens=20,
        )
        return isinstance(result, dict)
    except Exception:
        return False
