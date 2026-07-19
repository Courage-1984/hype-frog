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
    # Consistent with the AEO Readiness Score's robots.txt coverage check
    # (engine_guardrails.py, pipeline/assemble.py), which already credits
    # GPTBot/PerplexityBot/CCBot coverage — CCBot was missing here.
    ("CCBot", "Robots.txt: CCBot"),
)

ROBOTS_ANALYSIS_COLUMNS: tuple[str, ...] = (
    "Section",
    "User Agent",
    "URL",
    "Status",
    "Detail",
    "Explanation",
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
    """Parse user-agent blocks into directive rows for the analysis sheet.

    Per the robots.txt spec, a "record" is one or more consecutive User-agent
    lines followed by directives that apply to ALL of them — e.g.::

        User-agent: Googlebot
        User-agent: Bingbot
        Disallow: /private/

    ``/private/`` applies to both bots. Consecutive User-agent lines accumulate
    into the current record; a non-user-agent directive attributes to every
    agent accumulated so far and closes the record (the next User-agent line
    starts a fresh one).
    """
    if not robots_text:
        return []
    groups: list[dict[str, str]] = []
    current_agents: list[str] = []
    in_agent_block = False
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
            if not in_agent_block:
                current_agents = []
            current_agents.append(val)
            in_agent_block = True
            groups.append(
                {
                    "user_agent": val,
                    "directive": "user-agent",
                    "value": val,
                }
            )
        elif directive in {"disallow", "allow", "crawl-delay", "sitemap"}:
            in_agent_block = False
            agent_labels = current_agents if current_agents else ["*"]
            for agent_label in agent_labels:
                groups.append(
                    {
                        "user_agent": agent_label,
                        "directive": directive,
                        "value": val,
                    }
                )
    return groups


def _agent_crawl_delay_value(robots_text: str | None, agent: str) -> str | None:
    """Return the raw Crawl-delay value applying to ``agent``, or ``None``."""
    if not robots_text:
        return None
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
                return val
    return None


def _agent_has_crawl_delay(robots_text: str | None, agent: str) -> bool:
    return _agent_crawl_delay_value(robots_text, agent) is not None


def _robots_has_sitemap_directive(robots_text: str | None) -> bool:
    """Whether robots.txt declares at least one ``Sitemap:`` directive."""
    if not robots_text:
        return False
    for raw_line in str(robots_text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip().lower() == "sitemap" and value.strip():
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
    # "Disallow: /" blocks the whole domain, not just this URL — check root-path
    # fetchability directly (via the same battle-tested urllib.robotparser used for
    # every other Allow/Disallow decision here) rather than re-parsing directives by
    # hand, so it's consistent with however can_fetch() resolves precedence/wildcards.
    root_disallowed = False
    if accessible and parser is not None:
        domain = _domain_key(url)
        if domain:
            try:
                root_disallowed = not parser.can_fetch("Googlebot", f"{domain}/")
            except Exception:
                root_disallowed = False
    fields: dict[str, Any] = {
        "Crawl-Delay Applies": _agent_has_crawl_delay(robots_text, "Googlebot"),
        "Robots.txt Crawl-Delay": _agent_crawl_delay_value(robots_text, "Googlebot"),
        "Sitemap in Robots.txt": _robots_has_sitemap_directive(robots_text),
        "Robots.txt Disallow /": root_disallowed,
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
                "Explanation": (
                    "No domain in this crawl returned a robots.txt fetch result — "
                    "either no URLs were crawled or the fetch phase did not run."
                ),
            }
        )
        return rows

    for domain, entry in sorted(robots_by_domain.items()):
        robots_text = str(entry.get("robots_text") or "").replace("\r\n", "\n").replace("\r", "\n")
        accessible = bool(entry.get("robots_accessible"))
        status_code = entry.get("robots_status")
        text_read_error = bool(entry.get("robots_text_read_error"))
        if text_read_error:
            status_label = "Fetched, body unreadable"
            explanation = (
                f"HTTP {status_code} — the file exists, but its body could not be "
                "decoded (encoding issue), so Allow/Disallow rules could not be parsed."
            )
        elif accessible:
            status_label = "Accessible"
            explanation = f"HTTP {status_code} with a non-empty body — treated as accessible."
        else:
            status_label = "Unavailable"
            explanation = (
                f"HTTP {status_code} or an empty body — this domain's robots.txt "
                "could not be used to make Allow/Disallow decisions for any monitored bot."
            )
        rows.append(
            {
                "Section": "1 — Raw robots.txt",
                "User Agent": domain,
                "URL": f"{domain}/robots.txt",
                "Status": status_label,
                "Detail": robots_text[:32000] if robots_text else "",
                "Explanation": explanation,
            }
        )
        has_sitemap_directive = _robots_has_sitemap_directive(robots_text)
        for group in parse_robot_groups(robots_text):
            directive = group["directive"]
            agent = group["user_agent"]
            if directive == "user-agent":
                explanation = f"Opens a rule block for user-agent \"{agent}\"."
            elif directive == "sitemap":
                explanation = "Declares a sitemap location (not attributed to a specific bot)."
            else:
                explanation = (
                    f"{directive.title()} rule for \"{agent}\" — applies to every "
                    "user-agent line immediately above it in this block."
                )
            rows.append(
                {
                    "Section": "2 — User-agent rules",
                    "User Agent": agent,
                    "URL": None,
                    "Status": directive,
                    "Detail": group["value"],
                    "Explanation": explanation,
                }
            )
        if sitemap_url_keys and not has_sitemap_directive:
            rows.append(
                {
                    "Section": "4 — Sitemap vs robots conflict",
                    "User Agent": None,
                    "URL": f"{domain}/robots.txt",
                    "Status": "Sitemap not declared",
                    "Detail": (
                        "This crawl discovered sitemap file(s) for this domain, but "
                        "robots.txt has no \"Sitemap:\" directive pointing to them."
                    ),
                    "Explanation": (
                        "Declaring the sitemap location in robots.txt helps search "
                        "engines discover it without relying on prior submission — "
                        "add a \"Sitemap: <url>\" line."
                    ),
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
                        "Explanation": (
                            f"can_fetch(\"{agent}\", url) returned False against this "
                            "domain's parsed robots.txt rules."
                        ),
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
                            "Explanation": (
                                "Listing a Googlebot-disallowed URL in the sitemap wastes "
                                "crawl budget — either remove it from the sitemap or "
                                "allow it in robots.txt."
                            ),
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
                "Explanation": "No row in this crawl resolved to Disallow for any monitored bot.",
            }
        )
    if not sitemap_conflicts and not any(
        r["Section"] == "4 — Sitemap vs robots conflict" for r in rows
    ):
        rows.append(
            {
                "Section": "4 — Sitemap vs robots conflict",
                "User Agent": None,
                "URL": None,
                "Status": "None",
                "Detail": "No sitemap URLs blocked for Googlebot.",
                "Explanation": "No conflict found between discovered sitemap URLs and Googlebot's robots.txt rules.",
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
    robots_text_read_error: bool = False,
) -> dict[str, Any]:
    accessible = robots_status == 200 and bool(robots_text)
    return {
        "llms_present": llms_present,
        "ai_allowed": ai_allowed,
        "aeo_engine_bot_coverage": aeo_engine_bot_coverage,
        "robots_text": robots_text or "",
        "robots_accessible": accessible,
        "robots_status": robots_status,
        # True when the HTTP response was a real 200 but the body failed to
        # decode — distinct from "no robots.txt" so reporting doesn't conflate
        # the two (see crawler/fetcher.py::_populate_robots_cache).
        "robots_text_read_error": robots_text_read_error,
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
