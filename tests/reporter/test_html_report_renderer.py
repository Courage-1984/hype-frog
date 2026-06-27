"""Test HTML report rendering produces valid self-contained HTML."""
import pytest
from hype_frog.reporter.html_report_data import ReportContext
from hype_frog.reporter.html_report_renderer import render_html_report


def test_render_produces_valid_html():
    ctx = ReportContext(
        domain="example.com",
        crawl_date="2026-06-27",
        total_urls=100,
        seo_health_mean=45.0,
        aeo_readiness_mean=30.0,
        psi_mobile_mean=52.0,
        critical_url_count=20,
        warning_url_count=30,
        observation_url_count=50,
        status_200_count=90,
        status_4xx_count=10,
        executive_narrative="Test narrative.",
        total_fix_hours=40.0,
    )
    html = render_html_report(ctx)

    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "example.com" in html
    assert "45.0%" in html  # SEO health KPI
    assert "30.0%" in html  # AEO readiness KPI
    assert 'class="kpi-card critical"' in html
    assert "<style>" in html
    # No external stylesheet or JS file references
    style_block = html.split("<style>")[1].split("</style>")[0]
    assert "http://" not in style_block
    assert ".js" not in html


def test_render_no_branding_leaks():
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    html = render_html_report(ctx)
    html_lower = html.lower()
    assert "hype-frog" not in html_lower
    assert "hype_frog" not in html_lower
    assert "hypefrog" not in html_lower
    assert "github.com" not in html_lower


def test_render_white_label_branding():
    ctx = ReportContext(
        domain="client.com",
        crawl_date="2026-06-27",
        total_urls=50,
        prepared_by="Logi-Ink Digital",
        client_name="Client Corp",
        brand_colour="#0a5c36",
        accent_colour="#e8a317",
    )
    html = render_html_report(ctx)
    assert "Client Corp" in html
    assert "Logi-Ink Digital" in html
    assert "#0a5c36" in html
    assert "#e8a317" in html


def test_render_print_safe():
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    html = render_html_report(ctx)
    assert "@media print" in html
    assert "page-break-before" in html


def test_render_gsc_unavailable():
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=5, gsc_available=False)
    html = render_html_report(ctx)
    assert "Google Search Console data was not available" in html


def test_render_gsc_available():
    ctx = ReportContext(
        domain="example.com",
        crawl_date="2026-06-27",
        total_urls=5,
        gsc_available=True,
        gsc_clicks_total=1234,
        gsc_impressions_total=9999,
        gsc_avg_position=4.5,
        gsc_pages_with_clicks=3,
    )
    html = render_html_report(ctx)
    assert "1,234" in html  # formatted clicks
    assert "9,999" in html  # formatted impressions


def test_render_severity_relabel_and_total():
    ctx = ReportContext(
        domain="example.com",
        crawl_date="2026-06-27",
        total_urls=100,
        critical_url_count=20,
        warning_url_count=30,
        observation_url_count=50,
    )
    html = render_html_report(ctx)
    assert "Pages by Worst Severity" in html
    assert "100 pages total" in html
    assert "highest-severity issue" in html


def test_render_quick_wins_section():
    ctx = ReportContext(
        domain="example.com",
        crawl_date="2026-06-27",
        total_urls=5,
        quick_wins=[
            {"name": "Missing Meta Description", "effort_hours": 4.0, "owner": "Copy Writer"},
        ],
    )
    html = render_html_report(ctx)
    assert "<h2>Quick Wins</h2>" in html
    assert "Missing Meta Description" in html
    assert "4.0h" in html


def test_render_quick_wins_empty():
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=5)
    html = render_html_report(ctx)
    assert "No quick wins identified" in html


def test_render_self_contained_no_external_urls():
    ctx = ReportContext(domain="example.com", crawl_date="2026-06-27", total_urls=1)
    html = render_html_report(ctx)
    # Confirm no CDN or external resource links
    assert "cdn." not in html
    assert 'src="http' not in html
    assert 'href="http' not in html
