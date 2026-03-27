import asyncio
import time
from datetime import datetime, timezone
from html.parser import HTMLParser

import httpx

from src.models import VideoItem

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.bilibili.com",
}

_BASE_URL = "https://api.bilibili.com/x/web-interface/search/type"


def _strip_html(text: str) -> str:
    """Remove HTML tags from a string."""
    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, d):
            self.parts.append(d)

    p = _P()
    p.feed(text)
    return "".join(p.parts).strip()


async def search_videos(
    keyword: str,
    max_results: int = 10,
    min_pubdate_ts: int = 0,   # Unix timestamp; skip videos older than this
) -> list[VideoItem]:
    """Search Bilibili for videos matching keyword, sorted by publish date."""
    collected_at = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient(headers=_HEADERS, timeout=15.0, follow_redirects=True) as client:
        # First request bilibili.com to obtain cookies (especially buvid3)
        await client.get("https://www.bilibili.com/")

        # Reuse the same client (with its cookie jar) for the search API call
        resp = await client.get(
            _BASE_URL,
            params={
                "search_type": "video",
                "keyword": keyword,
                "order": "pubdate",
                "page": 1,
                "page_size": max_results,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    results = data.get("data", {}).get("result", []) or []
    items = []
    for r in results:
        pubdate_ts = r.get("pubdate", 0)
        if min_pubdate_ts and pubdate_ts < min_pubdate_ts:
            continue

        bvid = r.get("bvid", "")
        if not bvid:
            continue

        title = _strip_html(r.get("title", ""))
        thumbnail = r.get("pic", "")
        if thumbnail.startswith("//"):
            thumbnail = "https:" + thumbnail

        tags = [t.strip() for t in r.get("tag", "").split(",") if t.strip()]
        published_at = datetime.fromtimestamp(pubdate_ts, tz=timezone.utc).isoformat() if pubdate_ts else ""

        items.append(VideoItem(
            id=bvid,
            platform="bilibili",
            url=f"https://www.bilibili.com/video/{bvid}",
            embed_url=f"https://player.bilibili.com/player.html?bvid={bvid}&autoplay=0&high_quality=1",
            title=title,
            title_ja="",        # filled by processor
            author=r.get("author", ""),
            description=r.get("description", "")[:500],
            summary_ja="",      # filled by processor
            thumbnail_url=thumbnail,
            published_at=published_at,
            collected_at=collected_at,
            relevance_score=0.0,  # filled by processor
            tags=tags,
        ))

    return items


async def collect_all_videos(keywords: list[str], max_per_keyword: int = 8) -> list[VideoItem]:
    """Search multiple keywords and deduplicate by bvid."""
    week_ago = int(time.time()) - 7 * 24 * 3600

    tasks = [search_videos(kw, max_per_keyword, week_ago) for kw in keywords]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen = set()
    videos = []
    for r in results:
        if isinstance(r, Exception):
            print(f"[bilibili] ERROR: {r}")
            continue
        for v in r:
            if v.id not in seen:
                seen.add(v.id)
                videos.append(v)

    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}] bilibili: collected {len(videos)} unique video(s)")
    return videos
