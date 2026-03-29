from __future__ import annotations

import json
from typing import Optional

from src.models import Article, ProcessedArticle
from src.processor.llm import llm_call

_SYSTEM_PROMPT = """\
あなたは中国の自動車・ADAS業界を担当する日本人ビジネス記者です。
以下の中国語記事を分析し、JSONで回答してください。

判定基準 - ADAS関連度スコア(0-10):
- 10: ADAS/自動運転の核心技術、製品発表
- 7-9: 主要OEM/Tier1のADAS関連ニュース
- 4-6: 自動車業界の周辺ニュース（EV、サプライチェーン）
- 0-3: ADAS無関係

【日本語品質基準】日経新聞・日経Automotiveのビジネス記者として書いてください。
- title_ja: 体言止めを基本とし、簡潔で情報密度の高い見出しにする（例:「〇〇、都市部NOA機能を正式リリース」）
- summary_ja: 翻訳調を避け、編集済みの日本語として自然に読めるよう書く。能動態・簡潔な文体を優先し、中国語の文章構造をそのまま写さない
- 専門用語: 自動運転、ADAS、NOA、OTA など業界標準の日本語表記を使用する。中国語固有名詞はカタカナ転写せず、一般的な日本語訳か英語表記を当てる（例: 华为→ファーウェイ、比亚迪→BYD）
- 読者想定: 日本の自動車業界関係者（HQ）。機械翻訳と気づかれないレベルの自然さを必須とする

重要：JSON文字列内でASCII二重引用符（"）を使用しないでください。中国語の引用には「」を使用してください。

必ずこのJSON形式のみで回答（前後に余分なテキスト不要）:
{
  "relevance_score": 8.5,
  "summary_zh": "2-3文の中国語要約",
  "title_ja": "日本語タイトル",
  "summary_ja": "2-3文の日本語要約",
  "tags": ["NOA", "比亚迪"],
  "company_mentions": ["比亚迪", "华为"]
}\
"""

_RELEVANCE_THRESHOLD = 3.0


def _strip_code_fence(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrapper if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json / ```) and last line (```)
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        return "\n".join(lines[start:end]).strip()
    return text


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from a string, tolerating surrounding prose."""
    text = _strip_code_fence(text.strip())
    # Try direct parse first.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Stack-based brace matching — handles nested objects correctly.
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"No JSON object found in LLM response: {text!r}")


async def process_article(
    article: Article,
    client_kwargs: dict,  # reserved for future per-call overrides; unused currently
) -> Optional[ProcessedArticle]:
    """Analyze a single article with one LLM call.

    Returns a ProcessedArticle if the article is ADAS-relevant (score >= 3.0),
    or None if it should be filtered out.

    Args:
        article: The raw collected article.
        client_kwargs: Reserved for future use (e.g. model overrides).
    """
    user_message = f"タイトル: {article.title}\n\n本文:\n{article.content}"

    raw_response = await llm_call(
        system=_SYSTEM_PROMPT,
        user=user_message,
        max_tokens=1000,
    )

    parsed = _extract_json(raw_response)

    relevance_score = float(parsed.get("relevance_score", 0.0))
    if relevance_score < _RELEVANCE_THRESHOLD:
        return None

    return ProcessedArticle(
        id=article.id,
        url=article.url,
        source=article.source,
        title=article.title,
        content=article.content,
        published_at=article.published_at,
        collected_at=article.collected_at,
        relevance_score=relevance_score,
        summary_zh=parsed.get("summary_zh", ""),
        title_ja=parsed.get("title_ja", ""),
        summary_ja=parsed.get("summary_ja", ""),
        tags=parsed.get("tags", []),
        company_mentions=parsed.get("company_mentions", []),
    )
