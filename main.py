from __future__ import annotations

import asyncio
import os
import re
import shutil
from collections import defaultdict
from datetime import datetime
import math
from urllib.parse import urlparse

import numpy as np
import pandas as pd

from checkpoint import AuditCache, load_checkpoint, save_checkpoint
from config import (
    DEFAULT_EFFORT_BY_SEVERITY,
    DEFAULT_OWNER_BY_SEVERITY,
    MAX_RETRIES,
    MAX_WORKERS,
    TIMEOUT_SECONDS,
    DELAY_BETWEEN_REQUESTS,
)
from crawler import (
    check_url_status_light_limited,
    create_session,
    fetch_psi_metrics_batch,
    fetch_and_parse,
    parse_sitemap,
)
from models import CrawlResult
from reporters import adjust_sheet_format, apply_tab_hyperlinks
from reporters.tabs import (
    build_content_optimization_hub_rows,
    build_fixplan_rows,
    load_cached_rows,
    write_dict_rows_sheet,
)
from rules import (
    get_summary_rules,
    owner_for_issue,
    root_cause_and_fix,
    score_url_health,
    stable_issue_id,
    workflow_metrics_for_issue,
)
from utils import build_output_filename, normalize_text_hash, sanitize_filename_part


_ILLEGAL_XLSX_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
_INVALID_SHEET_CHARS_RE = re.compile(r"[:\\/*?\[\]]")


