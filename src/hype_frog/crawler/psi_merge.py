"""PSI payload parsing — Lighthouse lab, CrUX field, and merged row shapes."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from hype_frog.core.url_normalization import normalize_url

def psi_index_key(url: object) -> str:
    """Canonical key for PSI map lookups (matches crawl ``normalize_url_key``)."""
    return normalize_url(url, keep_query=True)
_PSI_CATEGORIES: tuple[str, ...] = (
    "performance",
    "accessibility",
    "best-practices",
    "seo",
)

PSI_LIGHTHOUSE_EXPORT_KEYS: tuple[str, ...] = (
    "Lighthouse Performance (Mobile)",
    "Lighthouse Accessibility (Mobile)",
    "Lighthouse Best Practices (Mobile)",
    "Lighthouse SEO Score (Mobile)",
    "Lab LCP (Mobile) (s)",
    "Lab CLS (Mobile)",
    "Lab TBT (Mobile) (ms)",
    "Lab INP (Mobile) (ms)",
    "Lab FCP (Mobile) (s)",
    "Lab Speed Index (Mobile) (s)",
    "Lab TTI (Mobile) (s)",
    "Lab TTFB (Mobile) (ms)",
    "Lighthouse Performance (Desktop)",
    "Lighthouse Accessibility (Desktop)",
    "Lighthouse Best Practices (Desktop)",
    "Lighthouse SEO Score (Desktop)",
    "Lab LCP (Desktop) (s)",
    "Lab CLS (Desktop)",
    "Lab TBT (Desktop) (ms)",
    "Lab INP (Desktop) (ms)",
    "Lab FCP (Desktop) (s)",
    "Lab Speed Index (Desktop) (s)",
    "Lab TTI (Desktop) (s)",
    "Lab TTFB (Desktop) (ms)",
    "Page Size (KB)",
    "DOM Size (nodes)",
    "JS Execution (ms)",
    "Network Request Count",
    "Has Text Compression",
    "Has Long Cache TTL Issues",
    "Has Render Blocking Resources",
    "Uses Modern Image Formats",
)
def audit_numeric(payload: dict[str, Any], audit_id: str) -> float | None:
    try:
        raw = payload["lighthouseResult"]["audits"][audit_id]["numericValue"]
        if raw is None:
            return None
        return float(raw)
    except (KeyError, TypeError, ValueError):
        return None


def category_score(payload: dict[str, Any], category: str) -> int | None:
    try:
        score = payload["lighthouseResult"]["categories"][category]["score"]
        if score is None:
            return None
        return int(round(float(score) * 100))
    except (KeyError, TypeError, ValueError):
        return None


def lab_strategy_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload.get("lighthouseResult"), dict):
        return {
            "performance_score": None,
            "seo_score": None,
            "lcp_seconds": None,
            "cls": None,
            "inp_ms": None,
            "ttfb_seconds": None,
        }
    lcp_ms = audit_numeric(payload, "largest-contentful-paint")
    cls_raw = audit_numeric(payload, "cumulative-layout-shift")
    inp_ms = audit_numeric(payload, "interaction-to-next-paint")
    ttfb_seconds: float | None = None
    for key in ("server-response-time", "network-server-latency"):
        ms = audit_numeric(payload, key)
        if ms is not None:
            ttfb_seconds = ms / 1000.0
            break
    return {
        "performance_score": category_score(payload, "performance"),
        "seo_score": category_score(payload, "seo"),
        "lcp_seconds": round(lcp_ms / 1000.0, 3) if lcp_ms is not None else None,
        "cls": round(float(cls_raw), 4) if cls_raw is not None else None,
        "inp_ms": round(float(inp_ms), 2) if inp_ms is not None else None,
        "ttfb_seconds": round(float(ttfb_seconds), 4) if ttfb_seconds is not None else None,
    }


def extract_lighthouse_data(
    lighthouse_result: dict[str, Any],
    prefix: str = "mobile",
) -> dict[str, Any]:
    """Extract comprehensive Lighthouse lab data for export columns."""
    out: dict[str, Any] = {}
    if not lighthouse_result:
        return out

    audits = lighthouse_result.get("audits", {})
    categories = lighthouse_result.get("categories", {})

    def audit_score(key: str) -> int | None:
        audit = audits.get(key, {})
        if not isinstance(audit, dict):
            return None
        score = audit.get("score")
        if score is None:
            return None
        return int(round(float(score) * 100))

    def audit_ms(key: str) -> float | None:
        audit = audits.get(key, {})
        if not isinstance(audit, dict):
            return None
        value = audit.get("numericValue")
        if value is None:
            return None
        return round(float(value), 1)

    def audit_s(key: str) -> float | None:
        ms_value = audit_ms(key)
        return round(ms_value / 1000.0, 3) if ms_value is not None else None

    def cat_score(key: str) -> int | None:
        category = categories.get(key, {})
        if not isinstance(category, dict):
            return None
        score = category.get("score")
        if score is None:
            return None
        return int(round(float(score) * 100))

    label = prefix.capitalize()

    out[f"Lighthouse Performance ({label})"] = cat_score("performance")
    out[f"Lighthouse Accessibility ({label})"] = cat_score("accessibility")
    out[f"Lighthouse Best Practices ({label})"] = cat_score("best-practices")
    out[f"Lighthouse SEO Score ({label})"] = cat_score("seo")

    out[f"Lab LCP ({label}) (s)"] = audit_s("largest-contentful-paint")
    cls_audit = audits.get("cumulative-layout-shift", {})
    cls_val = cls_audit.get("numericValue") if isinstance(cls_audit, dict) else None
    out[f"Lab CLS ({label})"] = round(float(cls_val), 4) if cls_val is not None else None
    out[f"Lab TBT ({label}) (ms)"] = audit_ms("total-blocking-time")
    out[f"Lab INP ({label}) (ms)"] = audit_ms("interaction-to-next-paint")
    out[f"Lab FCP ({label}) (s)"] = audit_s("first-contentful-paint")
    out[f"Lab Speed Index ({label}) (s)"] = audit_s("speed-index")
    out[f"Lab TTI ({label}) (s)"] = audit_s("interactive")

    ttfb_ms = audit_ms("server-response-time")
    if ttfb_ms is None:
        ttfb_ms = audit_ms("network-server-latency")
    out[f"Lab TTFB ({label}) (ms)"] = ttfb_ms

    if prefix == "mobile":
        total_bytes = audits.get("total-byte-weight", {}).get("numericValue")
        out["Page Size (KB)"] = (
            round(float(total_bytes) / 1024.0, 1) if total_bytes is not None else None
        )
        dom_size = audits.get("dom-size", {}).get("numericValue")
        out["DOM Size (nodes)"] = int(dom_size) if dom_size is not None else None
        js_exec = audits.get("bootup-time", {}).get("numericValue")
        out["JS Execution (ms)"] = round(float(js_exec), 1) if js_exec is not None else None
        net_req = audits.get("network-requests", {})
        items = (net_req.get("details") or {}).get("items", []) if isinstance(net_req, dict) else []
        out["Network Request Count"] = len(items) if items else None

        compression_score = audit_score("uses-text-compression")
        cache_score = audit_score("uses-long-cache-ttl")
        render_score = audit_score("render-blocking-resources")
        webp_score = audit_score("uses-webp-images")
        modern_score = audit_score("modern-image-formats")
        out["Has Text Compression"] = compression_score == 100
        out["Has Long Cache TTL Issues"] = (
            cache_score is not None and cache_score < 100
        )
        out["Has Render Blocking Resources"] = (
            render_score is not None and render_score < 100
        )
        out["Uses Modern Image Formats"] = webp_score == 100 or modern_score == 100

    return out


def extract_psi_network_payload(
    raw_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Extract Lighthouse network-requests and render-blocking URLs for A2."""
    lh = raw_payload.get("lighthouseResult")
    if not isinstance(lh, dict):
        return [], []
    audits = lh.get("audits", {})
    if not isinstance(audits, dict):
        return [], []

    net_req = audits.get("network-requests", {})
    raw_items: list[Any] = []
    if isinstance(net_req, dict):
        details = net_req.get("details") or {}
        if isinstance(details, dict):
            raw_items = details.get("items") or []

    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        items.append(
            {
                "url": url,
                "transferSize": item.get("transferSize"),
                "resourceType": item.get("resourceType"),
            }
        )

    blocking: list[str] = []
    rb_audit = audits.get("render-blocking-resources", {})
    if isinstance(rb_audit, dict):
        rb_details = rb_audit.get("details") or {}
        if isinstance(rb_details, dict):
            for rb_item in rb_details.get("items") or []:
                if isinstance(rb_item, dict) and rb_item.get("url"):
                    blocking.append(str(rb_item["url"]))

    return items, blocking


