"""robots.txt per-URL access mapping and analysis sheet builders (A5)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from hype_frog.core.url_normalization import normalize_url

ROBOTS_AGENTS: tuple[tuple[str, str], ...] = (
    ("Googlebot", "Robots.txt: Googlebot"),
    ("Bingbot", "Robots.txt: Bingbot"),
    ("GPTBot", "Robots.txt: GPTBot"),
    ("ClaudeBot", "Robots.txt: ClaudeBot"),
    ("PerplexityBot", "Robots.txt: PerplexityBot"),
)

ROBOTS_ANALYSIS_COLUMNS: tuple[str, ...] = (
    "Section",
    "User Agent",
    "URL",
    "Status",
    "Detail",
)


def _domain_key(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def build_robot_parser(robots_text: str | None) -> RobotFileParser | None:
    if not robots_text or not str(robots_text).strip():
        return None
    parser = RobotFileParser()
    parser.parse(str(robots_text).splitlines())
    return parser


def parse_robot_groups(robots_text: str | None) -> list[dict[str, str]]:
    """Parse user-agent blocks into directive rows for the analysis sheet."""
    if not robots_text:
        return []
    groups: list[dict[str, str]] = []
    current_agents: list[str] = []
    for raw_line in str(robots_text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        directive = key.strip().lower()
        val = value.strip()
        if directive == "user-agent":
            current_agents = [val]
            groups.append(
                {
                    "user_agent": val,
                    "directive": "user-agent",
                    "value": val,
                }
            )
        elif directive in {"disallow", "allow", "crawl-delay", "sitemap"}:
            agent_label = current_agents[-1] if current_agents else "*"
            groups.append(
                {
                    "user_agent": agent_label,
                    "directive": directive,
                    "value": val,
                }
            )
    return groups


def _agent_has_crawl_delay(robots_text: str | None, agent: str) -> bool:
    if not robots_text:
        return False
    agent_lower = agent.lower()
    active_agents: list[str] = []
    for raw_line in str(robots_text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        directive = key.strip().lower()
        val = value.strip()
        if directive == "user-agent":
            active_agents = [val.lower()]
        elif directive == "crawl-delay" and val:
            if not active_agents or agent_lower in active_agents or "*" in active_agents:
                return True
    return False


def agent_access_label(
    parser: RobotFileParser | None,
    *,
    agent: str,
    url: str,
    robots_accessible: bool,
) -> str:
    if not robots_accessible or parser is None:
        return "Not specified"
    try:
        return "Allow" if parser.can_fetch(agent, url) else "Disallow"
    except Exception:
        return "Not specified"


def build_robots_row_fields(
    *,
    url: str,
    domain_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Per-URL robots.txt columns for extra/main rows."""
    parser = domain_entry.get("parser") if domain_entry else None
    accessible = bool(domain_entry and domain_entry.get("robots_accessible"))
    robots_text = domain_entry.get("robots_text") if domain_entry else None
    fields: dict[str, Any] = {
        "Crawl-Delay Applies": _agent_has_crawl_delay(robots_text, "Googlebot"),
    }
    for agent, column in ROBOTS_AGENTS:
        fields[column] = agent_access_label(
            parser,
            agent=agent,
            url=url,
            robots_accessible=accessible,
        )
    return fields


def enrich_extra_rows_robots_mapping(
    extra_rows: list[dict[str, Any]],
    *,
    robots_by_domain: dict[str, dict[str, Any]],
) -> None:
    """Mutate extra rows with per-agent robots.txt access labels."""
    for row in extra_rows:
        url = str(row.get("Final URL") or row.get("URL") or "").strip()
        if not url:
            continue
        domain = _domain_key(url)
        entry = robots_by_domain.get(domain)
        row.update(build_robots_row_fields(url=url, domain_entry=entry))


