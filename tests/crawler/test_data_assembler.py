from __future__ import annotations

from hype_frog.crawler.data_assembler import assemble_from_html, finalize_row_state, init_rows
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
    assert main["Extraction State"] == "skipped"


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
    assert main["Extraction State"] == "skipped"


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
    assert main["Extraction State"] == "skipped"


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
    assert main_payload.values["Extraction State"] == "skipped"


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
    assert main_payload.values["Extraction State"] == "skipped"
