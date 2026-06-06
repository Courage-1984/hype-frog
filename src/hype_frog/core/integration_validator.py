"""Integration checks for runtime secrets and external APIs.

Validates Google Search Console OAuth files, PageSpeed Insights API access,
and optional LLM keys without starting a crawl.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from hype_frog.config import PROJECT_ROOT, load_environment
from hype_frog.core.api_clients import parse_psi_response
from hype_frog.crawler.gsc_engine import (
    load_gsc_credentials_readonly,
    probe_gsc_api_access,
    resolve_gsc_credentials_path,
    resolve_gsc_token_path,
    SCOPES,
)
from hype_frog.crawler.psi_engine import get_psi_api_key, probe_psi_api_key

_DEFAULT_PSI_PROBE_URL = "https://example.com"
_GSC_READONLY_SCOPE = SCOPES[0]


class CheckStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class IntegrationCheck:
    """Single validation outcome for console reporting."""

    name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def _mask_secret(value: str, *, visible: int = 4) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return "<empty>"
    if len(cleaned) <= visible * 2:
        return "***"
    return f"{cleaned[:visible]}...{cleaned[-visible:]}"


def _status_icon(status: CheckStatus) -> str:
    return {
        CheckStatus.PASS: "[PASS]",
        CheckStatus.WARN: "[WARN]",
        CheckStatus.FAIL: "[FAIL]",
        CheckStatus.SKIP: "[SKIP]",
    }[status]


def _parse_client_secrets(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read or parse JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "Root JSON value must be an object."
    return payload, None


def _extract_oauth_client_block(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    for key in ("installed", "web"):
        block = payload.get(key)
        if isinstance(block, dict):
            return block, key
    return None, None


def check_environment_file() -> IntegrationCheck:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return IntegrationCheck(
            name="Environment file",
            status=CheckStatus.WARN,
            message="`.env` not found. Copy `.env.example` to `.env` and add your keys.",
            details={"path": str(env_path)},
        )
    return IntegrationCheck(
        name="Environment file",
        status=CheckStatus.PASS,
        message="`.env` is present and loaded.",
        details={"path": str(env_path)},
    )


def check_gsc_client_secrets() -> IntegrationCheck:
    path = resolve_gsc_credentials_path()
    if not path.exists():
        return IntegrationCheck(
            name="GSC client_secrets.json",
            status=CheckStatus.FAIL,
            message=(
                "OAuth client secrets file not found. Place `client_secrets.json` in "
                "`secrets/`, `src/hype_frog/`, or the repository root."
            ),
            details={"expected_paths": [
                str(resolve_gsc_credentials_path()),
                str(PROJECT_ROOT / "src" / "hype_frog" / "client_secrets.json"),
                str(PROJECT_ROOT / "client_secrets.json"),
            ]},
        )

    payload, error = _parse_client_secrets(path)
    if error:
        return IntegrationCheck(
            name="GSC client_secrets.json",
            status=CheckStatus.FAIL,
            message=error,
            details={"path": str(path)},
        )

    block, block_type = _extract_oauth_client_block(payload or {})
    if block is None:
        return IntegrationCheck(
            name="GSC client_secrets.json",
            status=CheckStatus.FAIL,
            message='JSON must contain an "installed" or "web" OAuth client block.',
            details={"path": str(path)},
        )

    client_id = str(block.get("client_id") or "").strip()
    project_id = str(block.get("project_id") or "").strip()
    if not client_id:
        return IntegrationCheck(
            name="GSC client_secrets.json",
            status=CheckStatus.FAIL,
            message="OAuth client block is missing `client_id`.",
            details={"path": str(path), "block_type": block_type},
        )

    status = CheckStatus.PASS
    message = "OAuth client secrets file looks valid."
    if block_type != "installed":
        status = CheckStatus.WARN
        message = (
            'OAuth client secrets use a "web" client. hype-frog expects a Desktop '
            '("installed") OAuth client for the local browser flow.'
        )

    return IntegrationCheck(
        name="GSC client_secrets.json",
        status=status,
        message=message,
        details={
            "path": str(path),
            "block_type": block_type,
            "client_id": _mask_secret(client_id),
            "project_id": project_id or "<missing>",
        },
    )


def check_gsc_token_file() -> IntegrationCheck:
    token_path = resolve_gsc_token_path()
    if not token_path.exists():
        return IntegrationCheck(
            name="GSC token.json",
            status=CheckStatus.FAIL,
            message=f"Token file not found at {token_path}. Run: uv run hype-frog --gsc-auth",
            details={"path": str(token_path)},
        )

    creds, error = load_gsc_credentials_readonly()
    if error or creds is None:
        return IntegrationCheck(
            name="GSC token.json",
            status=CheckStatus.FAIL,
            message=error or "Token could not be loaded.",
            details={"path": str(token_path)},
        )

    expiry = getattr(creds, "expiry", None)
    return IntegrationCheck(
        name="GSC token.json",
        status=CheckStatus.PASS,
        message="OAuth token is present, valid, and includes the Search Console read-only scope.",
        details={
            "path": str(token_path),
            "scope": _GSC_READONLY_SCOPE,
            "expiry": expiry.isoformat() if expiry is not None else "<unknown>",
        },
    )


def check_gsc_api(target_url: str | None) -> IntegrationCheck:
    ok, message, site_urls, matched_property = probe_gsc_api_access(target_url=target_url)
    status = CheckStatus.PASS if ok else CheckStatus.FAIL
    if ok and target_url and matched_property is None:
        status = CheckStatus.FAIL
    return IntegrationCheck(
        name="GSC Search Console API",
        status=status,
        message=message,
        details={
            "target_url": target_url,
            "matched_property": matched_property,
            "visible_properties": site_urls,
        },
    )


def check_psi_api_key_present() -> IntegrationCheck:
    api_key = get_psi_api_key()
    if not api_key:
        return IntegrationCheck(
            name="PSI API key",
            status=CheckStatus.FAIL,
            message="PSI_API_KEY is not set in `.env`. PSI enrichment will be skipped during crawls.",
            details={},
        )
    return IntegrationCheck(
        name="PSI API key",
        status=CheckStatus.PASS,
        message="PSI_API_KEY is set.",
        details={"masked_key": _mask_secret(api_key)},
    )


async def check_psi_api_live(test_url: str) -> IntegrationCheck:
    ok, message, details = await probe_psi_api_key(test_url)
    status = CheckStatus.PASS if ok else CheckStatus.FAIL
    if ok and details and details.get("http_status") == 429:
        status = CheckStatus.WARN

    lab_metrics = (details or {}).get("lab_metrics") if details else None
    if ok and isinstance(lab_metrics, dict):
        validated = parse_psi_response(lab_metrics, url=test_url)
        if validated is None:
            status = CheckStatus.WARN
            message = (
                f"{message} Parsed metrics did not pass the internal PSI contract validator."
            )

    return IntegrationCheck(
        name="PSI API live probe",
        status=status,
        message=message,
        details=details or {},
    )


def check_optional_llm_keys() -> list[IntegrationCheck]:
    checks: list[IntegrationCheck] = []
    for env_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        value = str(os.getenv(env_name) or "").strip()
        if not value:
            checks.append(
                IntegrationCheck(
                    name=f"Optional {env_name}",
                    status=CheckStatus.SKIP,
                    message="Not set. Search intent will fall back to Unknown.",
                    details={},
                )
            )
            continue
        checks.append(
            IntegrationCheck(
                name=f"Optional {env_name}",
                status=CheckStatus.PASS,
                message="Key is set (live probe not run; classifier is validated during crawls).",
                details={"masked_key": _mask_secret(value)},
            )
        )
    return checks


async def run_integration_validation(
    *,
    target_url: str | None = None,
    psi_probe_url: str = _DEFAULT_PSI_PROBE_URL,
) -> list[IntegrationCheck]:
    """Run all integration checks and return structured outcomes."""
    load_environment()
    checks: list[IntegrationCheck] = [
        check_environment_file(),
        check_gsc_client_secrets(),
        check_gsc_token_file(),
        check_psi_api_key_present(),
    ]
    checks.extend(check_optional_llm_keys())

    token_check = checks[2]
    if token_check.status == CheckStatus.PASS:
        checks.append(check_gsc_api(target_url))
    else:
        checks.append(
            IntegrationCheck(
                name="GSC Search Console API",
                status=CheckStatus.SKIP,
                message="Skipped because the OAuth token is not ready.",
                details={},
            )
        )

    psi_key_check = checks[3]
    if psi_key_check.status == CheckStatus.PASS:
        checks.append(await check_psi_api_live(psi_probe_url))
    else:
        checks.append(
            IntegrationCheck(
                name="PSI API live probe",
                status=CheckStatus.SKIP,
                message="Skipped because PSI_API_KEY is not set.",
                details={},
            )
        )
    return checks


def format_validation_report(checks: list[IntegrationCheck]) -> str:
    lines = ["=== Hype Frog integration validator ===", ""]
    counts = {status: 0 for status in CheckStatus}

    for check in checks:
        counts[check.status] += 1
        lines.append(f"{_status_icon(check.status)} {check.name}")
        lines.append(f"       {check.message}")
        for key, value in check.details.items():
            if key == "visible_properties" and isinstance(value, list):
                if value:
                    lines.append(f"       {key}:")
                    for site in value:
                        lines.append(f"         - {site}")
                else:
                    lines.append(f"       {key}: <none>")
                continue
            lines.append(f"       {key}: {value}")
        lines.append("")

    lines.append(
        "Summary: "
        f"{counts[CheckStatus.PASS]} passed, "
        f"{counts[CheckStatus.WARN]} warnings, "
        f"{counts[CheckStatus.FAIL]} failed, "
        f"{counts[CheckStatus.SKIP]} skipped"
    )
    return "\n".join(lines)


def run_validation_cli(
    *,
    target_url: str | None = None,
    psi_probe_url: str = _DEFAULT_PSI_PROBE_URL,
) -> int:
    """Execute checks, print a report, and return a process exit code."""
    checks = asyncio.run(
        run_integration_validation(
            target_url=target_url,
            psi_probe_url=psi_probe_url,
        )
    )
    print(format_validation_report(checks))
    failed = any(check.status == CheckStatus.FAIL for check in checks)
    return 1 if failed else 0


__all__ = [
    "CheckStatus",
    "IntegrationCheck",
    "format_validation_report",
    "run_integration_validation",
    "run_validation_cli",
]
