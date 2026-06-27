"""Competitor benchmark row builder (B5)."""

from __future__ import annotations

from hype_frog.analysis.competitor_benchmarks import build_competitor_benchmark_rows


def test_build_competitor_benchmark_rows_shapes_comparison_table() -> None:
    rows, columns = build_competitor_benchmark_rows(
        client_label="client.example",
        client_metrics={"avg_aeo_proxy_score": 55.0, "title_coverage_pct": 90.0},
        competitor_metrics={
            "rival.example": {
                "avg_aeo_proxy_score": 72.0,
                "title_coverage_pct": 100.0,
            }
        },
    )
    assert columns == ("Metric", "Client Site", "rival.example")
    aeo_row = next(row for row in rows if row["Metric"] == "Average AEO / Readiness Score")
    assert aeo_row["Client Site"] == 55.0
    assert aeo_row["rival.example"] == 72.0
