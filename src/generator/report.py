"""HTML report generator using Jinja2."""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def generate_report(
    articles: list,
    week_label: str,
    executive_summary: list,
    output_path: str,
    videos: list = None,
) -> str:
    """Render the weekly HTML report and write it to *output_path*.

    Also writes ``output/index.html`` as a redirect to the latest week.

    Args:
        articles: List of ProcessedArticle dicts (or objects with __dict__).
        week_label: Human-readable week label, e.g. "2026年3月第4週".
        executive_summary: Exactly 3 Japanese bullet strings.
        output_path: Destination path, e.g. "output/2026-W13/index.html".
        videos: Optional list of VideoItem dicts (or objects with __dict__).

    Returns:
        The resolved absolute path of the written report file.
    """
    # Normalise articles to plain dicts
    normalised = [
        a if isinstance(a, dict) else a.__dict__
        for a in articles
    ]

    # Sort by relevance descending, with a bonus for Momenta-related articles
    _MOMENTA_KEYWORDS = {"momenta", "モメンタ"}
    _MOMENTA_BONUS = 1.5

    def _sort_score(a: dict) -> float:
        base = a.get("relevance_score", 0)
        text = " ".join([
            a.get("title", ""),
            a.get("title_ja", ""),
            a.get("summary_ja", ""),
        ]).lower()
        if any(kw in text for kw in _MOMENTA_KEYWORDS):
            base += _MOMENTA_BONUS
        return base

    normalised.sort(key=_sort_score, reverse=True)

    # Keep only the top 24 articles — fills exactly 7 complete grid rows, zero gaps
    normalised = normalised[:24]

    # Assign tiers by position (not score) to guarantee visual balance:
    #   T1: 1 article  (span 6 × 1 = 1 row)
    #   T2: 2 articles (span 3 × 2 = 1 row)
    #   T3: 9 articles (span 2 × 9 = 3 rows)
    #   T4: 12 articles (span 1 × 12 = 2 rows)
    _TIER_CUTS = [1, 3, 12]  # positions where tier changes (exclusive upper bound)
    for i, a in enumerate(normalised):
        if i < _TIER_CUTS[0]:
            a["tier"] = 1
        elif i < _TIER_CUTS[1]:
            a["tier"] = 2
        elif i < _TIER_CUTS[2]:
            a["tier"] = 3
        else:
            a["tier"] = 4

    # Normalise videos to plain dicts, keep top 8 by relevance
    normalised_videos = sorted(
        [v if isinstance(v, dict) else v.__dict__ for v in (videos or [])],
        key=lambda v: v.get("relevance_score", 0),
        reverse=True,
    )[:8]

    generated_at = datetime.now().strftime("%Y年%m月%d日 %H:%M JST")

    env = _jinja_env()
    template = env.get_template("weekly.html.j2")
    html = template.render(
        week_label=week_label,
        generated_at=generated_at,
        articles=normalised,
        total_articles=len(normalised),
        executive_summary=executive_summary,
        videos=normalised_videos,
    )

    # Write the week-specific report
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    # Write/update output/index.html as a redirect to the latest week
    _write_redirect(out)

    return str(out.resolve())


def _write_redirect(report_path: Path) -> None:
    """Write (or overwrite) output/index.html to redirect to the latest report."""
    # Navigate up until we reach the top-level output/ directory.
    # report_path is e.g. output/2026-W13/index.html
    output_root = report_path.parent.parent
    redirect_target = report_path.relative_to(output_root).as_posix()

    redirect_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="0; url={redirect_target}" />
  <title>中国ADAS週報 — 最新版</title>
</head>
<body>
  <p><a href="{redirect_target}">最新週報へ移動しています...</a></p>
</body>
</html>
"""
    index = output_root / "index.html"
    index.write_text(redirect_html, encoding="utf-8")
