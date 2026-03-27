"""Generate the executive summary using the LLM."""
from __future__ import annotations

import json
from typing import Callable, Awaitable


async def generate_executive_summary(
    articles: list,
    llm_call_fn: Callable[..., Awaitable[str]],
) -> list[str]:
    """Return exactly 3 Japanese bullet strings summarising the week's top ADAS news.

    Args:
        articles: Up to 10 ProcessedArticle dicts (or objects with __dict__),
                  already filtered to the most relevant items.
        llm_call_fn: The ``llm_call`` coroutine from ``src.processor.llm``.
                     Signature: ``async llm_call(messages, ...) -> str``

    Returns:
        A list of exactly 3 Japanese strings (each ~30 characters).
    """
    # Normalise to plain dicts
    dicts = [a if isinstance(a, dict) else a.__dict__ for a in articles]

    # Build a compact digest for the prompt
    digest_lines = []
    for i, a in enumerate(dicts, 1):
        title = a.get("title_ja") or a.get("title", "")
        summary = a.get("summary_ja") or a.get("summary_zh", "")
        score = a.get("relevance_score", 0)
        digest_lines.append(f"{i}. [{score:.1f}] {title} — {summary}")

    digest = "\n".join(digest_lines)

    system_prompt = (
        "あなたは中国の自動運転（ADAS）業界を専門とするアナリストです。"
        "日本の自動車メーカー向けに、今週の中国ADAS動向を簡潔にまとめてください。"
    )

    user_prompt = f"""以下は今週の中国ADAS関連記事（関連スコア順）です。

{digest}

これらの記事を踏まえ、今週の最も重要なADAS動向を**正確に3点**、日本語の箇条書きで要約してください。

要件:
- 各ポイントは約30文字以内
- 具体的な企業名・技術名・数値を含める
- 抽象的な表現を避け、事実ベースで記述する
- 回答はJSON配列のみ（余分なテキスト不要）: ["ポイント1", "ポイント2", "ポイント3"]"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    raw = await llm_call_fn(system=system_prompt, user=user_prompt)

    # Parse the JSON array from the response
    bullets = _parse_bullets(raw)
    return bullets


def _parse_bullets(raw: str) -> list[str]:
    """Extract a 3-element list from the LLM response, with fallback."""
    raw = raw.strip()

    # Try direct JSON parse first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) >= 3:
            return [str(s) for s in parsed[:3]]
    except json.JSONDecodeError:
        pass

    # Try to find a JSON array embedded in the text
    start = raw.find("[")
    end = raw.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw[start : end + 1])
            if isinstance(parsed, list) and len(parsed) >= 3:
                return [str(s) for s in parsed[:3]]
        except json.JSONDecodeError:
            pass

    # Last resort: split by newlines and take first 3 non-empty lines
    lines = [ln.lstrip("-・•▸ ").strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) >= 3:
        return lines[:3]

    # Pad with placeholder if we couldn't extract 3 bullets
    while len(lines) < 3:
        lines.append("今週の動向を確認中…")
    return lines[:3]
