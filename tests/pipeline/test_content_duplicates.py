"""WordPress draft slug and near-duplicate content detection."""

from __future__ import annotations

from hype_frog.core.models import ExtraRowPayload, MainRowPayload
from hype_frog.pipeline.content_duplicates import (
    enrich_content_duplicate_signals,
    heading_structure_fingerprint,
    is_wordpress_draft_slug,
    jaccard_similarity,
    strip_wordpress_draft_suffix,
)


def test_wordpress_copy_slug_detected() -> None:
    assert is_wordpress_draft_slug("amc-conference-speakers-2026-copy") is True
    had_suffix, base = strip_wordpress_draft_suffix("amc-conference-speakers-2026-copy")
    assert had_suffix is True
    assert base == "amc-conference-speakers-2026"


def test_heading_fingerprint_ignores_trivial_differences() -> None:
    main_a = {"H2 Content": "Speaker Lineup | Agenda", "H3 Content": "Day One"}
    main_b = {"H2 Content": "speaker lineup | agenda", "H3 Content": "day one"}
    assert heading_structure_fingerprint(main_a) == heading_structure_fingerprint(main_b)


def test_jaccard_similarity_high_for_overlapping_copy() -> None:
    from hype_frog.pipeline.content_duplicates import content_similarity_tokens

    main = {
        "H2 Content": "Featured Speakers | Conference Agenda",
        "H3 Content": "Opening Keynote | Panel Discussion",
    }
    extra = {
        "Current Page Copy Snippet": (
            "featured speakers conference agenda opening keynote panel discussion schedule"
        ),
        "Current H-Tag Structure": "h1: Speakers | h2: Featured Speakers",
    }
    tokens_a = content_similarity_tokens(main, extra)
    tokens_b = content_similarity_tokens(main, extra)
    assert jaccard_similarity(tokens_a, tokens_b) == 1.0


def test_copy_slug_points_to_canonical_sibling() -> None:
    canonical_main = MainRowPayload.model_validate(
        {
            "URL": "https://example.com/speakers/amc-conference-speakers-2026",
            "H2 Content": "Featured Speakers | Agenda",
            "H3 Content": "Day One | Day Two",
        }
    )
    copy_main = MainRowPayload.model_validate(
        {
            "URL": "https://example.com/speakers/amc-conference-speakers-2026-copy",
            "H2 Content": "Featured Speakers | Agenda",
            "H3 Content": "Day One | Day Two",
        }
    )
    canonical_extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/speakers/amc-conference-speakers-2026",
            "Final URL": "https://example.com/speakers/amc-conference-speakers-2026",
            "Current Page Copy Snippet": (
                "featured speakers agenda day one day two opening keynote panel discussion"
            ),
        }
    )
    copy_extra = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/speakers/amc-conference-speakers-2026-copy",
            "Final URL": "https://example.com/speakers/amc-conference-speakers-2026-copy",
            "Current Page Copy Snippet": (
                "featured speakers agenda day one day two opening keynote panel discussion draft"
            ),
        }
    )
    enriched = enrich_content_duplicate_signals(
        [canonical_main, copy_main],
        [canonical_extra, copy_extra],
        inlinks_map={},
    )
    by_url = {str(row.values["URL"]): row.values for row in enriched}
    copy_row = by_url["https://example.com/speakers/amc-conference-speakers-2026-copy"]
    assert copy_row["Draft Page Flag"] is True
    assert copy_row["Probable Duplicate Flag"] is True
    assert copy_row["Duplicate Of URL"] == (
        "https://example.com/speakers/amc-conference-speakers-2026"
    )
    assert "Probable duplicate of" in str(copy_row["Cannibalization Hint"])
    assert copy_row["Heading Structure Cluster Size"] == 2


def test_repeated_headings_without_copy_slug_still_flags_cluster() -> None:
    main_a = MainRowPayload.model_validate(
        {
            "URL": "https://example.com/events/speakers",
            "H2 Content": "Speaker Bios | Schedule",
            "H3 Content": "Track One | Track Two",
        }
    )
    main_b = MainRowPayload.model_validate(
        {
            "URL": "https://example.com/events/speakers-v2",
            "H2 Content": "Speaker Bios | Schedule",
            "H3 Content": "Track One | Track Two",
        }
    )
    extra_a = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/events/speakers",
            "Current Page Copy Snippet": "speaker bios schedule track one track two keynote panel",
        }
    )
    extra_b = ExtraRowPayload.model_validate(
        {
            "URL": "https://example.com/events/speakers-v2",
            "Current Page Copy Snippet": "speaker bios schedule track one track two keynote panel updated",
        }
    )
    enriched = enrich_content_duplicate_signals(
        [main_a, main_b],
        [extra_a, extra_b],
        inlinks_map={},
    )
    flagged = [row for row in enriched if row.values.get("Probable Duplicate Flag")]
    assert len(flagged) >= 1
    hints = " ".join(str(row.values.get("Cannibalization Hint") or "") for row in enriched)
    assert "Probable duplicate of" in hints or "Repeated H2/H3" in hints
