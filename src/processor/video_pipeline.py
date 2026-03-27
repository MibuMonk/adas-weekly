from __future__ import annotations
import asyncio
import json
from datetime import datetime, timezone

from src.models import VideoItem
from src.processor.llm import llm_call

_SYSTEM = """\
あなたは中国の自動車・ADAS業界の専門アナリストです。
以下のBilibili動画情報（中国語）を分析し、JSONで回答してください。

判定基準 - ADAS関連度スコア(0-10):
- 10: ADAS/自動運転の核心技術デモ・発表動画
- 7-9: 主要OEM/Tier1のADAS関連レビュー・ニュース
- 4-6: 自動車業界周辺（EV、デザイン等）
- 0-3: ADAS無関係

信頼性スコア(0-10)の判定基準:
- 10: OEM/Tier1公式発表・プレスリリース
- 7-9: 主要自動車メディア（盖世汽車、36氪等）
- 4-6: 自動車評価系YouTuber/Biliビリ投稿者
- 1-3: 未確認の噂・個人の憶測

必ずこのJSON形式で回答:
{
  "relevance_score": 8.5,
  "credibility_score": 6.0,
  "title_ja": "日本語タイトル",
  "summary_ja": "2文の日本語要約",
  "tags": ["NOA", "比亚迪"]
}\
"""

_THRESHOLD = 4.0


async def process_video(video: VideoItem) -> VideoItem | None:
    user_msg = f"タイトル: {video.title}\n投稿者: {video.author}\n説明: {video.description}"
    raw = await llm_call(system=_SYSTEM, user=user_msg, max_tokens=400)

    # Strip ```json ... ``` fences, then stack-based JSON extraction
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end]).strip()
    start = text.find("{")
    parsed = None
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    break

    if not parsed:
        return None

    score = float(parsed.get("relevance_score", 0))
    if score < _THRESHOLD:
        return None

    video.relevance_score = score
    video.credibility_score = float(parsed.get("credibility_score", 5.0))
    video.title_ja = parsed.get("title_ja", video.title)
    video.summary_ja = parsed.get("summary_ja", "")
    video.tags = parsed.get("tags", video.tags)
    return video


async def process_all_videos(videos: list[VideoItem], max_concurrent: int = 5) -> list[VideoItem]:
    sem = asyncio.Semaphore(max_concurrent)
    results = []

    async def _run(v, i):
        async with sem:
            out = await process_video(v)
            status = f"score={out.relevance_score:.1f}" if out else "filtered"
            print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] video: [{i}/{len(videos)}] {v.author} — '{v.title[:40]}' ({status})")
            return out

    tasks = [_run(v, i + 1) for i, v in enumerate(videos)]
    for r in await asyncio.gather(*tasks):
        if r is not None:
            results.append(r)

    results.sort(key=lambda v: v.relevance_score, reverse=True)
    return results
