from __future__ import annotations

import pytest

from hype_frog.crawler.data_assembler import (
    _append_schema_ld_image_value,
    _collect_raw_og_image_candidates,
    _dedupe_preserve_order,
    _has_truthy_header,
    _json_ld_walk_collect_images,
    _normalize_candidate_image_url,
    assemble_from_html,
    finalize_row_state,
    init_rows,
    readability_flesch,
    url_depth,
)
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.export import sanitize_rows


def test_assemble_from_html_populates_typed_payload_offline() -> None:
    html = """
    <html>
      <head>
        <title>Enterprise SEO Migration Guide</title>
        <meta name="description" content="A practical migration guide for enterprise SEO teams." />
        <meta name="keywords" content="seo, migration, enterprise" />
        <link rel="canonical" href="/guide" />
        <meta property="og:title" content="Enterprise SEO Migration Guide" />
        <meta property="og:description" content="Guide summary" />
        <meta property="og:image" content="https://example.com/og.jpg" />
      </head>
      <body class="page page-id-99">
        <main>
          <h1>Migration playbook</h1>
          <h2>What is enterprise SEO migration?</h2>
          <p>Enterprise SEO migration is a structured transition process that protects rankings while systems, URLs, and templates evolve across large websites and teams.</p>
          <a href="/internal-page">Read more</a>
        </main>
      </body>
    </html>
    """
    main_dict, extra_dict = init_rows("https://example.com/guide", None)
    main_payload = MainRowPayload.model_validate(main_dict)
    extra_payload = ExtraRowPayload.model_validate(extra_dict)

    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/guide",
    )
    finalize_row_state(main_payload, extra_payload)

    main = main_payload.values
    extra = extra_payload.values

    assert main["Title"] == "Enterprise SEO Migration Guide"
    assert main["Meta Description"] == "A practical migration guide for enterprise SEO teams."
    assert main["Meta Desc Length"] == len(
        "A practical migration guide for enterprise SEO teams."
    )
    assert main["Indexability"] == "Indexable"
    assert main["OG-Image"] == "https://example.com/og.jpg"

    assert extra["WordPress Post ID"] == 99
    assert extra["Canonical Type"] == "self"
    assert extra["Canonical URL"] == "https://example.com/guide"
    assert extra["H1 Count"] == 1
    assert extra["Title Missing"] is False
    assert extra["Meta Description Missing"] is False
    assert extra["Internal Links Count"] == 1
    assert extra["Indexability Reason"] == "Indexable"
    assert main["Extraction State"] == "complete"


def test_assemble_from_html_og_image_relative_resolves_to_absolute() -> None:
    html = """
    <html>
      <head>
        <title>Rel OG</title>
        <meta property="og:image" content="/assets/share.png" />
      </head>
      <body><main><h1>H</h1><p>Body.</p></main></body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/blog/post", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/blog/post",
    )
    finalize_row_state(main_payload, extra_payload)
    assert main_payload.values["OG-Image"] == "https://example.com/assets/share.png"


def test_assemble_from_html_og_image_secure_url_meta() -> None:
    html = """
    <html>
      <head>
        <title>Secure OG</title>
        <meta property="og:image:secure_url" content="https://cdn.example.com/hi.webp" />
      </head>
      <body><main><h1>H</h1><p>Body.</p></main></body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/p", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/p",
    )
    finalize_row_state(main_payload, extra_payload)
    assert main_payload.values["OG-Image"] == "https://cdn.example.com/hi.webp"


def test_assemble_from_html_og_image_from_json_ld_article() -> None:
    html = """
    <html>
      <head>
        <title>JSON-LD image</title>
        <script type="application/ld+json">
        {"@type": "Article", "image": "https://static.example.org/hero.jpg"}
        </script>
      </head>
      <body><main><h1>H</h1><p>Body.</p></main></body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/news/a", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/news/a",
    )
    finalize_row_state(main_payload, extra_payload)
    assert main_payload.values["OG-Image"] == "https://static.example.org/hero.jpg"


def test_assemble_from_html_og_image_scheme_relative_twitter() -> None:
    html = """
    <html>
      <head>
        <title>Protocol-relative</title>
        <meta name="twitter:image" content="//img.example.net/x.png" />
      </head>
      <body><main><h1>H</h1><p>Body.</p></main></body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/",
    )
    finalize_row_state(main_payload, extra_payload)
    assert main_payload.values["OG-Image"] == "https://img.example.net/x.png"


