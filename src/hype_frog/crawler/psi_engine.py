"""PageSpeed Insights batch fetch — public facade re-exporting split modules."""

from __future__ import annotations

from hype_frog.core.env_vars import get_psi_api_key
from hype_frog.crawler.psi_batch import (  # noqa: F401 — private aliases for tests
    build_endpoint as _build_endpoint,
    fetch_psi_metrics_batch,
    format_probe_transport_error as _format_probe_transport_error,
    is_retryable_psi_error as _is_retryable_psi_error,
    jittered_seconds as _jittered_seconds,
    probe_psi_api_key,
)
from hype_frog.crawler.psi_merge import (  # noqa: F401 — private aliases for tests
    PSI_LIGHTHOUSE_EXPORT_KEYS,
    detect_crux_level as _detect_crux_level,
    extract_lighthouse_data as _extract_lighthouse_data,
    field_experience_metrics as _field_experience_metrics,
    merge_url_results as _merge_url_results,
    psi_index_key,
    resolve_psi_data_status as _resolve_psi_data_status,
    store_psi_result as _store_psi_result,
)

__all__ = [
    "PSI_LIGHTHOUSE_EXPORT_KEYS",
    "_detect_crux_level",
    "_extract_lighthouse_data",
    "_field_experience_metrics",
    "_format_probe_transport_error",
    "_is_retryable_psi_error",
    "_jittered_seconds",
    "_merge_url_results",
    "_resolve_psi_data_status",
    "_store_psi_result",
    "fetch_psi_metrics_batch",
    "get_psi_api_key",
    "probe_psi_api_key",
    "psi_index_key",
]

