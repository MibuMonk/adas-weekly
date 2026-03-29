#!/usr/bin/env python3
"""ADAS Weekly Report Generator — main orchestration script."""
from __future__ import annotations

import asyncio
import os
from datetime import datetime


async def main() -> None:
    # 1. Collect articles
    from src.collector.runner import collect_all
    articles = await collect_all()
    print(f"Collected {len(articles)} articles")

    # 2. Collect videos from Bilibili
    from src.collector.bilibili import collect_all_videos
    import yaml
    with open("data/sources.yaml") as f:
        sources_cfg = yaml.safe_load(f)
    bili_cfg = sources_cfg.get("bilibili", {})
    keywords = bili_cfg.get("keywords", [])
    max_per = bili_cfg.get("max_per_keyword", 8)
    videos_raw = await collect_all_videos(keywords, max_per)
    print(f"Collected {len(videos_raw)} videos")

    # 3. Process articles with LLM (filter, translate, score)
    from src.processor.runner import process_all
    processed = await process_all(articles)
    print(f"Processed {len(processed)} relevant articles")

    # 4. Process videos with LLM
    from src.processor.video_pipeline import process_all_videos
    processed_videos = await process_all_videos(videos_raw)
    print(f"Processed {len(processed_videos)} relevant videos")

    # 5. Generate executive summary from top 10 articles
    from src.processor.llm import llm_call
    from src.generator.executive_summary import generate_executive_summary, generate_morning_brief
    summary = await generate_executive_summary(processed[:10], llm_call)
    brief = await generate_morning_brief(processed[:10], llm_call)

    # 6. Render HTML report
    from src.generator.report import generate_report
    week_label = get_week_label()
    iso_week = datetime.now().strftime("%Y-W%V")
    output_path = f"output/{iso_week}/index.html"
    result = generate_report(
        articles=[a.__dict__ for a in processed],
        videos=[v.__dict__ for v in processed_videos],
        week_label=week_label,
        executive_summary=summary,
        morning_brief=brief,
        output_path=output_path,
    )
    print(f"Report generated: {result}")


def get_week_label() -> str:
    """Return a Japanese-style week label: 年月第N週."""
    now = datetime.now()
    week_num = (now.day - 1) // 7 + 1
    return f"{now.year}年{now.month}月第{week_num}週"


def run() -> None:
    """Sync entrypoint for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