def test_assemble_from_malformed_html_is_resilient() -> None:
    html = """
    <html>
      <head><title>Broken Title<title><meta name="description" content="desc"
      <body class="page-id-7">
        <h1>Broken heading
        <p>Unclosed tags can happen in production pages.
        <a href="/a">a<a href="/b">b
      </body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/broken", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/broken",
    )
    finalize_row_state(main_payload, extra_payload)

    main = main_payload.values
    extra = extra_payload.values
    assert main["Title"] is None or "Broken Title" in str(main["Title"])
    assert extra["H1 Count"] >= 1
    assert main["Extraction State"] == "complete"


def test_assemble_with_missing_elements_uses_safe_defaults() -> None:
    html = "<html><body><main><p>Plain body only.</p></main></body></html>"
    main_payload, extra_payload = init_rows("https://example.com/minimal", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/minimal",
    )
    finalize_row_state(main_payload, extra_payload)

    main = main_payload.values
    extra = extra_payload.values
    assert main["Title"] is None
    assert main["Meta Description"] is None
    assert main["Meta Desc Length"] == 0
    assert extra["Title Missing"] is True
    assert extra["Meta Description Missing"] is True
    assert extra["H1 Count"] == 0
    assert extra["Missing H1 Flag"] is True
    assert main["Extraction State"] == "complete"


def test_assemble_excludes_sidebar_widget_content_without_main_tag() -> None:
    """Regression (H2/M4): templates with no <main>/<article>/[role=main] must
    not bleed sidebar/widget text (or its <ul>) into the extracted body text
    and list/table detection — only nav/header/footer/aside/script were being
    stripped before, leaving WordPress "recent posts" widgets in scope."""
    html = """
    <html>
      <head><title>Conference Page</title></head>
      <body>
        <div class="sidebar widget_recent_entries">
          <h3>Recent Posts</h3>
          <ul>
            <li>Old announcement one</li>
            <li>Old announcement two</li>
          </ul>
          <p>Shared sidebar boilerplate text about unrelated news.</p>
        </div>
        <div class="content-area">
          <h1>Marketing Conference Africa</h1>
          <p>
            This year's marketing conference in Africa brings together
            keynote speakers and workshops focused on brand strategy.
          </p>
        </div>
      </body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/conference", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/conference",
    )
    extra = extra_payload.values

    body_text = str(extra["Body Text Excerpt"])
    assert "keynote speakers" in body_text.lower()
    assert "sidebar boilerplate" not in body_text.lower()
    assert "old announcement" not in body_text.lower()
    assert "recent posts" not in body_text.lower()

    # The only <ul> on the page lives inside the sidebar widget — once excluded,
    # there's no real list/table/question-heading in the main content, so
    # AEO Extractability Score must read "Low", not "Medium"/"High".
    assert extra["AEO Extractability Score"] == "Low"


def test_assemble_still_detects_a_real_list_in_main_content() -> None:
    """The sidebar/widget strip must not suppress a genuine list that's part
    of the actual page content (no false negative from the H2/M4 fix)."""
    html = """
    <html>
      <head><title>Steps Page</title></head>
      <body>
        <div class="content-area">
          <h1>How To Register</h1>
          <ul>
            <li>Step one: create an account</li>
            <li>Step two: choose a package</li>
            <li>Step three: confirm payment</li>
          </ul>
        </div>
      </body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/register", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/register",
    )
    assert extra_payload.values["AEO Extractability Score"] in {"Medium", "High"}


def test_assemble_excludes_sidebar_widget_even_when_main_tag_present() -> None:
    """A <main> tag that itself contains a nested sidebar/widget region (some
    WordPress themes do this) should still have that region stripped."""
    html = """
    <html>
      <head><title>Conference Page</title></head>
      <body>
        <main>
          <div class="content-area">
            <h1>Marketing Conference Africa</h1>
            <p>
              This year's marketing conference in Africa brings together
              keynote speakers and workshops focused on brand strategy.
            </p>
          </div>
          <div class="widget-area sidebar">
            <ul>
              <li>Old announcement one</li>
              <li>Old announcement two</li>
            </ul>
            <p>Shared sidebar boilerplate text about unrelated news.</p>
          </div>
        </main>
      </body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/conference2", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/conference2",
    )
    extra = extra_payload.values
    body_text = str(extra["Body Text Excerpt"])
    assert "keynote speakers" in body_text.lower()
    assert "sidebar boilerplate" not in body_text.lower()
    assert extra["AEO Extractability Score"] == "Low"


