from __future__ import annotations

import asyncio
import os
from functools import partial

from openai import OpenAI

_BASE_URL = "https://llm-gateway.momenta.works/v1"
_DEFAULT_MODEL = "claude-sonnet-4-6"


def _get_client() -> OpenAI:
    api_key = os.environ.get("LLM_API_KEY", "")
    return OpenAI(api_key=api_key, base_url=_BASE_URL)


async def llm_call(system: str, user: str, max_tokens: int = 1000) -> str:
    """Make a single LLM chat completion call.

    Runs the synchronous OpenAI client in a thread-pool executor so it does
    not block the event loop.

    Args:
        system: System prompt text.
        user: User message text.
        max_tokens: Maximum tokens in the completion response.

    Returns:
        The assistant message content as a string.
    """
    model = os.environ.get("LLM_MODEL", _DEFAULT_MODEL)
    client = _get_client()

    def _sync_call() -> str:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content or ""

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_call)
