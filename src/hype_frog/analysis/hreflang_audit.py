"""Hreflang extraction, ISO validation, and reciprocal cluster checks (A6)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from hype_frog.core.url_normalization import normalize_url

_ISO639_1 = frozenset(
    {
        "aa",
        "ab",
        "ae",
        "af",
        "ak",
        "am",
        "an",
        "ar",
        "as",
        "av",
        "ay",
        "az",
        "ba",
        "be",
        "bg",
        "bh",
        "bi",
        "bm",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "ce",
        "ch",
        "co",
        "cr",
        "cs",
        "cu",
        "cv",
        "cy",
        "da",
        "de",
        "dv",
        "dz",
        "ee",
        "el",
        "en",
        "eo",
        "es",
        "et",
        "eu",
        "fa",
        "ff",
        "fi",
        "fj",
        "fo",
        "fr",
        "fy",
        "ga",
        "gd",
        "gl",
        "gn",
        "gu",
        "gv",
        "ha",
        "he",
        "hi",
        "ho",
        "hr",
        "ht",
        "hu",
        "hy",
        "hz",
        "ia",
        "id",
        "ie",
        "ig",
        "ii",
        "ik",
        "io",
        "is",
        "it",
        "iu",
        "ja",
        "jv",
        "ka",
        "kg",
        "ki",
        "kj",
        "kk",
        "kl",
        "km",
        "kn",
        "ko",
        "kr",
        "ks",
        "ku",
        "kv",
        "kw",
        "ky",
        "la",
        "lb",
        "lg",
        "li",
        "ln",
        "lo",
        "lt",
        "lu",
        "lv",
        "mg",
        "mh",
        "mi",
        "mk",
        "ml",
        "mn",
        "mr",
        "ms",
        "mt",
        "my",
        "na",
        "nb",
        "nd",
        "ne",
        "ng",
        "nl",
        "nn",
        "no",
        "nr",
        "nv",
        "ny",
        "oc",
        "oj",
        "om",
        "or",
        "os",
        "pa",
        "pi",
        "pl",
        "ps",
        "pt",
        "qu",
        "rm",
        "rn",
        "ro",
        "ru",
        "rw",
        "sa",
        "sc",
        "sd",
        "se",
        "sg",
        "si",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sq",
        "sr",
        "ss",
        "st",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "ti",
        "tk",
        "tl",
        "tn",
        "to",
        "tr",
        "ts",
        "tt",
        "tw",
        "ty",
        "ug",
        "uk",
        "ur",
        "uz",
        "ve",
        "vi",
        "vo",
        "wa",
        "wo",
        "xh",
        "yi",
        "yo",
        "za",
        "zh",
        "zu",
    }
)

_ISO3166_1_ALPHA2 = frozenset(
    {
        "ad",
        "ae",
        "af",
        "ag",
        "ai",
        "al",
        "am",
        "ao",
        "aq",
        "ar",
        "as",
        "at",
        "au",
        "aw",
        "ax",
        "az",
        "ba",
        "bb",
        "bd",
        "be",
        "bf",
        "bg",
        "bh",
        "bi",
        "bj",
        "bl",
        "bm",
        "bn",
        "bo",
        "bq",
        "br",
        "bs",
        "bt",
        "bv",
        "bw",
        "by",
        "bz",
        "ca",
        "cc",
        "cd",
        "cf",
        "cg",
        "ch",
        "ci",
        "ck",
        "cl",
        "cm",
        "cn",
        "co",
        "cr",
        "cu",
        "cv",
        "cw",
        "cx",
        "cy",
        "cz",
        "de",
        "dj",
        "dk",
        "dm",
        "do",
        "dz",
        "ec",
        "ee",
        "eg",
        "eh",
        "er",
        "es",
        "et",
        "fi",
        "fj",
        "fk",
        "fm",
        "fo",
        "fr",
        "ga",
        "gb",
        "gd",
        "ge",
        "gf",
        "gg",
        "gh",
        "gi",
        "gl",
        "gm",
        "gn",
        "gp",
        "gq",
        "gr",
        "gs",
        "gt",
        "gu",
        "gw",
        "gy",
        "hk",
        "hm",
        "hn",
        "hr",
        "ht",
        "hu",
        "id",
        "ie",
        "il",
        "im",
        "in",
        "io",
        "iq",
        "ir",
        "is",
        "it",
        "je",
        "jm",
        "jo",
        "jp",
        "ke",
        "kg",
        "kh",
        "ki",
        "km",
        "kn",
        "kp",
        "kr",
        "kw",
        "ky",
        "kz",
        "la",
        "lb",
        "lc",
        "li",
        "lk",
        "lr",
        "ls",
        "lt",
        "lu",
        "lv",
        "ly",
        "ma",
        "mc",
        "md",
        "me",
        "mf",
        "mg",
        "mh",
        "mk",
        "ml",
        "mm",
        "mn",
        "mo",
        "mp",
        "mq",
        "mr",
        "ms",
        "mt",
        "mu",
        "mv",
        "mw",
        "mx",
        "my",
        "mz",
        "na",
        "nc",
        "ne",
        "nf",
        "ng",
        "ni",
        "nl",
        "no",
        "np",
        "nr",
        "nu",
        "nz",
        "om",
        "pa",
        "pe",
        "pf",
        "pg",
        "ph",
        "pk",
        "pl",
        "pm",
        "pn",
        "pr",
        "ps",
        "pt",
        "pw",
        "py",
        "qa",
        "re",
        "ro",
        "rs",
        "ru",
        "rw",
        "sa",
        "sb",
        "sc",
        "sd",
        "se",
        "sg",
        "sh",
        "si",
        "sj",
        "sk",
        "sl",
        "sm",
        "sn",
        "so",
        "sr",
        "ss",
        "st",
        "sv",
        "sx",
        "sy",
        "sz",
        "tc",
        "td",
        "tf",
        "tg",
        "th",
        "tj",
        "tk",
        "tl",
        "tm",
        "tn",
        "to",
        "tr",
        "tt",
        "tv",
        "tw",
        "tz",
        "ua",
        "ug",
        "um",
        "us",
        "uy",
        "uz",
        "va",
        "vc",
        "ve",
        "vg",
        "vi",
        "vn",
        "vu",
        "wf",
        "ws",
        "ye",
        "yt",
        "za",
        "zm",
        "zw",
    }
)

_SIGNAL_PAIR_RE = re.compile(r"^\s*([^:]+):\s*(.+)\s*$")


@dataclass(frozen=True)
class HreflangExtraction:
    signals: str | None
    count: int
    self_referenced: bool
    x_default_present: bool
    declared_languages: str
    alternate_urls: str
    codes_valid: bool
    invalid_codes: str
    pairs: tuple[tuple[str, str], ...]


def is_valid_hreflang_code(code: str) -> bool:
    """Validate hreflang against ISO 639-1 and optional ISO 3166-1 region."""
    token = str(code or "").strip().lower()
    if not token:
        return False
    if token == "x-default":
        return True
    parts = token.split("-")
    if len(parts) == 1:
        return parts[0] in _ISO639_1
    if len(parts) == 2:
        lang, region = parts
        return lang in _ISO639_1 and region in _ISO3166_1_ALPHA2
    if len(parts) == 3 and parts[1] == "latn":
        return parts[0] in _ISO639_1 and parts[2] in _ISO3166_1_ALPHA2
    return False


def extract_hreflang_from_soup(
    soup: BeautifulSoup, resolved_url: str
) -> HreflangExtraction:
    """Parse on-page hreflang alternates without extra network I/O."""
    pairs: list[tuple[str, str]] = []
    count = 0
    self_referenced = False
    x_default = False
    resolved_norm = normalize_url(resolved_url)
    seen: set[tuple[str, str]] = set()
    invalid: list[str] = []
    languages: list[str] = []
    urls: list[str] = []

    try:
        candidates = soup.find_all("link", attrs={"rel": True, "hreflang": True})
    except Exception:
        return HreflangExtraction(None, 0, False, False, "", "", True, "", ())

    for tag in candidates:
        rel_tokens = tag.get("rel") or []
        if isinstance(rel_tokens, str):
            rel_tokens = [rel_tokens]
        if not any("alternate" in str(token).lower() for token in rel_tokens):
            continue
        lang = (tag.get("hreflang") or "").strip()
        href = (tag.get("href") or "").strip()
        if not lang or not href:
            continue
        if not is_valid_hreflang_code(lang):
            invalid.append(lang)
        try:
            absolute = normalize_url(urljoin(resolved_url, href))
        except Exception:
            absolute = href
        key = (lang.lower(), absolute)
        if key in seen:
            continue
        seen.add(key)
        count += 1
        pairs.append((lang, absolute))
        languages.append(lang)
        urls.append(absolute)
        if lang.lower() == "x-default":
            x_default = True
        if absolute == resolved_norm:
            self_referenced = True

    if not pairs:
        return HreflangExtraction(None, 0, False, False, "", "", True, "", ())

    joined = "; ".join(f"{lang}: {url}" for lang, url in pairs)
    return HreflangExtraction(
        signals=joined,
        count=count,
        self_referenced=self_referenced,
        x_default_present=x_default,
        declared_languages=", ".join(languages),
        alternate_urls=" | ".join(urls),
        codes_valid=not invalid,
        invalid_codes=", ".join(invalid),
        pairs=tuple(pairs),
    )


def parse_hreflang_signal_pairs(signals: object) -> list[tuple[str, str]]:
    text = str(signals or "").strip()
    if not text:
        return []
    pairs: list[tuple[str, str]] = []
    for chunk in text.split(";"):
        match = _SIGNAL_PAIR_RE.match(chunk.strip())
        if not match:
            continue
        pairs.append((match.group(1).strip(), match.group(2).strip()))
    return pairs


def _row_values(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return row.values


def _page_url_key(row_values: dict[str, Any]) -> str:
    return normalize_url(str(row_values.get("Final URL") or row_values.get("URL") or ""))


def _reciprocal_status(
    page_url: str,
    pairs: list[tuple[str, str]],
    clusters_by_url: dict[str, list[tuple[str, str]]],
) -> tuple[str, bool]:
    if not pairs:
        return "Not Declared", True
    page_norm = normalize_url(page_url)
    missing_returns: list[str] = []
    uncrawled = 0
    for _lang, alt_url in pairs:
        alt_norm = normalize_url(alt_url)
        if alt_norm == page_norm:
            continue
        alt_pairs = clusters_by_url.get(alt_norm)
        if alt_pairs is None:
            uncrawled += 1
            continue
        back_urls = {normalize_url(url) for _, url in alt_pairs}
        if page_norm not in back_urls:
            missing_returns.append(alt_url)
    if missing_returns:
        return "Missing Return Link", False
    if uncrawled > 0:
        return "Alternate Not Crawled", False
    return "Valid", True


def enrich_hreflang_reciprocity(rows: list[Any]) -> None:
    """Validate reciprocal hreflang clusters across crawled pages."""
    clusters_by_url: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        values = _row_values(row)
        url_key = _page_url_key(values)
        if not url_key:
            continue
        pairs = parse_hreflang_signal_pairs(values.get("Hreflang Signals"))
        if pairs:
            clusters_by_url[url_key] = pairs

    for row in rows:
        values = _row_values(row)
        if not values.get("Hreflang Present"):
            values["Hreflang Reciprocal Status"] = "Not Declared"
            values["Hreflang Reciprocal Check"] = None
            continue
        page_url = str(values.get("Final URL") or values.get("URL") or "")
        pairs = parse_hreflang_signal_pairs(values.get("Hreflang Signals"))
        if not values.get("Hreflang Code Valid", True):
            values["Hreflang Reciprocal Status"] = "Invalid Language Code"
            values["Hreflang Reciprocal Check"] = False
            continue
        status, ok = _reciprocal_status(page_url, pairs, clusters_by_url)
        values["Hreflang Reciprocal Status"] = status
        values["Hreflang Reciprocal Check"] = ok
