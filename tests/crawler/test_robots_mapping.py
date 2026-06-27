"""A5 robots.txt per-URL mapping tests."""
from __future__ import annotations

from hype_frog.crawler.robots_mapping import (
    agent_access_label,
    build_robot_parser,
    build_robots_analysis_rows,
    build_robots_row_fields,
    enrich_extra_rows_robots_mapping,
    prepare_robots_domain_entry,
)


def test_agent_access_allow_and_disallow() -> None:
    robots_text = "\n".join(
        [
            "User-agent: Googlebot",
            "Disallow: /private/",
            "Allow: /",
        ]
    )
    parser = build_robot_parser(robots_text)
    assert agent_access_label(
        parser,
        agent="Googlebot",
        url="https://example.com/public",
        robots_accessible=True,
    ) == "Allow"
    assert agent_access_label(
        parser,
        agent="Googlebot",
        url="https://example.com/private/page",
        robots_accessible=True,
    ) == "Disallow"


def test_build_robots_row_fields_includes_crawl_delay() -> None:
    robots_text = "User-agent: Googlebot\nCrawl-delay: 10\nAllow: /"
    entry = prepare_robots_domain_entry(
        robots_text=robots_text,
        robots_status=200,
        llms_present=False,
        ai_allowed=True,
        aeo_engine_bot_coverage=1.0,
    )
    fields = build_robots_row_fields(
        url="https://example.com/page",
        domain_entry=entry,
    )
    assert fields["Crawl-Delay Applies"] is True
    assert fields["Robots.txt: Googlebot"] == "Allow"


def test_enrich_extra_rows_and_sitemap_conflict_section() -> None:
    entry = prepare_robots_domain_entry(
        robots_text="User-agent: Googlebot\nDisallow: /blocked\n",
        robots_status=200,
        llms_present=False,
        ai_allowed=False,
        aeo_engine_bot_coverage=0.0,
    )
    robots_by_domain = {"https://example.com": entry}
    extra_rows = [
        {
            "URL": "https://example.com/blocked",
            "Final URL": "https://example.com/blocked",
        }
    ]
    enrich_extra_rows_robots_mapping(extra_rows, robots_by_domain=robots_by_domain)
    assert extra_rows[0]["Robots.txt: Googlebot"] == "Disallow"
    analysis = build_robots_analysis_rows(
        robots_by_domain=robots_by_domain,
        extra_rows=extra_rows,
        sitemap_url_keys={"https://example.com/blocked"},
    )
    sections = {row["Section"] for row in analysis}
    assert "4 — Sitemap vs robots conflict" in sections