def apply_lighthouse_extraction(
    merged_flat: dict[str, Any],
    *,
    mobile_raw: dict[str, Any],
    desktop_raw: dict[str, Any],
    mobile_ok: bool,
    desktop_ok: bool,
) -> None:
    """Merge Lighthouse lab columns and sync legacy PSI score/LCP keys."""
    if mobile_ok:
        mobile_lh = mobile_raw.get("lighthouseResult")
        if isinstance(mobile_lh, dict):
            merged_flat.update(extract_lighthouse_data(mobile_lh, prefix="mobile"))
    if desktop_ok:
        desktop_lh = desktop_raw.get("lighthouseResult")
        if isinstance(desktop_lh, dict):
            merged_flat.update(extract_lighthouse_data(desktop_lh, prefix="desktop"))

    mobile_perf = merged_flat.get("Lighthouse Performance (Mobile)")
    if mobile_perf is not None:
        merged_flat["Mobile Score"] = mobile_perf
    desktop_perf = merged_flat.get("Lighthouse Performance (Desktop)")
    if desktop_perf is not None:
        merged_flat["Desktop Score"] = desktop_perf

    if merged_flat.get("Mobile LCP") is None:
        lab_lcp = merged_flat.get("Lab LCP (Mobile) (s)")
        if lab_lcp is not None:
            merged_flat["Mobile LCP"] = lab_lcp
    if merged_flat.get("Mobile CLS") is None:
        lab_cls = merged_flat.get("Lab CLS (Mobile)")
        if lab_cls is not None:
            merged_flat["Mobile CLS"] = lab_cls
    if merged_flat.get("Mobile TTFB") is None:
        ttfb_ms = merged_flat.get("Lab TTFB (Mobile) (ms)")
        if ttfb_ms is not None:
            merged_flat["Mobile TTFB"] = round(float(ttfb_ms) / 1000.0, 3)


