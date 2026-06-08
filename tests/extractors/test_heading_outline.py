from __future__ import annotations

from hype_frog.crawler.data_assembler import assemble_from_html, finalize_row_state, init_rows
from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.extractors.page import extract_heading_outline


def test_heading_outline_preserves_document_order_and_all_levels() -> None:
    html = """
    <html><body>
      <main>
        <h1>Playbook</h1>
        <h2>Section A</h2>
        <h3>Detail A1</h3>
        <h4>Detail A1a</h4>
        <h2>Section B</h2>
        <h5>Footnote level</h5>
        <h6>Fine print</h6>
      </main>
    </body></html>
    """
    outline = extract_heading_outline(html)
    assert outline.h1_count == 1
    assert outline.outline_lines == (
        "H1: Playbook",
        "H2: Section A",
        "H3: Detail A1",
        "H4: Detail A1a",
        "H2: Section B",
        "H5: Footnote level",
        "H6: Fine print",
    )
    assert outline.headings_by_level[2] == ("Section A", "Section B")


def test_heading_outline_excludes_chrome_and_hidden_headings() -> None:
    html = """
    <html><body>
      <header><h1>Site Logo Title</h1></header>
      <nav><h2>Menu</h2></nav>
      <main>
        <h1>Real page title</h1>
        <h2 class="sr-only">Hidden section</h2>
        <h2 aria-hidden="true">Also hidden</h2>
        <h2>Visible section</h2>
      </main>
      <footer><h3>Footer promo</h3></footer>
    </body></html>
    """
    outline = extract_heading_outline(html)
    assert outline.h1_count == 1
    assert outline.current_h_tag_structure == "H1: Real page title\nH2: Visible section"


def test_heading_outline_supports_aria_role_headings() -> None:
    html = """
    <html><body><main>
      <div role="heading" aria-level="1">Role heading one</div>
      <p>Body</p>
      <div role="heading" aria-level="3">Role heading three</div>
    </main></body></html>
    """
    outline = extract_heading_outline(html)
    assert outline.h1_count == 1
    assert "H1: Role heading one" in outline.outline_lines
    assert "H3: Role heading three" in outline.outline_lines


def test_heading_outline_counts_multiple_h1_in_content() -> None:
    html = """
    <html><body><main>
      <h1>First</h1>
      <h1>Second</h1>
    </main></body></html>
    """
    outline = extract_heading_outline(html)
    assert outline.h1_count == 2
    assert outline.headings_by_level[1] == ("First", "Second")


def test_heading_outline_finds_h1_in_header_when_main_absent() -> None:
    """Homepage heroes outside ``<main>`` should still yield a primary H1."""
    html = """
    <html><body>
      <header class="hero"><h1>Welcome to the conference</h1></header>
      <div class="content"><p>Intro copy.</p></div>
    </body></html>
    """
    outline = extract_heading_outline(html)
    assert outline.h1_count == 1
    assert outline.headings_by_level[1] == ("Welcome to the conference",)


def test_heading_outline_cms_elementor_h1_selector() -> None:
    html = """
    <html><body>
      <div class="elementor-widget-heading">
        <h1 class="elementor-heading-title">Elementor page title</h1>
      </div>
      <p>Body</p>
    </body></html>
    """
    outline = extract_heading_outline(html)
    assert outline.h1_count == 1
    assert "Elementor page title" in outline.headings_by_level[1]


def test_heading_outline_allows_pipe_character_in_single_h1() -> None:
    html = """
    <html><body><main><h1>Tips | Tools for marketers</h1></main></body></html>
    """
    outline = extract_heading_outline(html)
    assert outline.h1_count == 1
    assert outline.headings_by_level[1][0] == "Tips | Tools for marketers"


def test_assemble_populates_main_heading_fields_from_outline() -> None:
    html = """
    <html><body><main>
      <h1>Primary</h1>
      <h2>Sub one</h2>
      <h2>Sub two</h2>
      <h3>Nested</h3>
    </main></body></html>
    """
    main_payload, extra_payload = init_rows("https://example.com/page", None)
    assemble_from_html(
        main_data=main_payload,
        extra=extra_payload,
        html=html,
        resolved_url="https://example.com/page",
    )
    finalize_row_state(main_payload, extra_payload)

    assert extra_payload.values["Primary H1 Content"] == "Primary"
    assert main_payload.values["H1 Content"] == "Primary"
    assert main_payload.values["H2 Content"] == "Sub one | Sub two"
    assert main_payload.values["H3 Content"] == "Nested"
    assert "H4:" not in (extra_payload.values.get("Current H-Tag Structure") or "")
