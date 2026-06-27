"""Deterministic topical-cluster id derivation."""

from __future__ import annotations

from hype_frog.pipeline.content_cluster import compute_content_cluster_id


def test_uses_first_path_segment_and_title() -> None:
    assert (
        compute_content_cluster_id("https://s.test/blog/post-name", title="My Title")
        == "blog-my-title"
    )


def test_digits_are_templatised_to_placeholder() -> None:
    cid = compute_content_cluster_id("https://s.test/blog/post", title="Top 10 Tips")
    assert cid.startswith("blog-")
    assert "{n}" in cid


def test_falls_back_to_url_slug_when_title_missing() -> None:
    assert (
        compute_content_cluster_id("https://s.test/services/seo-audit", title="")
        == "services-seo-audit"
    )


def test_empty_url_and_title_yield_home_untitled() -> None:
    assert compute_content_cluster_id("", title="") == "home-untitled"


def test_long_title_is_truncated() -> None:
    cid = compute_content_cluster_id(
        "https://s.test/x/y", title="a very long marketing focused title that exceeds the cap"
    )
    # Title segment capped at 24 chars before the URL segment prefix is added.
    title_part = cid.split("-", 1)[1]
    assert len(title_part.replace("-", " ")) <= 24