def crux_cls_from_percentile(raw: float) -> float:
    """CrUX CLS percentiles are often stored as hundredths (e.g. 12 → 0.12)."""
    v = float(raw)
    if v > 1.0:
        return round(v / 100.0, 4)
    return round(v, 4)


def detect_crux_level(
    payload: dict[str, Any],
    requested_url: str,
) -> tuple[dict[str, Any] | None, str]:
    """Return CrUX metrics and level: ``URL``, ``Origin``, or ``None``."""
    url_exp = payload.get("loadingExperience")
    origin_exp = payload.get("originLoadingExperience")

    if url_exp:
        if url_exp.get("origin_fallback") is True:
            if isinstance(origin_exp, dict) and origin_exp.get("metrics"):
                return origin_exp.get("metrics"), "Origin"
            if isinstance(url_exp.get("metrics"), dict):
                return url_exp.get("metrics"), "Origin"
            return None, "Origin"

        exp_id = str(url_exp.get("id") or "")
        if exp_id:
            exp_parsed = urlparse(exp_id.rstrip("/"))
            req_parsed = urlparse(str(requested_url or "").rstrip("/"))
            if exp_parsed.path in ("", "/") and req_parsed.path not in ("", "/"):
                if isinstance(origin_exp, dict) and origin_exp.get("metrics"):
                    return origin_exp.get("metrics"), "Origin"
                if isinstance(url_exp.get("metrics"), dict):
                    return url_exp.get("metrics"), "Origin"
                return None, "Origin"

        if isinstance(url_exp.get("metrics"), dict) and url_exp.get("metrics"):
            return url_exp.get("metrics"), "URL"

    if isinstance(origin_exp, dict) and origin_exp.get("metrics"):
        return origin_exp.get("metrics"), "Origin"

    return None, "None"


def extract_crux_metric(
    metrics: dict[str, Any],
    metric_key: str,
    *,
    to_seconds: bool = False,
) -> float | None:
    """Extract the 75th percentile value from a CrUX metrics dict."""
    metric = metrics.get(metric_key, {})
    if not isinstance(metric, dict):
        return None
    percentile = metric.get("percentile")
    if percentile is None:
        return None
    val = float(percentile)
    if metric_key == "CUMULATIVE_LAYOUT_SHIFT_SCORE":
        return crux_cls_from_percentile(val)
    if to_seconds:
        return round(val / 1000.0, 3)
    return round(val, 2)