def build_robots_analysis_rows(
    *,
    robots_by_domain: dict[str, dict[str, Any]],
    extra_rows: list[dict[str, Any]],
    sitemap_url_keys: set[str],
) -> list[dict[str, Any]]:
    """Multi-section Robots.txt Analysis worksheet rows."""
    rows: list[dict[str, Any]] = []
    if not robots_by_domain:
        rows.append(
            {
                "Section": "Summary",
                "User Agent": None,
                "URL": None,
                "Status": "No robots.txt data",
                "Detail": "robots.txt was not fetched during this crawl.",
            }
        )
        return rows

    for domain, entry in sorted(robots_by_domain.items()):
        robots_text = str(entry.get("robots_text") or "").replace("\r\n", "\n").replace("\r", "\n")
        accessible = bool(entry.get("robots_accessible"))
        rows.append(
            {
                "Section": "1 — Raw robots.txt",
                "User Agent": domain,
                "URL": f"{domain}/robots.txt",
                "Status": "Accessible" if accessible else "Unavailable",
                "Detail": robots_text[:32000] if robots_text else "",
            }
        )
        for group in parse_robot_groups(robots_text):
            rows.append(
                {
                    "Section": "2 — User-agent rules",
                    "User Agent": group["user_agent"],
                    "URL": None,
                    "Status": group["directive"],
                    "Detail": group["value"],
                }
            )

    blocked: list[dict[str, Any]] = []
    sitemap_conflicts: list[dict[str, Any]] = []
    for row in extra_rows:
        url = str(row.get("URL") or "").strip()
        if not url:
            continue
        url_key = normalize_url(url, keep_query=True)
        for agent, column in ROBOTS_AGENTS:
            status = str(row.get(column) or "")
            if status == "Disallow":
                blocked.append(
                    {
                        "Section": "3 — Blocked crawled URLs",
                        "User Agent": agent,
                        "URL": url,
                        "Status": "Disallow",
                        "Detail": f"Blocked for {agent} per robots.txt",
                    }
                )
                if agent == "Googlebot" and url_key in sitemap_url_keys:
                    sitemap_conflicts.append(
                        {
                            "Section": "4 — Sitemap vs robots conflict",
                            "User Agent": "Googlebot",
                            "URL": url,
                            "Status": "In sitemap but Disallow",
                            "Detail": "URL appears in sitemap but is blocked for Googlebot.",
                        }
                    )
    rows.extend(blocked)
    rows.extend(sitemap_conflicts)
    if not blocked:
        rows.append(
            {
                "Section": "3 — Blocked crawled URLs",
                "User Agent": None,
                "URL": None,
                "Status": "None",
                "Detail": "No crawled URLs were blocked for monitored user-agents.",
            }
        )
    if not sitemap_conflicts:
        rows.append(
            {
                "Section": "4 — Sitemap vs robots conflict",
                "User Agent": None,
                "URL": None,
                "Status": "None",
                "Detail": "No sitemap URLs blocked for Googlebot.",
            }
        )
    return rows


def prepare_robots_domain_entry(
    *,
    robots_text: str | None,
    robots_status: int | None,
    llms_present: bool,
    ai_allowed: bool | None,
    aeo_engine_bot_coverage: float | None,
) -> dict[str, Any]:
    accessible = robots_status == 200 and bool(robots_text)
    return {
        "llms_present": llms_present,
        "ai_allowed": ai_allowed,
        "aeo_engine_bot_coverage": aeo_engine_bot_coverage,
        "robots_text": robots_text or "",
        "robots_accessible": accessible,
        "robots_status": robots_status,
        "parser": build_robot_parser(robots_text) if accessible else None,
    }


__all__ = [
    "ROBOTS_AGENTS",
    "ROBOTS_ANALYSIS_COLUMNS",
    "agent_access_label",
    "build_robot_parser",
    "build_robots_analysis_rows",
    "build_robots_row_fields",
    "enrich_extra_rows_robots_mapping",
    "parse_robot_groups",
    "prepare_robots_domain_entry",
]
