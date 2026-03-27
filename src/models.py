from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Article:
    id: str              # sha256[:8] of URL
    url: str
    source: str          # source name, e.g. "智驾网"
    title: str           # Chinese title
    content: str         # Chinese content (up to 2000 chars)
    published_at: str    # ISO datetime string or empty
    collected_at: str    # ISO datetime string

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Article:
        return cls(
            id=d["id"],
            url=d["url"],
            source=d["source"],
            title=d["title"],
            content=d["content"],
            published_at=d["published_at"],
            collected_at=d["collected_at"],
        )


@dataclass
class ProcessedArticle:
    id: str
    url: str
    source: str
    title: str
    content: str
    published_at: str
    collected_at: str
    relevance_score: float = 0.0      # 0-10, ADAS relevance
    credibility_score: float = 0.0    # 0-10, source credibility
    summary_zh: str = ""              # Chinese 2-3 sentence summary
    title_ja: str = ""           # Japanese title
    summary_ja: str = ""         # Japanese 2-3 sentence summary
    tags: list = field(default_factory=list)            # e.g. ["NOA", "比亚迪", "城市智驾"]
    company_mentions: list = field(default_factory=list)  # company names mentioned

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProcessedArticle:
        return cls(
            id=d["id"],
            url=d["url"],
            source=d["source"],
            title=d["title"],
            content=d["content"],
            published_at=d["published_at"],
            collected_at=d["collected_at"],
            relevance_score=d["relevance_score"],
            summary_zh=d["summary_zh"],
            title_ja=d["title_ja"],
            summary_ja=d["summary_ja"],
            tags=d.get("tags", []),
            company_mentions=d.get("company_mentions", []),
        )


@dataclass
class VideoItem:
    id: str            # bvid (e.g. "BV1xx411c7mD")
    platform: str      # "bilibili"
    url: str           # https://www.bilibili.com/video/{bvid}
    embed_url: str     # https://player.bilibili.com/player.html?bvid={bvid}&autoplay=0
    title: str         # original Chinese title
    title_ja: str      # Japanese translated title (filled by processor)
    author: str        # channel/uploader name
    description: str   # video description (up to 500 chars)
    summary_ja: str    # Japanese summary (filled by processor)
    thumbnail_url: str # cover image URL
    published_at: str  # ISO datetime
    collected_at: str  # ISO datetime
    relevance_score: float = 0.0   # 0-10 (filled by processor)
    credibility_score: float = 0.0  # 0-10 (filled by processor)
    tags: list = field(default_factory=list)  # e.g. ["NOA", "比亚迪"]

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "VideoItem":
        return cls(**d)