def extract_crux_category(metrics: dict[str, Any], metric_key: str) -> str | None:
    metric = metrics.get(metric_key, {})
    if not isinstance(metric, dict):
        return None
    category = metric.get("category")
    return str(category) if category is not None else None


def parsed_crux_snapshot(metrics: dict[str, Any]) -> dict[str, Any]:
    """Flatten raw CrUX metrics into legacy ``lcp_seconds`` / ``cls`` / ``inp_ms`` keys."""
    out: dict[str, Any] = {}
    lcp = extract_crux_metric(metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True)
    if lcp is not None:
        out["lcp_seconds"] = lcp
    cls_val = extract_crux_metric(metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE")
    if cls_val is not None:
        out["cls"] = cls_val
    inp = extract_crux_metric(metrics, "INTERACTION_TO_NEXT_PAINT")
    if inp is None:
        inp = extract_crux_metric(metrics, "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT")
    if inp is None:
        inp = extract_crux_metric(metrics, "FIRST_INPUT_DELAY_MS")
    if inp is not None:
        out["inp_ms"] = inp
    return out


def field_experience_metrics(
    payload: dict[str, Any],
    requested_url: str = "",
) -> dict[str, Any] | None:
    """Legacy CrUX snapshot helper retained for unit tests and nested ``psi_metrics``."""
    metrics, level = detect_crux_level(payload, requested_url)
    if not metrics:
        return None
    out = parsed_crux_snapshot(metrics)
    if not out:
        return None
    out["crux_data_level"] = (
        "origin" if level == "Origin" else "url" if level == "URL" else "none"
    )
    return out


def apply_crux_columns(
    merged_flat: dict[str, Any],
    *,
    crux_metrics: dict[str, Any] | None,
    crux_level: str,
) -> None:
    """Populate URL-level vs origin-level CrUX columns on the merged PSI flat dict."""
    null_cwv_keys = (
        "CWV LCP (s)",
        "CWV CLS",
        "CWV INP (ms)",
        "CWV FCP (ms)",
        "CWV TTFB (ms)",
        "CrUX LCP Category",
        "CrUX CLS Category",
        "CrUX INP Category",
        "Origin CrUX LCP (s)",
        "Origin CrUX CLS",
        "Origin CrUX INP (ms)",
    )
    for key in null_cwv_keys:
        merged_flat[key] = None

    if crux_level == "URL" and crux_metrics:
        merged_flat["CWV LCP (s)"] = extract_crux_metric(
            crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True
        )
        merged_flat["CWV CLS"] = extract_crux_metric(
            crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE"
        )
        merged_flat["CWV INP (ms)"] = extract_crux_metric(
            crux_metrics, "INTERACTION_TO_NEXT_PAINT"
        )
        if merged_flat["CWV INP (ms)"] is None:
            merged_flat["CWV INP (ms)"] = extract_crux_metric(
                crux_metrics, "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT"
            )
        if merged_flat["CWV INP (ms)"] is None:
            merged_flat["CWV INP (ms)"] = extract_crux_metric(
                crux_metrics, "FIRST_INPUT_DELAY_MS"
            )
        merged_flat["CWV FCP (ms)"] = extract_crux_metric(
            crux_metrics, "FIRST_CONTENTFUL_PAINT_MS"
        )
        merged_flat["CWV TTFB (ms)"] = extract_crux_metric(
            crux_metrics, "EXPERIMENTAL_TIME_TO_FIRST_BYTE"
        )
        merged_flat["CrUX LCP Category"] = extract_crux_category(
            crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS"
        )
        merged_flat["CrUX CLS Category"] = extract_crux_category(
            crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE"
        )
        merged_flat["CrUX INP Category"] = extract_crux_category(
            crux_metrics, "INTERACTION_TO_NEXT_PAINT"
        )
    elif crux_level == "Origin" and crux_metrics:
        merged_flat["Origin CrUX LCP (s)"] = extract_crux_metric(
            crux_metrics, "LARGEST_CONTENTFUL_PAINT_MS", to_seconds=True
        )
        merged_flat["Origin CrUX CLS"] = extract_crux_metric(
            crux_metrics, "CUMULATIVE_LAYOUT_SHIFT_SCORE"
        )
        merged_flat["Origin CrUX INP (ms)"] = extract_crux_metric(
            crux_metrics, "INTERACTION_TO_NEXT_PAINT"
        )
        if merged_flat["Origin CrUX INP (ms)"] is None:
            merged_flat["Origin CrUX INP (ms)"] = extract_crux_metric(
                crux_metrics, "EXPERIMENTAL_INTERACTION_TO_NEXT_PAINT"
            )
        if merged_flat["Origin CrUX INP (ms)"] is None:
            merged_flat["Origin CrUX INP (ms)"] = extract_crux_metric(
                crux_metrics, "FIRST_INPUT_DELAY_MS"
            )


def parse_pagespeed_payload(
    payload: dict[str, Any],
    requested_url: str = "",
) -> dict[str, Any]:
    """Split Lighthouse lab metrics vs CrUX field metrics when present."""
    lab = lab_strategy_metrics(payload)
    field = field_experience_metrics(payload, requested_url)
    return {"lab": lab, "field": field}

def strategy_ok(raw: dict[str, Any]) -> bool:
    return bool(raw and isinstance(raw, dict) and "lighthouseResult" in raw)


def optional_int(raw: int | None) -> int | None:
    return int(raw) if raw is not None else None


def optional_float(raw: float | None) -> float | None:
    return float(raw) if raw is not None else None


def resolve_psi_data_status(
    *,
    mobile_ok: bool,
    desktop_ok: bool,
    has_field: bool,
    mobile_error: str | None,
    desktop_error: str | None,
) -> str:
    if mobile_ok and desktop_ok:
        return "Complete (Lab + Field)" if has_field else "Lab only"
    if mobile_ok and not desktop_ok:
        detail = f": {desktop_error}" if desktop_error else ""
        return f"Partial (desktop unavailable{detail})"
    if desktop_ok and not mobile_ok:
        detail = f": {mobile_error}" if mobile_error else ""
        return f"Partial (mobile unavailable{detail})"
    parts: list[str] = []
    if mobile_error:
        parts.append(f"mobile: {mobile_error}")
    if desktop_error:
        parts.append(f"desktop: {desktop_error}")
    if parts:
        return "Unavailable (" + "; ".join(parts) + ")"
    return "Unavailable"


def resolve_cwv_labelling(
    *,
    has_lab: bool,
    crux_level: str,
) -> tuple[str, str, str]:
    """Return ``(PSI Data Status, Field vs Lab, CWV Data Source)``."""
    if crux_level == "URL":
        if has_lab:
            return (
                "PSI + CrUX Field (URL)",
                "Field (URL-level CrUX)",
                "CrUX API (URL-level)",
            )
        return (
            "CrUX Field (URL)",
            "Field (URL-level CrUX)",
            "CrUX API (URL-level)",
        )

    if crux_level == "Origin":
        if has_lab:
            return (
                "PSI + CrUX Field (Origin)",
                "Lab (Origin CrUX available)",
                "CrUX API (Origin-level)",
            )
        return (
            "CrUX Field (Origin)",
            "Field (Origin)",
            "CrUX API (Origin-level)",
        )

    if has_lab:
        return ("PSI Lab", "Lab only", "None")

    return ("Not available", "N/A", "None")

def merge_url_results(
    target_url: str,
    mobile_raw: dict[str, Any],
    desktop_raw: dict[str, Any],
    *,
    mobile_error: str | None = None,
    desktop_error: str | None = None,
) -> dict[str, Any]:
    mobile_ok = strategy_ok(mobile_raw)
    desktop_ok = strategy_ok(desktop_raw)

    mobile = (
        parse_pagespeed_payload(mobile_raw, target_url)
        if mobile_ok
        else {"lab": {}, "field": None}
    )
    desktop = (
        parse_pagespeed_payload(desktop_raw, target_url)
        if desktop_ok
        else {"lab": {}, "field": None}
    )

    m_lab = mobile["lab"] or {}
    d_lab = desktop["lab"] or {}

    crux_metrics: dict[str, Any] | None = None
    crux_level = "None"
    for raw in (mobile_raw, desktop_raw):
        if isinstance(raw, dict) and raw:
            crux_metrics, crux_level = detect_crux_level(raw, target_url)
            if crux_level != "None":
                break
    else:
        crux_metrics, crux_level = None, "None"
    field_mobile = mobile.get("field")
    if crux_level == "URL" and crux_metrics:
        field_mobile = parsed_crux_snapshot(crux_metrics)
        field_mobile["crux_data_level"] = "url"
    elif crux_level == "Origin" and crux_metrics:
        field_mobile = parsed_crux_snapshot(crux_metrics)
        field_mobile["crux_data_level"] = "origin"

    has_lab = mobile_ok or desktop_ok
    has_crux = crux_level in {"URL", "Origin"} and bool(crux_metrics)

    if has_lab or has_crux:
        psi_data_status, field_vs_lab, cwv_source = resolve_cwv_labelling(
            has_lab=has_lab,
            crux_level=crux_level,
        )
    else:
        psi_data_status = resolve_psi_data_status(
            mobile_ok=mobile_ok,
            desktop_ok=desktop_ok,
            has_field=False,
            mobile_error=mobile_error,
            desktop_error=desktop_error,
        )
        field_vs_lab = "N/A"
        cwv_source = "None"

    lab_mobile_inp = m_lab.get("inp_ms")
    lab_desktop_inp = d_lab.get("inp_ms")

    merged_flat: dict[str, Any] = {
        "URL": target_url,
        "PSI Data Status": psi_data_status,
        "CrUX Level": crux_level,
        "Desktop Score": optional_int(d_lab.get("performance_score")) if desktop_ok else None,
        "Mobile Score": optional_int(m_lab.get("performance_score")) if mobile_ok else None,
        "Desktop SEO Score": optional_int(d_lab.get("seo_score")) if desktop_ok else None,
        "Mobile SEO Score": optional_int(m_lab.get("seo_score")) if mobile_ok else None,
        "Mobile LCP": optional_float(m_lab.get("lcp_seconds")) if mobile_ok else None,
        "Mobile CLS": optional_float(m_lab.get("cls")) if mobile_ok else None,
        "Mobile TTFB": (
            round(float(m_lab["ttfb_seconds"]), 3)
            if mobile_ok and m_lab.get("ttfb_seconds") is not None
            else None
        ),
        "Desktop LCP": optional_float(d_lab.get("lcp_seconds")) if desktop_ok else None,
        "Desktop CLS": optional_float(d_lab.get("cls")) if desktop_ok else None,
        "Desktop TTFB": (
            round(float(d_lab["ttfb_seconds"]), 3)
            if desktop_ok and d_lab.get("ttfb_seconds") is not None
            else None
        ),
        "Lab Mobile INP (ms)": optional_float(lab_mobile_inp) if mobile_ok else None,
        "Lab Desktop INP (ms)": optional_float(lab_desktop_inp) if desktop_ok else None,
        "Field Mobile LCP (s)": (
            field_mobile.get("lcp_seconds") if field_mobile and crux_level == "URL" else None
        ),
        "Field Mobile CLS": (
            field_mobile.get("cls") if field_mobile and crux_level == "URL" else None
        ),
        "Field Mobile INP (ms)": (
            field_mobile.get("inp_ms") if field_mobile and crux_level == "URL" else None
        ),
        "has_field_crux": has_crux,
        "Field vs Lab": field_vs_lab,
        "CWV Data Source": cwv_source,
        "psi_metrics": {
            "lab": {"mobile": m_lab, "desktop": d_lab},
            "field": {"mobile": field_mobile} if field_mobile else None,
        },
    }
    apply_crux_columns(merged_flat, crux_metrics=crux_metrics, crux_level=crux_level)
    apply_lighthouse_extraction(
        merged_flat,
        mobile_raw=mobile_raw,
        desktop_raw=desktop_raw,
        mobile_ok=mobile_ok,
        desktop_ok=desktop_ok,
    )
    network_source = mobile_raw if mobile_ok else desktop_raw if desktop_ok else {}
    network_items, blocking_urls = extract_psi_network_payload(network_source)
    merged_flat["PSI Network Items"] = network_items
    merged_flat["PSI Render Blocking URLs"] = blocking_urls
    return merged_flat


def store_psi_result(results: dict[str, dict[str, Any]], target_url: str, merged: dict[str, Any]) -> None:
    """Index PSI rows under raw and normalized URL keys for enrichment lookup."""
    results[target_url] = merged
    norm = psi_index_key(target_url)
    if norm and norm != target_url:
        results[norm] = merged