def test_assemble_with_giant_link_payload_counts_correctly() -> None:
    links = "".join(f'<a href="/internal-{idx}">link {idx}</a>' for idx in range(3000))
    html = f"""
    <html>
      <head><title>Many Links</title></head>
      <body><main><h1>Scale Test</h1>{links}</main></body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/scale", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/scale",
    )
    finalize_row_state(main_payload, extra_payload)

    extra = extra_payload.values
    assert extra["Internal Links Count"] == 3000
    assert extra["Unique Internal Links Count"] == 3000
    assert len(extra["Internal Links List"]) == 200
    assert len(extra["Internal Links List Full"]) == 3000
    assert len(extra["Link Details"]) == 3000
    assert main_payload.values["Extraction State"] == "complete"


def test_assemble_character_encoding_remains_excel_safe_after_sanitize() -> None:
    html = """
    <html>
      <head><title>Emoji 😀 عربى 日本語 \x0b</title></head>
      <body>
        <h1>Заголовок 😀</h1>
        <p>Mixed script text with printable unicode is expected.</p>
      </body>
    </html>
    """
    main_payload, extra_payload = init_rows("https://example.com/encoding", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/encoding",
    )
    finalize_row_state(main_payload, extra_payload)

    sanitized_main = sanitize_rows([main_payload.values])[0]
    sanitized_extra = sanitize_rows([extra_payload.values])[0]
    assert "😀" in str(sanitized_main["Title"])
    assert "日本語" in str(sanitized_main["Title"])
    assert "\x0b" not in str(sanitized_main["Title"])
    assert "Заголовок 😀" in str(sanitized_extra["Current H-Tag Structure"] or "")
    assert main_payload.values["Extraction State"] == "complete"


def test_init_rows_populates_sitemap_metadata_including_images() -> None:
    sitemap_meta = {
        "https://example.com/page": {
            "changefreq": "weekly",
            "priority": "0.8",
            "lastmod": "2026-01-01",
            "image_count": 2,
            "first_image_url": "https://example.com/img1.jpg",
        }
    }
    main_dict, extra_dict = init_rows("https://example.com/page", sitemap_meta)
    extra_payload = ExtraRowPayload.model_validate(extra_dict)
    assert extra_payload.values["Change Frequency"] == "weekly"
    assert extra_payload.values["Priority"] == "0.8"
    assert extra_payload.values["Last Updated"] == "2026-01-01"
    assert extra_payload.values["Sitemap Image Count"] == 2
    assert extra_payload.values["Sitemap First Image"] == "https://example.com/img1.jpg"


def test_init_rows_sitemap_lookup_survives_url_normalization_mismatch() -> None:
    # sitemap_meta keys are normalized upstream; init_rows must look up by the
    # normalized URL, not require the raw url param to already match exactly.
    sitemap_meta = {
        "https://example.com/page": {
            "changefreq": "monthly",
            "priority": None,
            "lastmod": None,
            "image_count": 0,
            "first_image_url": None,
        }
    }
    main_dict, extra_dict = init_rows("https://example.com/page/", sitemap_meta)
    extra_payload = ExtraRowPayload.model_validate(extra_dict)
    assert extra_payload.values["Change Frequency"] == "monthly"


def test_finalize_row_state_http_404_sets_not_indexable() -> None:
    main_dict, extra_dict = init_rows("https://example.com/missing", None)
    main_payload = MainRowPayload.model_validate(main_dict)
    extra_payload = ExtraRowPayload.model_validate(extra_dict)
    extra_payload.values["Status Code"] = 404
    finalize_row_state(main_payload, extra_payload)
    assert main_payload.values["Indexability"] == "Not Indexable"
    assert extra_payload.values["Indexability Reason"] == "HTTP 404"


@pytest.mark.parametrize(
    ("status_code", "expected_reason"),
    [
        ("Timeout", "Request Timeout"),
        ("timeout", "Request timeout"),
        ("Connection Error", "Request Connection Error"),
        ("connection error", "Request connection error"),
        ("DNS Error", "Request DNS Error"),
        ("Error", "Request Error"),
    ],
)
def test_finalize_row_state_request_failures_set_not_indexable(
    status_code: str,
    expected_reason: str,
) -> None:
    main_dict, extra_dict = init_rows("https://example.com/slow", None)
    main_payload = MainRowPayload.model_validate(main_dict)
    extra_payload = ExtraRowPayload.model_validate(extra_dict)
    main_payload.values["Status Code"] = status_code
    extra_payload.values["Status Code"] = status_code
    finalize_row_state(main_payload, extra_payload)
    assert main_payload.values["Indexability"] == "Not Indexable"
    assert extra_payload.values["Indexability Reason"] == expected_reason


# ---------------------------------------------------------------------------
# readability_flesch
# ---------------------------------------------------------------------------


def test_readability_flesch_typical_values_produce_bounded_score() -> None:
    score = readability_flesch(words=100, sentences=8, syllables=140)
    assert score is not None
    assert 0.0 <= score <= 100.0


def test_readability_flesch_zero_words_returns_none() -> None:
    assert readability_flesch(words=0, sentences=5, syllables=10) is None


def test_readability_flesch_zero_sentences_returns_none() -> None:
    assert readability_flesch(words=50, sentences=0, syllables=10) is None


def test_readability_flesch_extreme_inputs_clamp_to_bounds() -> None:
    """Degenerate inputs (very long words/sentences) must clamp to the
    documented [0, 100] range rather than returning an out-of-range score."""
    high = readability_flesch(words=10, sentences=10, syllables=10)
    assert high is not None
    assert high <= 100.0
    low = readability_flesch(words=100, sentences=1, syllables=1000)
    assert low is not None
    assert low >= 0.0


# ---------------------------------------------------------------------------
# url_depth
# ---------------------------------------------------------------------------


def test_url_depth_root_is_zero() -> None:
    assert url_depth("https://example.com/") == 0
    assert url_depth("https://example.com") == 0


def test_url_depth_counts_path_segments() -> None:
    assert url_depth("https://example.com/a/b/c") == 3


# ---------------------------------------------------------------------------
# _has_truthy_header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        (False, False),
        ("", False),
        ("   ", False),
        ("value", True),
        (0, False),
        (1, True),
        ([], False),
        ([1], True),
    ],
)
def test_has_truthy_header(value: object, expected: bool) -> None:
    assert _has_truthy_header(value) is expected


# ---------------------------------------------------------------------------
# _normalize_candidate_image_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scheme",
    ["javascript:alert(1)", "data:image/png;base64,abc", "vbscript:msgbox(1)", "file:///etc/passwd", "about:blank"],
)
def test_normalize_candidate_image_url_rejects_dangerous_schemes(scheme: str) -> None:
    assert _normalize_candidate_image_url(scheme, "https://example.com/") is None


def test_normalize_candidate_image_url_blank_returns_none() -> None:
    assert _normalize_candidate_image_url("", "https://example.com/") is None
    assert _normalize_candidate_image_url(None, "https://example.com/") is None


def test_normalize_candidate_image_url_scheme_relative_gets_https() -> None:
    result = _normalize_candidate_image_url("//cdn.example.com/img.jpg", "https://example.com/")
    assert result is not None
    assert result.startswith("https://cdn.example.com")


def test_normalize_candidate_image_url_relative_resolves_against_base() -> None:
    result = _normalize_candidate_image_url("/img/photo.jpg", "https://example.com/page")
    assert result == "https://example.com/img/photo.jpg"


def test_normalize_candidate_image_url_already_absolute_passthrough() -> None:
    result = _normalize_candidate_image_url("https://example.com/img.jpg", "https://example.com/")
    assert result == "https://example.com/img.jpg"


# ---------------------------------------------------------------------------
# _dedupe_preserve_order
# ---------------------------------------------------------------------------


def test_dedupe_preserve_order_removes_duplicates_keeps_first_occurrence_order() -> None:
    assert _dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_dedupe_preserve_order_empty_list() -> None:
    assert _dedupe_preserve_order([]) == []


# ---------------------------------------------------------------------------
# _append_schema_ld_image_value
# ---------------------------------------------------------------------------


def test_append_schema_ld_image_value_string() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value("https://example.com/img.jpg", bucket)
    assert bucket == ["https://example.com/img.jpg"]


def test_append_schema_ld_image_value_dict_with_url_key() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value({"url": "https://example.com/img.jpg"}, bucket)
    assert bucket == ["https://example.com/img.jpg"]


def test_append_schema_ld_image_value_dict_with_content_url_key() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value({"contentUrl": "https://example.com/img.jpg"}, bucket)
    assert bucket == ["https://example.com/img.jpg"]


def test_append_schema_ld_image_value_dict_with_id_key() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value({"@id": "https://example.com/img.jpg"}, bucket)
    assert bucket == ["https://example.com/img.jpg"]


def test_append_schema_ld_image_value_dict_id_key_ignores_non_http() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value({"@id": "#local-fragment"}, bucket)
    assert bucket == []


def test_append_schema_ld_image_value_nested_image_key() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value(
        {"image": {"url": "https://example.com/nested.jpg"}}, bucket
    )
    assert bucket == ["https://example.com/nested.jpg"]


def test_append_schema_ld_image_value_list_of_items() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value(
        ["https://example.com/a.jpg", {"url": "https://example.com/b.jpg"}], bucket
    )
    assert bucket == ["https://example.com/a.jpg", "https://example.com/b.jpg"]


def test_append_schema_ld_image_value_none_is_noop() -> None:
    bucket: list[str] = []
    _append_schema_ld_image_value(None, bucket)
    assert bucket == []


# ---------------------------------------------------------------------------
# _json_ld_walk_collect_images
# ---------------------------------------------------------------------------


def test_json_ld_walk_collect_images_finds_nested_image_key() -> None:
    bucket: list[str] = []
    _json_ld_walk_collect_images(
        {"@type": "Article", "image": "https://example.com/article.jpg"}, bucket
    )
    assert bucket == ["https://example.com/article.jpg"]


def test_json_ld_walk_collect_images_depth_limit_stops_recursion() -> None:
    """A pathologically deep JSON-LD structure must not cause unbounded
    recursion — the depth cutoff silently stops collecting instead."""
    bucket: list[str] = []
    _json_ld_walk_collect_images(
        {"image": "https://example.com/too-deep.jpg"}, bucket, depth=19
    )
    assert bucket == []


def test_json_ld_walk_collect_images_walks_list_of_nodes() -> None:
    bucket: list[str] = []
    _json_ld_walk_collect_images(
        [{"image": "https://example.com/a.jpg"}, {"thumbnailUrl": "https://example.com/b.jpg"}],
        bucket,
    )
    assert bucket == ["https://example.com/a.jpg", "https://example.com/b.jpg"]


# ---------------------------------------------------------------------------
# _collect_raw_og_image_candidates — meta/link variants beyond og:image
# ---------------------------------------------------------------------------


def test_collect_raw_og_image_candidates_twitter_image_as_property_attr() -> None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        '<html><head><meta property="twitter:image" content="https://example.com/tw.jpg">'
        "</head><body></body></html>",
        "lxml",
    )
    assert "https://example.com/tw.jpg" in _collect_raw_og_image_candidates(soup)


def test_collect_raw_og_image_candidates_itemprop_image() -> None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        '<html><head><meta itemprop="image" content="https://example.com/schema.jpg">'
        "</head><body></body></html>",
        "lxml",
    )
    assert "https://example.com/schema.jpg" in _collect_raw_og_image_candidates(soup)


def test_collect_raw_og_image_candidates_link_rel_image_src() -> None:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        '<html><head><link rel="image_src" href="https://example.com/link.jpg">'
        "</head><body></body></html>",
        "lxml",
    )
    assert "https://example.com/link.jpg" in _collect_raw_og_image_candidates(soup)