def _sanitize_excel_string(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _ILLEGAL_XLSX_CHARS_RE.sub("", value)


def _sanitize_excel_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (float, np.floating)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return ""
    if isinstance(value, str):
        return _sanitize_excel_string(value)
    return value


def _sanitize_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    sanitized: list[dict[str, object]] = []
    for row in rows:
        sanitized.append({k: _sanitize_excel_value(v) for k, v in row.items()})
    return sanitized


def _sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    clean_df = df.copy()
    clean_df = clean_df.replace([np.inf, -np.inf], np.nan)
    clean_df = clean_df.fillna("")
    for col in clean_df.columns:
        if pd.api.types.is_datetime64tz_dtype(clean_df[col].dtype):
            clean_df[col] = clean_df[col].dt.tz_localize(None).astype(str)
            clean_df[col] = clean_df[col].replace("NaT", "")
            continue
        if pd.api.types.is_datetime64_any_dtype(clean_df[col].dtype):
            clean_df[col] = clean_df[col].astype(str).replace("NaT", "")
            continue
        if pd.api.types.is_object_dtype(clean_df[col].dtype) or pd.api.types.is_string_dtype(clean_df[col].dtype):
            parsed_dt = pd.to_datetime(clean_df[col], errors="coerce", utc=True)
            if parsed_dt.notna().any():
                clean_df[col] = parsed_dt.dt.tz_localize(None).astype(str).replace("NaT", "")
                continue
            clean_df[col] = clean_df[col].map(_sanitize_excel_value)
    return clean_df


def _safe_sheet_name(name: str) -> str:
    sanitized = _INVALID_SHEET_CHARS_RE.sub("_", str(name or "Sheet"))
    sanitized = sanitized[:31]
    return sanitized or "Sheet"


def _to_excel_safe(df: pd.DataFrame, writer: pd.ExcelWriter, sheet_name: str, **kwargs) -> None:
    safe_df = _sanitize_dataframe(df)
    safe_df.columns = [str(col).replace("\n", " ").replace("\r", " ").strip()[:255] or f"Column_{idx + 1}" for idx, col in enumerate(safe_df.columns)]
    safe_df.to_excel(writer, sheet_name=_safe_sheet_name(sheet_name), **kwargs)


async def main() -> None:
    print("=== Python Technical SEO Auditor ===")
    print("1. Read URLs from a Sitemap (XML)")
    print("2. Read URLs from a local text file")
    choice = input("Select input method (1 or 2): ").strip()
    urls: list[str] = []
    sitemap_meta: dict[str, dict[str, str | None]] = {}
    workers = MAX_WORKERS
    request_delay = DELAY_BETWEEN_REQUESTS
    source_label = "manual_input"

    async with create_session() as session:
        if choice == "1":
            sitemap_url = input("Enter the full Sitemap URL (e.g., https://example.com/sitemap.xml): ").strip()
            urls, sitemap_meta = await parse_sitemap(sitemap_url, session)
            parsed_source = urlparse(sitemap_url)
            source_label = parsed_source.netloc or "sitemap"
        elif choice == "2":
            file_path = input("Enter the file path (e.g., urls.txt): ").strip()
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    urls = [line.strip() for line in f if line.strip()]
                print(f"Loaded {len(urls)} URLs from {file_path}.")
                source_label = os.path.splitext(os.path.basename(file_path))[0]
            else:
                print("File not found.")
                return
        else:
            print("Invalid choice. Exiting.")
            return

        if not urls:
            print("No URLs to crawl. Exiting.")
            return

        original_count = len(urls)
        urls = list(dict.fromkeys(urls))
        if len(urls) != original_count:
            print(f"Removed {original_count - len(urls)} duplicate URLs.")

        print("\nCrawl safety profile:")
        print("1. Gentle (fewer workers, longer delay)")
        print("2. Balanced (default)")
        print("3. Faster (more workers, shorter delay)")
        profile_choice = input("Select crawl profile (1, 2, or 3): ").strip()
        if profile_choice == "1":
            workers = 2
            request_delay = 4.0
        elif profile_choice == "3":
            workers = 4
            request_delay = 1.5

        suite_choice = input("Run mode - 1) Main tab only  2) Full SEO suite (all tabs): ").strip()
        full_suite = suite_choice == "2"
        previous_audit_path = input("Optional previous audit .xlsx path for comparison (leave blank to skip): ").strip()
        output_filename = os.getenv("HF_OUTPUT_FILENAME") or build_output_filename(source_label, full_suite)
        checkpoint_file = output_filename.replace(".xlsx", "_checkpoint.json")
        cache_file = output_filename.replace(".xlsx", "_temp_cache.db")
        cache = AuditCache(cache_file)
        flush_batch_size = 250
        output_dir = os.path.dirname(output_filename)
        os.makedirs(output_dir, exist_ok=True)

        print(f"Output file: {output_filename}")
        print(f"\nStarting crawl of {len(urls)} URLs...")
        print(
            f"Max Workers: {workers} | Delay: {request_delay}s | "
            f"Retries: {MAX_RETRIES} | Timeout: {TIMEOUT_SECONDS}s | "
            f"Mode: {'Full Suite' if full_suite else 'Main Only'}"
        )
        checkpoint_raw = input("Checkpoint save every N completed URLs (0 to disable): ").strip()
        try:
            checkpoint_every = int(checkpoint_raw or "0")
        except ValueError:
            checkpoint_every = 0

        semaphore = asyncio.Semaphore(workers)
        robots_cache: dict[str, dict[str, object]] = {}
        resumed_results: list[CrawlResult] = []
        checkpoint_completed_urls: set[str] = set()
        if os.path.exists(checkpoint_file):
            resume_choice = input("Checkpoint found for this source. Resume from checkpoint? (y/N): ").strip().lower()
            if resume_choice in {"y", "yes"}:
                try:
                    resumed_results, checkpoint_completed_urls = load_checkpoint(checkpoint_file)
                    cache.upsert_results(resumed_results)
                    urls = [u for u in urls if u not in checkpoint_completed_urls]
                    print(f"Resuming crawl. Completed: {len(checkpoint_completed_urls)} | Remaining: {len(urls)}")
                except Exception as e:
                    print(f"Could not load checkpoint. Starting fresh. ({e})")
                    resumed_results = []
                    checkpoint_completed_urls = set()

        tasks = [
            asyncio.create_task(
                fetch_and_parse(
                    url, session, semaphore, full_suite, robots_cache, request_delay, sitemap_meta
                )
            )
            for url in urls
        ]

        completed_urls_runtime = set(checkpoint_completed_urls)
        pending_batch: list[CrawlResult] = []
        crawled_count = len(checkpoint_completed_urls)
        total_urls = len(urls) + len(checkpoint_completed_urls)
        for done_task in asyncio.as_completed(tasks):
            result = await done_task
            pending_batch.append(result)
            crawled_count += 1
            url_done = result.get("main", {}).get("URL")
            if url_done:
                completed_urls_runtime.add(url_done)
            if len(pending_batch) >= flush_batch_size:
                cache.upsert_results(pending_batch)
                pending_batch = []
            done_count = crawled_count
            if checkpoint_every > 0 and done_count % checkpoint_every == 0:
                if pending_batch:
                    cache.upsert_results(pending_batch)
                    pending_batch = []
                checkpoint_results = cache.all_results()
                save_checkpoint(checkpoint_file, checkpoint_results, urls, checkpoint_completed_urls)
                print(f"Checkpoint saved: {done_count}/{total_urls} -> {checkpoint_file}")
        if pending_batch:
            cache.upsert_results(pending_batch)
        if checkpoint_every > 0:
            checkpoint_results = cache.all_results()
            save_checkpoint(checkpoint_file, checkpoint_results, urls, checkpoint_completed_urls)

        print("\nGenerating Excel report...")
        main_rows, extra_rows = load_cached_rows(cache)
        psi_map = await fetch_psi_metrics_batch(
            session,
            [str(r.get("URL") or "") for r in extra_rows if r.get("URL")],
        )
        for row in extra_rows:
            url_key = str(row.get("URL") or "")
            psi = psi_map.get(url_key)
            if psi:
                row["CWV LCP (s)"] = psi.get("CWV LCP (s)")
                row["CWV INP (ms)"] = psi.get("CWV INP (ms)")
                row["CWV CLS"] = psi.get("CWV CLS")
                row["CWV Data Source"] = psi.get("CWV Data Source")
                row["Field vs Lab"] = psi.get("Field vs Lab")

        status_by_url: dict[str, object] = {}
        for row in extra_rows:
            if row.get("Final URL"):
                status_by_url[str(row["Final URL"]).rstrip("/")] = row.get("Status Code")
            if row.get("URL"):
                status_by_url[str(row["URL"]).rstrip("/")] = row.get("Status Code")

        unresolved_targets = set()
        for row in extra_rows:
            for target in row.get("Internal Links List Full", []):
                if target.rstrip("/") not in status_by_url:
                    unresolved_targets.add(target)
        if unresolved_targets:
            print(f"Running lightweight status checks for {len(unresolved_targets)} internal links not in crawl set...")
            link_check_semaphore = asyncio.Semaphore(min(20, max(5, workers * 3)))
            checked_statuses = await asyncio.gather(*[
                check_url_status_light_limited(session, t, link_check_semaphore) for t in unresolved_targets
            ])
            for target, status in zip(unresolved_targets, checked_statuses):
                status_by_url[target.rstrip("/")] = status

        crawled_finals = {str(row.get("Final URL")).rstrip("/") for row in extra_rows if row.get("Final URL")}
        for row in extra_rows:
            canonical_url = row.get("Canonical URL")
            if canonical_url and row.get("URL"):
                row["Canonical in Sitemap Match"] = canonical_url.rstrip("/") == str(row["URL"]).rstrip("/")
            row["Hreflang Canonical Consistency"] = (bool(row.get("Hreflang Present")) and row.get("Canonical Type") in {"self", "missing"}) if row.get("Hreflang Present") else None
            if row.get("Hreflang Present"):
                row["Hreflang Reciprocal Check"] = str(row.get("Final URL", "")).rstrip("/") in crawled_finals and bool(row.get("Hreflang Self Reference"))
            broken_internal = 0
            unresolved_internal = 0
            link_statuses: list[str] = []
            for target in row.get("Internal Links List Full", []):
                status = status_by_url.get(target.rstrip("/"))
                if isinstance(status, int) and status >= 400:
                    broken_internal += 1
                elif status is None:
                    unresolved_internal += 1
                link_statuses.append(f"{target} => {status if status is not None else 'Not crawled'}")
            row["Broken Internal Links Count"] = broken_internal
            row["Unresolved Internal Links Count"] = unresolved_internal
            row["Internal Link Statuses"] = " | ".join(link_statuses) if link_statuses else None

        inlinks_map: defaultdict[str, set[str]] = defaultdict(set)
        crawled_set = {str((row.get("Final URL") or row.get("URL") or "")).rstrip("/") for row in extra_rows if (row.get("Final URL") or row.get("URL"))}
        for row in extra_rows:
            source = str((row.get("Final URL") or row.get("URL") or "")).rstrip("/")
            for target in row.get("Internal Links List", []):
                t_norm = str(target).rstrip("/")
                if t_norm in crawled_set and source:
                    inlinks_map[t_norm].add(source)

        title_map: defaultdict[str, list[str]] = defaultdict(list)
        meta_map: defaultdict[str, list[str]] = defaultdict(list)
        segment_by_url: dict[str, str] = {}
        for mrow in main_rows:
            t_key = normalize_text_hash(mrow.get("Title"))
            d_key = normalize_text_hash(mrow.get("Meta Description"))
            parsed_u = urlparse(str(mrow.get("URL") or ""))
            segs = [s for s in parsed_u.path.strip("/").split("/") if s]
            segment_by_url[mrow.get("URL")] = segs[0] if segs else "(home)"
            if t_key:
                title_map[t_key].append(mrow.get("URL"))
            if d_key:
                meta_map[d_key].append(mrow.get("URL"))

        summary_rules = get_summary_rules()
        score_by_url: dict[str, dict[str, object]] = {}
        for row in extra_rows:
            score, badge, icon, matched = score_url_health(row, summary_rules)
            row["SEO Health Score"] = score
            row["Severity Badge"] = badge
            row["Health Icon"] = icon
            row["Critical Issues Count"] = len(matched["Critical"])
            row["Warning Issues Count"] = len(matched["Warning"])
            row["Observation Issues Count"] = len(matched["Observation"])
            row["Matched Issues"] = " | ".join(matched["Critical"] + matched["Warning"] + matched["Observation"])
            row["Action Needed"] = "Yes" if badge in {"Critical", "Warning"} else "No"
            top_issue = (matched["Critical"] + matched["Warning"] + matched["Observation"])[0] if (matched["Critical"] + matched["Warning"] + matched["Observation"]) else ""
            row["Owner"] = owner_for_issue(top_issue, badge)
            row["Sprint"] = ""
            row["Status"] = "Open"
            all_issue_ids = [stable_issue_id(row.get("URL"), issue) for issue in matched["Critical"] + matched["Warning"] + matched["Observation"]]
            row["Stable Issue IDs"] = " | ".join(all_issue_ids) if all_issue_ids else None
            final_norm = str((row.get("Final URL") or row.get("URL") or "")).rstrip("/")
            inlinks_count = len(inlinks_map.get(final_norm, set()))
            row["Inlinks Bucket"] = "0" if inlinks_count == 0 else "1-2" if inlinks_count <= 2 else "3-10" if inlinks_count <= 10 else "10+"
            row["Important But Underlinked"] = score < 70 and inlinks_count <= 2
            url_for_hint = row.get("URL")
            title_key = normalize_text_hash(next((m.get("Title") for m in main_rows if m.get("URL") == url_for_hint), None))
            meta_key = normalize_text_hash(next((m.get("Meta Description") for m in main_rows if m.get("URL") == url_for_hint), None))
            hints: list[str] = []
            if title_key and len(title_map.get(title_key, [])) > 1:
                hints.append("Near-duplicate title cluster")
                seg_set = {segment_by_url.get(u) for u in title_map.get(title_key, []) if segment_by_url.get(u)}
                if len(seg_set) == 1:
                    hints.append("Shared path segment pattern")
            if meta_key and len(meta_map.get(meta_key, [])) > 1:
                hints.append("Near-duplicate meta description cluster")
            if hints:
                row["Cannibalization Hint"] = " | ".join(hints)
            if row.get("URL"):
                score_by_url[row["URL"]] = {"score": score, "badge": badge, "icon": icon}

        for mrow in main_rows:
            score_data = score_by_url.get(mrow.get("URL"), {})
            mrow["SEO Health Score"] = score_data.get("score")
            mrow["Severity Badge"] = score_data.get("badge")
            mrow["Health Icon"] = score_data.get("icon")
            extra_match = next((e for e in extra_rows if e.get("URL") == mrow.get("URL")), {})
            mrow["CWV LCP (s)"] = extra_match.get("CWV LCP (s)")
            mrow["CWV INP (ms)"] = extra_match.get("CWV INP (ms)")
            mrow["CWV CLS"] = extra_match.get("CWV CLS")
            mrow["Field vs Lab"] = extra_match.get("Field vs Lab")
            mrow["Regional Authority Score"] = extra_match.get("Regional Authority Score")

        main_df = pd.DataFrame(main_rows)
        main_by_url = {str(r.get("URL") or "").strip(): r for r in main_rows if r.get("URL")}

        prev_issue_ids: set[str] = set()
        prev_counts: dict[str, int] = {}
        prev_fixed_issue_ids: set[str] = set()
        previous_issue_inventory_df = pd.DataFrame()
        previous_audit_exists = bool(previous_audit_path) and os.path.exists(previous_audit_path)
        if previous_audit_exists:
            try:
                prev_xls = pd.ExcelFile(previous_audit_path)
                if "IssueInventory" in prev_xls.sheet_names:
                    previous_issue_inventory_df = pd.read_excel(previous_audit_path, sheet_name="IssueInventory")
                    if "Stable Issue ID" in previous_issue_inventory_df.columns:
                        prev_issue_ids = {
                            str(v).strip()
                            for v in previous_issue_inventory_df["Stable Issue ID"].dropna().tolist()
                            if str(v).strip()
                        }
                        if "Status" in previous_issue_inventory_df.columns:
                            prev_fixed_issue_ids = {
                                str(row.get("Stable Issue ID")).strip()
                                for _, row in previous_issue_inventory_df.iterrows()
                                if str(row.get("Stable Issue ID", "")).strip()
                                and str(row.get("Status", "")).strip().lower() in {"fixed", "done", "closed"}
                            }
                    else:
                        print("Previous audit IssueInventory is missing 'Stable Issue ID'. Delta compare will mark all current issues as New.")
                else:
                    print("Previous audit is missing 'IssueInventory'. Delta compare will mark all current issues as New.")
                if "Summary" in prev_xls.sheet_names:
                    prev_summary = pd.read_excel(previous_audit_path, sheet_name="Summary")
                    for _, srow in prev_summary.iterrows():
                        if str(srow.get("Section", "")) == "Issue Counts":
                            prev_counts[str(srow.get("Issue", ""))] = int(srow.get("Affected URL Count", 0) or 0)
            except Exception as exc:
                print(f"Could not parse previous audit for compare: {exc}")
                prev_issue_ids = set()
                prev_counts = {}
                prev_fixed_issue_ids = set()
                previous_issue_inventory_df = pd.DataFrame()
        elif previous_audit_path:
            print(f"Previous audit file not found: {previous_audit_path}. Delta compare will mark all current issues as New.")

        main_rows = _sanitize_rows(main_rows)
        extra_rows = _sanitize_rows(extra_rows)
        writer = None
        try:
            writer = pd.ExcelWriter(output_filename, engine="openpyxl")
            main_cols = list(main_rows[0].keys()) if main_rows else []
            write_dict_rows_sheet(writer, "Main", main_cols, main_rows)
            adjust_sheet_format(writer, "Main")
            if full_suite:
                technical_cols = ["URL", "Health Icon", "Severity Badge", "SEO Health Score", "Action Needed", "Owner", "Sprint", "Status", "Status Code", "Final URL", "Protocol", "Redirect Chain Length", "Redirect Target", "Redirect Hops", "HTTP->HTTPS Redirect", "Status Class", "TTFB (ms)", "Total Request Time (ms)", "Content-Type", "HTTP Version", "HTML Size (KB)", "Compression Enabled", "Cache-Control", "ETag", "X-Robots-Tag", "Meta Robots Raw", "Canonical URL", "Canonical Matches Final URL", "Canonical Type", "Canonical Absolute URL", "Canonical in Sitemap Match", "Hreflang Present", "Hreflang Count", "Hreflang Self Reference", "Hreflang Reciprocal Check", "Hreflang Canonical Consistency", "x-default Present", "Pagination rel=next", "Pagination rel=prev", "Last-Modified", "Published Date", "Modified Date", "Last Updated", "Change Frequency", "Priority", "Indexability Reason", "AI Crawlers Allowed (GPTBot/ClaudeBot/PerplexityBot)", "llms.txt Present", "CWV LCP (s)", "CWV INP (ms)", "CWV CLS", "CWV Data Source", "Field vs Lab", "Regional Authority Score", "Regional Entity Hits", "Answer Block Detected (First 60 Words)", "AEO Extractability Score", "Critical Issues Count", "Warning Issues Count", "Observation Issues Count", "Inlinks Bucket", "Important But Underlinked", "SERP Title Truncation Risk", "SERP Meta Truncation Risk", "SERP Title Pixel Approx", "SERP Meta Pixel Approx", "Cannibalization Hint", "Stable Issue IDs", "URL Depth", "Param URL Flag"]
                content_cols = ["URL", "H1 Count", "Missing H1 Flag", "Multiple H1 Flag", "Title Missing", "Meta Description Missing", "Word Count", "Word Count Band", "Sentence Count", "Body Text-to-HTML Ratio", "Readability (Rough Flesch)", "Thin Content Flag"]
                links_cols = ["URL", "Internal Links Count", "Unique Internal Links Count", "External Links Count", "Nofollow Internal Links Count", "Nofollow External Links Count", "Generic Anchor Text Count", "Broken Internal Links Count", "Unresolved Internal Links Count", "Internal Link Statuses"]
                media_cols = ["URL", "Image Count", "Images", "Images Missing Alt", "Image Alt Coverage (%)", "Image Extension Distribution", "Likely Large Image Count", "Image Filename Quality Issues", "Image On Canonical Domain (%)", "Mixed Content Detected"]
                schema_cols = ["URL", "Schema Types Found", "Schema Types Count", "Schema Parse Errors", "OG Title", "OG Description", "OG Image", "Open Graph Complete", "Twitter Card Type"]
                aeo_cols = [
                    "URL",
                    "AEO Badge",
                    "AEO Readiness Score",
                    "Why It Matters",
                    "FAQ Section Count",
                    "Question Heading Count",
                    "QAPage/FAQ Schema Present",
                    "Speakable Schema Present",
                    "HowTo Signal",
                    "Definition Signal",
                    "List/Table Answer Signal",
                    "Paragraphs 40-60 Words Count",
                    "Answer Block Detected (First 60 Words)",
                    "AEO Extractability Score",
                    "Snippet Preview Mockup",
                    "Title Missing",
                    "Meta Description Missing",
                ]
                security_cols = ["URL", "Strict-Transport-Security", "Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Permissions-Policy", "Robots.txt Accessible", "Sitemap in Robots.txt", "Robots.txt Crawl-Delay", "Robots.txt Disallow /"]
                write_dict_rows_sheet(writer, "Technical", technical_cols, extra_rows)
                write_dict_rows_sheet(writer, "Content", content_cols, extra_rows)
                write_dict_rows_sheet(writer, "Links", links_cols, extra_rows)
                write_dict_rows_sheet(writer, "Media", media_cols, extra_rows)
                write_dict_rows_sheet(writer, "Schema & Metadata", schema_cols, extra_rows)
                aeo_rows = _build_aeo_rows(extra_rows)
                write_dict_rows_sheet(writer, "AEO", aeo_cols, aeo_rows)
                aioseo_rows = _build_aioseo_rows(extra_rows, main_by_url, DEFAULT_OWNER_BY_SEVERITY)
                aioseo_cols = [
                    "URL",
                    "WordPress Post ID",
                    "Direct Edit Link",
                    "AIOSEO Panel",
                    "Severity",
                    "Issue",
                    "Current Value",
                    "Recommended Target",
                    "Why It Matters",
                    "How to Fix in AIOSEO",
                    "Reference Tab",
                    "Reference Field",
                    "Action Needed",
                    "Owner",
                    "Status",
                    "Priority Score",
                    "Est. Hours",
                    "Stable Issue ID",
                ]
                write_dict_rows_sheet(writer, "AIOSEO", aioseo_cols, aioseo_rows)
                write_dict_rows_sheet(writer, "Security", security_cols, extra_rows)
                indexability_cols = ["URL", "Status Code", "Status Class", "Final URL", "Indexability Reason", "Meta Robots Raw", "X-Robots-Tag", "Canonical URL", "Canonical Type", "Canonical Matches Final URL", "Canonical in Sitemap Match"]
                write_dict_rows_sheet(writer, "Indexability", indexability_cols, extra_rows)
                redirects_rows = []
                for r in extra_rows:
                    redirects_rows.append(
                        {
                            "URL": r.get("URL"),
                            "Status Code": r.get("Status Code"),
                            "Final URL": r.get("Final URL"),
                            "Redirect Chain Length": r.get("Redirect Chain Length"),
                            "Redirect Target": r.get("Redirect Target"),
                            "Redirect Hops": r.get("Redirect Hops"),
                            "HTTP->HTTPS Redirect": r.get("HTTP->HTTPS Redirect"),
                            "Redirect Loop Flag": (
                                isinstance(r.get("Redirect Hops"), str)
                                and str(r.get("URL", "")).rstrip("/") == str(r.get("Final URL", "")).rstrip("/")
                                and int(r.get("Redirect Chain Length") or 0) > 0
                            ),
                        }
                    )
                write_dict_rows_sheet(
                    writer,
                    "Redirects",
                    ["URL", "Status Code", "Final URL", "Redirect Chain Length", "Redirect Target", "Redirect Hops", "HTTP->HTTPS Redirect", "Redirect Loop Flag"],
                    redirects_rows,
                )
                link_rows = []
                for row in extra_rows:
                    for item in row.get("Link Details", []):
                        target_status = status_by_url.get(str(item.get("Target URL", "")).rstrip("/"))
                        item["Target Status (if crawled)"] = target_status
                        item["Crawlable"] = target_status is None or (isinstance(target_status, int) and target_status < 400)
                        link_rows.append(item)
                _to_excel_safe(pd.DataFrame(link_rows), writer, "LinksDetail", index=False)
                title_groups: defaultdict[str, list[str]] = defaultdict(list)
                desc_groups: defaultdict[str, list[str]] = defaultdict(list)
                for row in main_rows:
                    t_key = normalize_text_hash(row.get("Title"))
                    d_key = normalize_text_hash(row.get("Meta Description"))
                    if t_key:
                        title_groups[t_key].append(row.get("URL"))
                    if d_key:
                        desc_groups[d_key].append(row.get("URL"))
                duplicate_rows = []
                for row in main_rows:
                    t_key = normalize_text_hash(row.get("Title"))
                    d_key = normalize_text_hash(row.get("Meta Description"))
                    duplicate_rows.append({"URL": row.get("URL"), "Title Duplicate Count": len(title_groups.get(t_key, [])) if t_key else 0, "Meta Description Duplicate Count": len(desc_groups.get(d_key, [])) if d_key else 0, "Title Duplicate URLs": " | ".join(title_groups.get(t_key, [])) if t_key and len(title_groups.get(t_key, [])) > 1 else None, "Meta Duplicate URLs": " | ".join(desc_groups.get(d_key, [])) if d_key and len(desc_groups.get(d_key, [])) > 1 else None})
                _to_excel_safe(pd.DataFrame(duplicate_rows), writer, "Duplicates", index=False)
                cluster_groups: defaultdict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
                for row in extra_rows:
                    final_url = row.get("Final URL") or row.get("URL")
                    if not final_url:
                        continue
                    parsed = urlparse(str(final_url))
                    segs = [s for s in parsed.path.strip("/").split("/") if s]
                    first_seg = segs[0] if segs else "(home)"
                    title = next((m.get("Title") for m in main_rows if m.get("URL") == row.get("URL")), None)
                    title_pattern = re.sub(r"\d+", "{n}", normalize_text_hash(title))[:80] if normalize_text_hash(title) else "(no-title)"
                    cluster_groups[(first_seg, title_pattern)].append(row)
                cluster_rows = []
                template_issue_counts: defaultdict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
                for (seg, pattern), urls_in_group in sorted(cluster_groups.items(), key=lambda x: len(x[1]), reverse=True):
                    url_list = [u.get("URL") for u in urls_in_group if u.get("URL")]
                    critical_count = sum(1 for u in urls_in_group if (u.get("Critical Issues Count") or 0) > 0)
                    warning_count = sum(1 for u in urls_in_group if (u.get("Critical Issues Count") or 0) == 0 and (u.get("Warning Issues Count") or 0) > 0)
                    for u in urls_in_group:
                        for issue in str(u.get("Matched Issues") or "").split(" | "):
                            if issue:
                                template_issue_counts[seg][issue] += 1
                    dominant_issue = max(template_issue_counts[seg].items(), key=lambda x: x[1])[0] if template_issue_counts[seg] else None
                    suggested_fix = root_cause_and_fix(dominant_issue)[1] if dominant_issue else None
                    avg_score = round(sum([(u.get("SEO Health Score") or 0) for u in urls_in_group]) / max(1, len(urls_in_group)), 2)
                    cluster_rows.append({"Path Segment": seg, "Title Pattern": pattern, "URL Count": len(url_list), "Cluster Health Score Avg": avg_score, "% with Critical": round((critical_count / max(1, len(url_list))) * 100, 2), "% with Warnings": round((warning_count / max(1, len(url_list))) * 100, 2), "Dominant Issue Type": dominant_issue, "Suggested Template Fix": suggested_fix, "URLs": " | ".join(url_list[:30])})
                _to_excel_safe(pd.DataFrame(cluster_rows), writer, "TemplateClusters", index=False)
                summary_rows = []
                aeo_issue_names = {"Low AEO Readiness Score", "Missing FAQ/QA Schema", "No Question Headings", "No Answer-Friendly Structure", "No 40-60 Word Answer Paragraphs"}
                summary_rows.append({"Section": "Issue Counts", "Severity": None, "Issue": None, "Affected URL Count": None, "Affected URLs (sample)": None})
                for severity, issue_name, rule_fn in summary_rules:
                    affected_urls = [row.get("URL") for row in extra_rows if _safe_rule(rule_fn, row)]
                    summary_rows.append({"Section": "Issue Counts", "Severity": severity, "Issue": issue_name, "Affected URL Count": len(affected_urls), "Reference Tab": "Indexability" if "Canonical" in issue_name or "Noindex" in issue_name else "Links" if "Links" in issue_name else "AEO" if "AEO" in issue_name or "Question" in issue_name or "FAQ" in issue_name else "Technical", "Affected URLs (sample)": " | ".join([u for u in affected_urls[:25] if u]) + " || Full list: see Technical/Links/Indexability tabs"})
                summary_rows.append({"Section": "AEO Opportunities", "Severity": None, "Issue": None, "Affected URL Count": None, "Affected URLs (sample)": "Detailed rows: see AEO tab"})
                for severity, issue_name, rule_fn in summary_rules:
                    if issue_name not in aeo_issue_names:
                        continue
                    affected_urls = [row.get("URL") for row in extra_rows if _safe_rule(rule_fn, row)]
                    summary_rows.append({"Section": "AEO Opportunities", "Severity": severity, "Issue": issue_name, "Affected URL Count": len(affected_urls), "Reference Tab": "AEO", "Affected URLs (sample)": " | ".join([u for u in affected_urls[:25] if u]) + " || Full list: see AEO tab"})
                severity_order = {"Critical": 0, "Warning": 1, "Observation": 2}
                summary_rows = sorted(summary_rows, key=lambda x: (x.get("Section", ""), severity_order.get(x.get("Severity", ""), 99), -(x.get("Affected URL Count") or 0), x.get("Issue", "")))
                summary_rows.append({"Section": "Top 10 Critical URLs", "Severity": None, "Issue": None, "Affected URL Count": None, "Affected URLs (sample)": None})
                critical_urls = sorted([r for r in extra_rows if (r.get("Critical Issues Count") or 0) > 0], key=lambda r: (-(r.get("Critical Issues Count") or 0), r.get("SEO Health Score") or 100))[:10]
                for idx, row in enumerate(critical_urls, start=1):
                    summary_rows.append({"Section": "Top 10 Critical URLs", "Severity": "Critical", "Issue": f"#{idx} {row.get('URL')}", "Affected URL Count": row.get("Critical Issues Count"), "Reference Tab": "Priority URLs", "Affected URLs (sample)": row.get("Matched Issues")})
                summary_rows.append({"Section": "Top Issues by Template", "Severity": None, "Issue": None, "Affected URL Count": None, "Affected URLs (sample)": None})
                top_template_issues = sorted([(seg, issue_name, issue_count) for seg, issues in template_issue_counts.items() for issue_name, issue_count in issues.items()], key=lambda x: x[2], reverse=True)[:20]
                for seg, issue_name, issue_count in top_template_issues:
                    summary_rows.append({"Section": "Top Issues by Template", "Severity": "Observation", "Issue": f"{seg} -> {issue_name}", "Affected URL Count": issue_count, "Reference Tab": "TemplateClusters", "Affected URLs (sample)": None})
                _to_excel_safe(pd.DataFrame(summary_rows), writer, "Summary", index=False)
                issue_inventory_rows = []
                for row in extra_rows:
                    url = row.get("URL")
                    for issue in str(row.get("Matched Issues") or "").split(" | "):
                        if not issue:
                            continue
                        issue_severity = "Critical" if issue in [i[1] for i in summary_rules if i[0] == "Critical"] else "Warning" if issue in [i[1] for i in summary_rules if i[0] == "Warning"] else "Observation"
                        reference_tab = (
                            "Indexability"
                            if ("Canonical" in issue or "Noindex" in issue)
                            else "Links"
                            if ("Links" in issue or "Anchor" in issue)
                            else "AEO"
                            if ("AEO" in issue or "Question" in issue or "FAQ" in issue)
                            else "Technical"
                        )
                        issue_inventory_rows.append(
                            {
                                "URL": url,
                                "Issue": issue,
                                "Stable Issue ID": stable_issue_id(url, issue),
                                "Severity": issue_severity,
                                "Reference Tab": reference_tab,
                                "Owner": owner_for_issue(issue, issue_severity),
                                "Sprint": "",
                                "Status": "Open",
                            }
                        )
                issue_inventory_df = pd.DataFrame(issue_inventory_rows)
                _to_excel_safe(issue_inventory_df, writer, "IssueInventory", index=False)
                fixplan_rows = build_fixplan_rows(
                    summary_rules,
                    extra_rows,
                    aeo_issue_names,
                    root_cause_and_fix,
                    DEFAULT_EFFORT_BY_SEVERITY,
                    DEFAULT_OWNER_BY_SEVERITY,
                )
                fixplan_df = pd.DataFrame(sorted(fixplan_rows, key=lambda x: (-x["Affected Count"], x["Severity"])))
                _to_excel_safe(fixplan_df, writer, "FixPlan", index=False)
                content_hub_rows = build_content_optimization_hub_rows(main_rows, extra_rows, fixplan_rows)
                content_hub_cols = [
                    "Status",
                    "Assigned Owner",
                    "Content Cluster ID",
                    "URL",
                    "Elementor Builder Link",
                    "Target Keywords",
                    "Current Page Copy Snippet",
                    "Current Title",
                    "Proposed Title (50-60 Chars)",
                    "Title Count",
                    "Current Meta Desc",
                    "Proposed Meta Desc (120-160 Chars)",
                    "Desc Count",
                    "Current H-Tag Structure",
                    "Proposed H-Tag Fixes",
                    "AEO Answer Block Draft",
                    "FAQ/QA Draft",
                    "Current OG-Image URL",
                    "OG Image Preview",
                    "Social Share Note",
                ]
                write_dict_rows_sheet(writer, "Content Optimization Hub", content_hub_cols, content_hub_rows)
                priority_rows = []
                for row in extra_rows:
                    risk_score = (row.get("Critical Issues Count") or 0) * 30 + (row.get("Warning Issues Count") or 0) * 10 + (100 - (row.get("SEO Health Score") or 100))
                    reasons = []
                    if (row.get("Critical Issues Count") or 0) > 0:
                        reasons.append("Has critical issues")
                    if (row.get("Broken Internal Links Count") or 0) > 0:
                        reasons.append("Broken internal links")
                    if row.get("Canonical Type") == "cross-canonical":
                        reasons.append("Cross canonical")
                    if "noindex" in str(row.get("Indexability Reason", "")).lower():
                        reasons.append("Noindex")
                    owner_seed_issue = (
                        "Broken Internal Links"
                        if (row.get("Broken Internal Links Count") or 0) > 0
                        else "Canonical Points Elsewhere"
                        if row.get("Canonical Type") == "cross-canonical"
                        else "Noindex Directive"
                        if "noindex" in str(row.get("Indexability Reason", "")).lower()
                        else ""
                    )
                    priority_rows.append({"URL": row.get("URL"), "Business Risk Score": int(risk_score), "SEO Health Score": row.get("SEO Health Score"), "Severity Badge": row.get("Severity Badge"), "Critical Issues Count": row.get("Critical Issues Count"), "Warning Issues Count": row.get("Warning Issues Count"), "Indexability Reason": row.get("Indexability Reason"), "Broken Internal Links Count": row.get("Broken Internal Links Count"), "Canonical Type": row.get("Canonical Type"), "Why Prioritized": " | ".join(reasons) if reasons else "Monitor", "Action Needed": "Yes" if risk_score >= 30 else "No", "Owner": owner_for_issue(owner_seed_issue, str(row.get("Severity Badge") or "")), "Sprint": "", "Status": "Open"})
                priority_df = pd.DataFrame(sorted(priority_rows, key=lambda x: x["Business Risk Score"], reverse=True))
                _to_excel_safe(priority_df, writer, "Priority URLs", index=False)
                total_urls = len(extra_rows)
                pass_count = len([r for r in extra_rows if r.get("Severity Badge") == "Pass"])
                critical_count = len([r for r in extra_rows if r.get("Severity Badge") == "Critical"])
                warning_count = len([r for r in extra_rows if r.get("Severity Badge") == "Warning"])
                score_bands = {"90-100": 0, "70-89": 0, "<70": 0}
                status_dist: defaultdict[str, int] = defaultdict(int)
                for row in extra_rows:
                    status_dist[str(row.get("Status Class"))] += 1
                    s = row.get("SEO Health Score") or 0
                    if s >= 90:
                        score_bands["90-100"] += 1
                    elif s >= 70:
                        score_bands["70-89"] += 1
                    else:
                        score_bands["<70"] += 1
                top_blockers = fixplan_df.head(10)[["Issue Type", "Severity", "Affected Count"]]
                dashboard_rows = [{"Metric": "URLs Crawled", "Value": total_urls}, {"Metric": "Pass Rate (%)", "Value": round((pass_count / max(1, total_urls)) * 100, 2)}, {"Metric": "Critical URL Count", "Value": critical_count}, {"Metric": "Warning URL Count", "Value": warning_count}, {"Metric": "Status Distribution", "Value": ", ".join([f"{k}:{v}" for k, v in sorted(status_dist.items())])}, {"Metric": "Score Bands", "Value": ", ".join([f"{k}:{v}" for k, v in score_bands.items()])}]
                _to_excel_safe(pd.DataFrame(dashboard_rows), writer, "Dashboard", index=False)
                immediate_action_cols = [
                    "URL",
                    "Business Risk Score",
                    "Why Prioritized",
                    "Action Needed",
                    "Owner",
                    "Status",
                ]
                immediate_actions_df = priority_df.reindex(columns=immediate_action_cols).head(5).copy()
                immediate_actions_df.insert(0, "Rank", range(1, len(immediate_actions_df) + 1))
                immediate_actions_startrow = len(dashboard_rows) + len(top_blockers) + 7
                _to_excel_safe(
                    pd.DataFrame([{"Immediate Actions": "Top 5 URLs by Business Risk Score"}]),
                    writer,
                    "Dashboard",
                    index=False,
                    startrow=immediate_actions_startrow,
                )
                _to_excel_safe(
                    immediate_actions_df,
                    writer,
                    "Dashboard",
                    index=False,
                    startrow=immediate_actions_startrow + 2,
                )
                run_meta_rows = [{"Key": "Run Timestamp", "Value": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")}, {"Key": "Total URLs", "Value": len(urls)}, {"Key": "Mode", "Value": "Full Suite"}, {"Key": "Workers", "Value": workers}, {"Key": "Delay Seconds", "Value": request_delay}, {"Key": "Retries", "Value": MAX_RETRIES}, {"Key": "Timeout Seconds", "Value": TIMEOUT_SECONDS}, {"Key": "Checkpoint Every", "Value": checkpoint_every}, {"Key": "Previous Audit Path", "Value": previous_audit_path or "Not supplied"}]
                _to_excel_safe(pd.DataFrame(run_meta_rows), writer, "RunMetadata", index=False)
                current_issue_inventory_df = issue_inventory_df.copy()
                current_issue_ids = {
                    str(v).strip()
                    for v in current_issue_inventory_df.get("Stable Issue ID", pd.Series(dtype="object")).dropna().tolist()
                    if str(v).strip()
                }
                new_issues = current_issue_ids - prev_issue_ids
                resolved_issues = prev_issue_ids - current_issue_ids
                unchanged_issues = current_issue_ids & prev_issue_ids
                delta_rows = [{"Metric": "New Issues", "Count": len(new_issues)}, {"Metric": "Resolved Issues", "Count": len(resolved_issues)}, {"Metric": "Unchanged Issues", "Count": len(unchanged_issues)}]
                reopened_from_previously_fixed = len(current_issue_ids & prev_fixed_issue_ids)
                delta_rows.append({"Metric": "Previously Fixed But Reopened", "Count": reopened_from_previously_fixed})
                for _, issue_name, _ in summary_rules:
                    current_count = len([r for r in extra_rows if issue_name in str(r.get("Matched Issues") or "").split(" | ")])
                    delta_rows.append({"Metric": f"Issue Delta: {issue_name}", "Count": current_count - int(prev_counts.get(issue_name, 0))})
                _to_excel_safe(pd.DataFrame(delta_rows), writer, "DeltaFromPreviousRun", index=False)
                if not previous_issue_inventory_df.empty and "Stable Issue ID" in previous_issue_inventory_df.columns:
                    previous_issue_inventory_df = previous_issue_inventory_df.copy()
                    previous_issue_inventory_df["Stable Issue ID"] = previous_issue_inventory_df["Stable Issue ID"].astype(str).str.strip()
                    resolved_issues_df = previous_issue_inventory_df[
                        previous_issue_inventory_df["Stable Issue ID"].isin(resolved_issues)
                    ].copy()
                else:
                    resolved_issues_df = pd.DataFrame(columns=["Stable Issue ID"])
                if resolved_issues_df.empty:
                    resolved_issues_df = pd.DataFrame(
                        [
                            {
                                "Stable Issue ID": "",
                                "Issue": "No resolved issues identified for this comparison run.",
                                "URL": "",
                            }
                        ]
                    )
                _to_excel_safe(resolved_issues_df, writer, "ResolvedIssues", index=False)
                legend_rows = [
                    {"Section": "How To Use", "Term": "Step 1: Start on Dashboard", "Meaning": "Review pass rate, critical URL count, and Immediate Actions to understand overall risk first.", "Values/Threshold": "5-minute executive scan", "Related Tabs": "Dashboard, Priority URLs"},
                    {"Section": "How To Use", "Term": "Step 2: Prioritize and Assign", "Meaning": "Use Priority URLs and FixPlan to pick highest-impact items, assign owner, and set status/sprint.", "Values/Threshold": "Work top-down by Business Risk Score", "Related Tabs": "Priority URLs, FixPlan"},
                    {"Section": "How To Use", "Term": "Step 3: Execute and Validate", "Meaning": "Implement fixes, then verify by checking Technical/Indexability/AEO tabs and rerunning the audit.", "Values/Threshold": "Close loop every sprint", "Related Tabs": "Technical, Indexability, AEO, AIOSEO"},
                    {"Section": "Orientation", "Term": "Where to Start", "Meaning": "If you're short on time, work only Critical and Warning issues first, then return to Observation items.", "Values/Threshold": "Critical > Warning > Observation", "Related Tabs": "Summary, FixPlan, Technical"},
                    {"Section": "Orientation", "Term": "How to Track Progress", "Meaning": "Use Status and Owner columns as your project board; move from To Do -> In Progress -> Fixed.", "Values/Threshold": "Update weekly", "Related Tabs": "FixPlan, AIOSEO, Priority URLs"},
                    {"Section": "Severity", "Term": "Critical", "Meaning": "High-impact SEO blocker that should be fixed first.", "Values/Threshold": "Immediate action", "Related Tabs": "Summary, FixPlan, Technical"},
                    {"Section": "Severity", "Term": "Warning", "Meaning": "Out-of-best-practice issue likely affecting performance.", "Values/Threshold": "Plan next sprint", "Related Tabs": "Summary, FixPlan, Technical"},
                    {"Section": "Severity", "Term": "Observation", "Meaning": "Optimization opportunity or context signal.", "Values/Threshold": "Backlog/monitor", "Related Tabs": "Summary, Technical"},
                    {"Section": "Scoring", "Term": "SEO Health Score", "Meaning": "Weighted technical SEO quality score per URL.", "Values/Threshold": ">=90 green, 70-89 orange, <70 red", "Related Tabs": "Technical, Priority URLs, Dashboard"},
                    {"Section": "Scoring", "Term": "AEO Readiness Score", "Meaning": "Answer Engine Optimization readiness score per URL.", "Values/Threshold": ">=80 strong, 60-79 good, 40-59 fair", "Related Tabs": "AEO"},
                    {"Section": "Indexing", "Term": "Indexability Reason", "Meaning": "Primary reason URL may not be indexed.", "Values/Threshold": "Noindex, non-200, canonical mismatch", "Related Tabs": "Indexability, Technical"},
                    {"Section": "Links", "Term": "Broken Internal Links Count", "Meaning": "Internal links returning 4xx/5xx or equivalent failures.", "Values/Threshold": ">0 flagged", "Related Tabs": "Links, LinksDetail, Priority URLs"},
                    {"Section": "Content", "Term": "Word Count Band", "Meaning": "Body content depth class.", "Values/Threshold": "Thin / OK / Strong", "Related Tabs": "Content"},
                    {"Section": "AEO", "Term": "Question Heading Count", "Meaning": "Headings phrased as questions to match answer intent.", "Values/Threshold": "Higher is generally better", "Related Tabs": "AEO"},
                    {"Section": "Color Key", "Term": "Green", "Meaning": "Pass / aligned with best practice or completed workflow item.", "Values/Threshold": "Good", "Related Tabs": "All"},
                    {"Section": "Color Key", "Term": "Orange", "Meaning": "Warning / in progress / medium-priority attention needed.", "Values/Threshold": "Medium risk", "Related Tabs": "All"},
                    {"Section": "Color Key", "Term": "Red", "Meaning": "Failure / high-priority issue or to-do critical task.", "Values/Threshold": "High risk", "Related Tabs": "All"},
                    {"Section": "Color Key", "Term": "Purple", "Meaning": "Informational edge-case or AEO category signal.", "Values/Threshold": "Context", "Related Tabs": "All"},
                ]
                _to_excel_safe(pd.DataFrame(legend_rows), writer, "Legend", index=False)
                crawl_inlinks_map: defaultdict[str, set[str]] = defaultdict(set)
                crawled_set_main = set(main_df["URL"].dropna().tolist())
                for row in extra_rows:
                    source = row.get("URL")
                    for target in row.get("Internal Links List", []):
                        if target in crawled_set_main:
                            crawl_inlinks_map[target].add(source)
                graph_rows = [{"URL": url_item, "Inlinks Count": len(inlinks := sorted(list(crawl_inlinks_map.get(url_item, set())))), "Inlinks URLs": " | ".join(inlinks) if inlinks else None, "Orphan Candidate": len(inlinks) == 0} for url_item in main_df["URL"].dropna().tolist()]
                _to_excel_safe(pd.DataFrame(graph_rows), writer, "CrawlGraph", index=False)
                sitemap_rows = []
                if sitemap_meta:
                    for sitemap_url, meta in sitemap_meta.items():
                        matched = next((row for row in extra_rows if str(row.get("URL", "")).rstrip("/") == str(sitemap_url).rstrip("/")), None)
                        final_url = matched.get("Final URL") if matched else None
                        status_code = matched.get("Status Code") if matched else None
                        sitemap_rows.append({"Sitemap URL": sitemap_url, "Final URL": final_url, "Status Code": status_code, "In Sitemap but Non-200": status_code != 200, "Sitemap URL Redirects": (matched.get("Redirect Chain Length", 0) > 0 if matched else None), "In Sitemap but Canonicalized Elsewhere": (matched.get("Canonical Type") == "cross-canonical" if matched else None), "Missing <lastmod>": not bool(meta.get("lastmod")), "Missing <changefreq>": not bool(meta.get("changefreq")), "Missing <priority>": not bool(meta.get("priority")), "Sitemap <lastmod>": meta.get("lastmod"), "Sitemap <changefreq>": meta.get("changefreq"), "Sitemap <priority>": meta.get("priority")})
                _to_excel_safe(pd.DataFrame(sitemap_rows), writer, "SitemapQA", index=False)
                preferred_first_tabs = [
                    "Dashboard",
                    "Content Optimization Hub",
                    "FixPlan",
                    "Main",
                    "Technical",
                    "Content",
                    "AEO",
                    "Schema & Metadata",
                    "Links",
                    "Indexability",
                    "Redirects",
                    "Priority URLs",
                    "AIOSEO",
                    "Security",
                    "Summary",
                    "Legend",
                    "LinksDetail",
                    "Media",
                ]
                wb = writer.book
                for idx, tab_name in enumerate(preferred_first_tabs):
                    if tab_name in wb.sheetnames:
                        wb.move_sheet(wb[tab_name], offset=-wb.index(wb[tab_name]) + idx)
                apply_tab_hyperlinks(writer)
                for sname in ["Dashboard", "Content Optimization Hub", "FixPlan", "Legend", "Technical", "Content", "Links", "LinksDetail", "Media", "Schema & Metadata", "AEO", "AIOSEO", "Security", "Indexability", "Redirects", "Duplicates", "TemplateClusters", "Priority URLs", "IssueInventory", "ResolvedIssues", "RunMetadata", "DeltaFromPreviousRun", "CrawlGraph", "SitemapQA", "Summary"]:
                    adjust_sheet_format(writer, sname)
            print(f"\nAudit complete! Report saved to {output_filename}")
        finally:
            if writer is not None:
                writer.close()
            cache.close(cleanup_file=True)


def _safe_rule(rule_fn, row):
    try:
        return bool(rule_fn(row))
    except Exception:
        return False


def _build_aeo_rows(extra_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in extra_rows:
        question_heading_count = int(row.get("Question Heading Count") or 0)
        faq_count = int(row.get("FAQ Section Count") or 0)
        answer_para_count = int(row.get("Paragraphs 40-60 Words Count") or 0)
        has_qa_schema = bool(row.get("QAPage/FAQ Schema Present"))
        has_speakable = bool(row.get("Speakable Schema Present"))
        has_howto = bool(row.get("HowTo Signal"))
        has_definition = bool(row.get("Definition Signal"))
        has_list_table = bool(row.get("List/Table Answer Signal"))
        title_missing = bool(row.get("Title Missing"))
        meta_missing = bool(row.get("Meta Description Missing"))
        aeo_score = int(row.get("AEO Readiness Score") or 0)

        why_notes: list[str] = []
        if answer_para_count == 0:
            why_notes.append("Missing 30-60 word answer blocks reduces eligibility for featured snippets.")
        if question_heading_count == 0:
            why_notes.append("Question-style headings help match conversational search and answer intent.")
        if not has_qa_schema:
            why_notes.append("FAQ/QA schema improves machine understanding for rich answer surfaces.")
        if not has_speakable:
            why_notes.append("Speakable markup can improve voice assistant readability of key answers.")
        if not has_howto and not has_definition and not has_list_table:
            why_notes.append("Answer-friendly structure (how-to, definitions, lists/tables) helps extraction by answer engines.")
        if title_missing or meta_missing:
            why_notes.append("Missing title/meta weakens topical context and lowers snippet confidence.")
        if not why_notes and aeo_score >= 80:
            why_notes.append("Strong answer-engine foundations are present; maintain concise, direct answer blocks.")

        row_copy = dict(row)
        row_copy["Why It Matters"] = " ".join(why_notes)
        row_copy["Question Heading Count"] = question_heading_count
        row_copy["FAQ Section Count"] = faq_count
        row_copy["Paragraphs 40-60 Words Count"] = answer_para_count
        first_snippet = (row.get("aeo_snippets") or [{}])[0] if row.get("aeo_snippets") else {}
        heading = str(first_snippet.get("heading") or "").strip()
        snippet = str(first_snippet.get("snippet") or "").strip()
        row_copy["Snippet Preview Mockup"] = f"{heading}\n{snippet}".strip() if heading or snippet else None
        rows.append(row_copy)
    return rows


def _build_aioseo_rows(
    extra_rows: list[dict[str, object]],
    main_by_url: dict[str, dict[str, object]],
    default_owner_by_severity: dict[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    severity_rank = {"Critical": 0, "Warning": 1, "Observation": 2}

    def _to_int(value: object, fallback: int = 0) -> int:
        try:
            return int(float(value)) if value is not None else fallback
        except Exception:
            return fallback

    def _to_float(value: object, fallback: float = 0.0) -> float:
        try:
            return float(value) if value is not None else fallback
        except Exception:
            return fallback

    def add_issue(
        *,
        url: str,
        issue: str,
        severity: str,
        panel: str,
        current_value: object,
        recommended_target: str,
        why_it_matters: str,
        how_to_fix: str,
        reference_tab: str,
        reference_field: str,
    ) -> None:
        workflow = workflow_metrics_for_issue(severity)
        rows.append(
            {
                "URL": url,
                "WordPress Post ID": current_post_id if current_post_id > 0 else None,
                "Direct Edit Link": current_direct_edit_link,
                "AIOSEO Panel": panel,
                "Severity": severity,
                "Issue": issue,
                "Current Value": current_value,
                "Recommended Target": recommended_target,
                "Why It Matters": why_it_matters,
                "How to Fix in AIOSEO": how_to_fix,
                "Reference Tab": reference_tab,
                "Reference Field": reference_field,
                "Action Needed": "Yes" if severity in {"Critical", "Warning"} else "No",
                "Owner": owner_for_issue(issue, severity),
                "Status": "Open",
                "Priority Score": workflow.get("Priority Score"),
                "Est. Hours": workflow.get("Est. Hours"),
                "Stable Issue ID": stable_issue_id(url, f"AIOSEO::{issue}"),
            }
        )

    for row in extra_rows:
        url = str(row.get("URL") or "").strip()
        if not url:
            continue
        post_id_raw = row.get("WordPress Post ID")
        current_post_id = _to_int(post_id_raw, 0)
        parsed_url = urlparse(url)
        site_root = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.scheme and parsed_url.netloc else ""
        current_direct_edit_link = (
            f"{site_root}/wp-admin/post.php?post={current_post_id}&action=edit"
            if site_root and current_post_id > 0
            else None
        )
        main_row = main_by_url.get(url, {})
        title = str(main_row.get("Title") or "").strip()
        meta = str(main_row.get("Meta Description") or "").strip()
        title_len = len(title)
        meta_len = len(meta)

        status_code = _to_int(row.get("Status Code"))
        if status_code >= 400:
            add_issue(
                url=url,
                issue="Page returns non-200 response",
                severity="Critical",
                panel="Basic SEO",
                current_value=status_code,
                recommended_target="200",
                why_it_matters="Pages that error cannot perform in search and fail core page-level SEO checks.",
                how_to_fix="Update URL target, restore page, or set correct redirect. In AIOSEO, review canonical/robots only after the page returns 200.",
                reference_tab="Technical",
                reference_field="Status Code",
            )

        if "noindex" in str(row.get("Indexability Reason") or "").lower():
            add_issue(
                url=url,
                issue="Noindex directive on page",
                severity="Critical",
                panel="Advanced SEO",
                current_value=row.get("Indexability Reason"),
                recommended_target="Indexable",
                why_it_matters="Noindex prevents the page from being indexed.",
                how_to_fix="In AIOSEO page settings -> Advanced, remove noindex for pages intended to rank.",
                reference_tab="Indexability",
                reference_field="Indexability Reason",
            )

        canonical_type = str(row.get("Canonical Type") or "")
        if canonical_type in {"missing", "cross-canonical"}:
            add_issue(
                url=url,
                issue="Canonical configuration issue",
                severity="Critical" if canonical_type == "cross-canonical" else "Warning",
                panel="Advanced SEO",
                current_value=canonical_type,
                recommended_target="self",
                why_it_matters="Incorrect canonicals can de-index or de-prioritise the intended URL.",
                how_to_fix="In AIOSEO -> Advanced -> Canonical URL, set canonical to the preferred final URL for this page.",
                reference_tab="Indexability",
                reference_field="Canonical Type",
            )

        if not title:
            add_issue(
                url=url,
                issue="Missing SEO title",
                severity="Warning",
                panel="Title",
                current_value="Missing",
                recommended_target="40-60 characters",
                why_it_matters="Titles are a core relevance and CTR signal.",
                how_to_fix="In AIOSEO snippet settings, add a unique SEO title with the primary topic near the beginning.",
                reference_tab="Main",
                reference_field="Title",
            )
        else:
            if title_len < 40:
                add_issue(
                    url=url,
                    issue="SEO title too short",
                    severity="Observation",
                    panel="Title",
                    current_value=title_len,
                    recommended_target="40-60 characters",
                    why_it_matters="Very short titles often under-describe page intent.",
                    how_to_fix="Expand title in AIOSEO snippet editor with clearer intent and value proposition.",
                    reference_tab="Main",
                    reference_field="Title",
                )
            elif title_len > 60:
                add_issue(
                    url=url,
                    issue="SEO title too long",
                    severity="Observation",
                    panel="Title",
                    current_value=title_len,
                    recommended_target="40-60 characters",
                    why_it_matters="Long titles are more likely to truncate in SERPs.",
                    how_to_fix="Shorten title in AIOSEO snippet editor and keep key terms in the first 55-60 characters.",
                    reference_tab="Main",
                    reference_field="Title",
                )

        if not meta:
            add_issue(
                url=url,
                issue="Missing meta description",
                severity="Warning",
                panel="Basic SEO",
                current_value="Missing",
                recommended_target="120-160 characters",
                why_it_matters="Missing descriptions reduce control over search snippet messaging.",
                how_to_fix="In AIOSEO snippet settings, add a concise, unique meta description aligned to page intent.",
                reference_tab="Main",
                reference_field="Meta Description",
            )
        else:
            if meta_len < 120:
                add_issue(
                    url=url,
                    issue="Meta description too short",
                    severity="Observation",
                    panel="Basic SEO",
                    current_value=meta_len,
                    recommended_target="120-160 characters",
                    why_it_matters="Short descriptions can under-communicate relevance and value.",
                    how_to_fix="Expand meta description in AIOSEO to include key value points and intent terms naturally.",
                    reference_tab="Main",
                    reference_field="Meta Description",
                )
            elif meta_len > 160:
                add_issue(
                    url=url,
                    issue="Meta description too long",
                    severity="Observation",
                    panel="Basic SEO",
                    current_value=meta_len,
                    recommended_target="120-160 characters",
                    why_it_matters="Long descriptions are often truncated and lose message clarity.",
                    how_to_fix="Trim meta description in AIOSEO and front-load essential context.",
                    reference_tab="Main",
                    reference_field="Meta Description",
                )

        if bool(row.get("Missing H1 Flag")):
            add_issue(
                url=url,
                issue="Missing H1 heading",
                severity="Warning",
                panel="Readability",
                current_value=row.get("H1 Count"),
                recommended_target="Exactly 1 descriptive H1",
                why_it_matters="A missing H1 weakens topical clarity for users and crawlers.",
                how_to_fix="Update page content to include a single descriptive H1 aligned to primary intent.",
                reference_tab="Content",
                reference_field="Missing H1 Flag",
            )
        if bool(row.get("Multiple H1 Flag")):
            add_issue(
                url=url,
                issue="Multiple H1 headings",
                severity="Observation",
                panel="Readability",
                current_value=row.get("H1 Count"),
                recommended_target="Exactly 1 H1",
                why_it_matters="Multiple H1s can reduce heading hierarchy clarity.",
                how_to_fix="Keep one primary H1, convert remaining top-level headings to H2/H3 where appropriate.",
                reference_tab="Content",
                reference_field="Multiple H1 Flag",
            )

        word_count = _to_int(row.get("Word Count"))
        if bool(row.get("Thin Content Flag")) or word_count < 300:
            add_issue(
                url=url,
                issue="Thin content",
                severity="Warning",
                panel="Readability",
                current_value=word_count,
                recommended_target=">=300 words (quality first)",
                why_it_matters="Low-content pages can struggle to satisfy intent and rank competitively.",
                how_to_fix="Expand page copy with useful, unique sections that answer key user questions.",
                reference_tab="Content",
                reference_field="Word Count",
            )

        readability = _to_float(row.get("Readability (Rough Flesch)"), -1)
        if readability >= 0 and readability < 50:
            add_issue(
                url=url,
                issue="Low readability score",
                severity="Observation",
                panel="Readability",
                current_value=readability,
                recommended_target=">=50",
                why_it_matters="Hard-to-read content lowers engagement and comprehension.",
                how_to_fix="Use shorter sentences/paragraphs, clearer transitions, and simpler phrasing in page content.",
                reference_tab="Content",
                reference_field="Readability (Rough Flesch)",
            )

        if _to_int(row.get("Internal Links Count")) == 0:
            add_issue(
                url=url,
                issue="No internal links found",
                severity="Observation",
                panel="Basic SEO",
                current_value=0,
                recommended_target=">=2 relevant internal links",
                why_it_matters="Internal links help discovery, topical signals, and authority flow.",
                how_to_fix="Add contextual internal links from and to related pages using descriptive anchor text.",
                reference_tab="Links",
                reference_field="Internal Links Count",
            )
        if _to_int(row.get("Broken Internal Links Count")) > 0:
            add_issue(
                url=url,
                issue="Broken internal links",
                severity="Critical",
                panel="Links",
                current_value=row.get("Broken Internal Links Count"),
                recommended_target="0",
                why_it_matters="Broken links waste crawl budget and degrade user experience.",
                how_to_fix="Replace dead links with live targets, or remove them in the page editor.",
                reference_tab="Links",
                reference_field="Broken Internal Links Count",
            )

        alt_coverage = _to_float(row.get("Image Alt Coverage (%)"), 100.0)
        if alt_coverage < 80:
            add_issue(
                url=url,
                issue="Low image alt coverage",
                severity="Warning",
                panel="Readability",
                current_value=alt_coverage,
                recommended_target=">=80%",
                why_it_matters="Missing alt text reduces accessibility and weakens image context signals.",
                how_to_fix="Add descriptive alt text to meaningful images in the page editor/media fields.",
                reference_tab="Media",
                reference_field="Image Alt Coverage (%)",
            )

        if _to_int(row.get("Schema Types Count")) == 0:
            add_issue(
                url=url,
                issue="No schema markup detected",
                severity="Warning",
                panel="Schema",
                current_value=0,
                recommended_target="At least one relevant schema type",
                why_it_matters="Schema improves understanding and rich result eligibility.",
                how_to_fix="In AIOSEO schema settings for the page, add the most relevant type (Article/FAQ/HowTo/Product, etc.).",
                reference_tab="Schema & Metadata",
                reference_field="Schema Types Count",
            )

        aeo_score = _to_int(row.get("AEO Readiness Score"), 100)
        if aeo_score < 60:
            add_issue(
                url=url,
                issue="Low AEO readiness score",
                severity="Warning",
                panel="Content",
                current_value=aeo_score,
                recommended_target=">=60",
                why_it_matters="Weak answer-style structure lowers AI/answer-engine retrieval potential.",
                how_to_fix="Add concise answer blocks, question-led subheadings, and clear structured sections.",
                reference_tab="AEO",
                reference_field="AEO Readiness Score",
            )
        if not bool(row.get("QAPage/FAQ Schema Present")):
            add_issue(
                url=url,
                issue="No FAQ/QA schema",
                severity="Observation",
                panel="Schema",
                current_value=False,
                recommended_target="True when page has Q&A intent",
                why_it_matters="Q&A schema can improve eligibility for answer-rich results.",
                how_to_fix="If content is Q&A style, add FAQPage/QAPage schema in AIOSEO and keep markup aligned with on-page content.",
                reference_tab="AEO",
                reference_field="QAPage/FAQ Schema Present",
            )
        if _to_int(row.get("Question Heading Count")) == 0:
            add_issue(
                url=url,
                issue="No question-style headings",
                severity="Observation",
                panel="Readability",
                current_value=0,
                recommended_target=">=1 where intent is informational",
                why_it_matters="Question headings better align with query phrasing and snippet extraction.",
                how_to_fix="Add at least one natural question heading (H2/H3) matching user intent.",
                reference_tab="AEO",
                reference_field="Question Heading Count",
            )
        if _to_int(row.get("Paragraphs 40-60 Words Count")) == 0:
            add_issue(
                url=url,
                issue="No concise answer paragraph (40-60 words)",
                severity="Observation",
                panel="Content",
                current_value=0,
                recommended_target=">=1 concise answer block",
                why_it_matters="Compact answer blocks improve direct-answer extraction chances.",
                how_to_fix="Add a direct 40-60 word answer immediately below key question headings.",
                reference_tab="AEO",
                reference_field="Paragraphs 40-60 Words Count",
            )

    rows.sort(
        key=lambda r: (
            severity_rank.get(str(r.get("Severity")), 9),
            -_to_int(r.get("Priority Score"), 0),
            str(r.get("AIOSEO Panel") or ""),
            str(r.get("URL") or ""),
            str(r.get("Issue") or ""),
        )
    )
    return rows


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
