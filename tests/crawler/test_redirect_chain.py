"""Unit tests for redirect chain parsing and export row builders (A3)."""
from __future__ import annotations

import json

from hype_frog.crawler.redirect_chain import (
    RedirectHopRecord,
    build_redirect_chain_fields,
    build_redirect_map_row,
    format_redirect_chain_display,
    has_mixed_redirect_types,
    has_temporary_redirect,
    is_redirect_loop,
    redirect_seo_risk,
)
from hype_frog.reporter.sheets.merged_builders import (
    build_redirect_map_rows,
    build_redirects_sheet_rows,
)


def test_format_redirect_chain_display_mixed_statuses() -> None:
    hops = [
        RedirectHopRecord(url="https://a.example/old", status=301),
        RedirectHopRecord(url="https://a.example/temp", status=302),
    ]
    display = format_redirect_chain_display(
        "https://a.example/start",
        hops,
        final_url="https://a.example/final",
    )
    assert "[301]" in display
    assert "[302]" in display
    assert "https://a.example/final" in display


def test_build_redirect_chain_fields_flags() -> None:
    hops = [
        RedirectHopRecord(url="https://a.example/hop1", status=301),
        RedirectHopRecord(url="https://a.example/hop2", status=302),
    ]
    fields = build_redirect_chain_fields(
        source_url="https://a.example/",
        hop_records=hops,
        final_url="https://a.example/final",
    )
    assert fields["Redirect Chain Length"] == 2
    assert fields["Has 302 in Chain"] is True
    assert fields["Has Mixed Redirect Types"] is True
    assert fields["Redirect Loop Flag"] is False
    hops_json = json.loads(fields["Redirect Chain Hops"])
    assert hops_json[0]["status"] == 301
    assert hops_json[1]["status"] == 302


def test_is_redirect_loop_when_source_equals_final() -> None:
    hops = [RedirectHopRecord(url="https://a.example/loop", status=302)]
    assert is_redirect_loop("https://a.example/", "https://a.example/", hops) is True


def test_build_redirect_map_row_hop_columns() -> None:
    hops = [
        RedirectHopRecord(url="https://a.example/1", status=301),
        RedirectHopRecord(url="https://a.example/2", status=302),
    ]
    fields = build_redirect_chain_fields(
        source_url="https://a.example/",
        hop_records=hops,
        final_url="https://a.example/final",
    )
    row = build_redirect_map_row(
        source_url="https://a.example/",
        hop_records=hops,
        final_url="https://a.example/final",
        fields=fields,
    )
    assert row["Hop 1 Status"] == 301
    assert row["Hop 2 Status"] == 302
    assert row["Has 302"] is True
    assert row["Chain Length"] == 2


def test_merged_builders_redirect_sheets() -> None:
    extra = {
        "URL": "https://a.example/",
        "Status Code": 200,
        "Final URL": "https://a.example/final",
        "Redirect Chain Length": 1,
        "Redirect Chain": "https://a.example/ → [301] → https://a.example/final",
        "Redirect Chain Hops": json.dumps(
            [{"url": "https://a.example/hop", "status": 301}]
        ),
        "Has 302 in Chain": False,
        "Has Mixed Redirect Types": False,
        "Redirect Loop Flag": False,
        "Redirect SEO Risk": "Single redirect",
    }
    redirects = build_redirects_sheet_rows([extra])
    assert len(redirects) == 1
    assert redirects[0]["Redirect Chain Length"] == 1

    map_rows = build_redirect_map_rows([extra])
    assert len(map_rows) == 1
    assert map_rows[0]["Source URL"] == "https://a.example/"
    assert map_rows[0]["Hop 1 Status"] == 301

    assert build_redirect_map_rows([{**extra, "Redirect Chain Length": 0}]) == []


def test_redirect_seo_risk_flags_chain_ending_in_error_status() -> None:
    """Regression (M5): a redirect chain that dead-ends in a 4xx/5xx must be
    flagged as risky, not classified identically to a healthy redirect."""
    hops = [RedirectHopRecord(url="https://a.example/old", status=301)]
    risk = redirect_seo_risk(
        hop_records=hops,
        redirect_loop=False,
        source_url="https://a.example/old",
        final_url="https://a.example/new",
        final_status=404,
    )
    assert risk == "Redirect chain ends in error (4xx/5xx)"


def test_redirect_seo_risk_healthy_single_redirect_unaffected_by_final_status() -> None:
    hops = [RedirectHopRecord(url="https://a.example/old", status=301)]
    risk = redirect_seo_risk(
        hop_records=hops,
        redirect_loop=False,
        source_url="https://a.example/old",
        final_url="https://a.example/new",
        final_status=200,
    )
    assert risk == "Single redirect"


def test_build_redirect_chain_fields_surfaces_error_ending_risk() -> None:
    hops = [RedirectHopRecord(url="https://a.example/old", status=301)]
    fields = build_redirect_chain_fields(
        source_url="https://a.example/old",
        hop_records=hops,
        final_url="https://a.example/new",
        final_status=404,
    )
    assert fields["Redirect SEO Risk"] == "Redirect chain ends in error (4xx/5xx)"


def test_has_temporary_and_mixed_helpers() -> None:
    permanent_only = [RedirectHopRecord(url="https://x/a", status=301)]
    mixed = [
        RedirectHopRecord(url="https://x/a", status=301),
        RedirectHopRecord(url="https://x/b", status=302),
    ]
    assert has_temporary_redirect(permanent_only) is False
    assert has_temporary_redirect(mixed) is True
    assert has_mixed_redirect_types(permanent_only) is False
    assert has_mixed_redirect_types(mixed) is True
