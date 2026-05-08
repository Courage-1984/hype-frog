from __future__ import annotations

from hype_frog.crawler.data_assembler import assemble_from_html, finalize_row_state, init_rows
from hype_frog.models import ExtraRowPayload, MainRowPayload


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
