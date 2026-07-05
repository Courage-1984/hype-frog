"""Direct tests for crawl_runner_interactive.py (preset resolution + interactive prompts).

Previously only exercised indirectly through crawl_runner.py's public API, which
never reaches the interactive-prompt fallback path (test fixtures always set a
workers_preset). This file targets prompt_crawl_options_sync's input() branches
and resolve_crawl_runtime_options's preset-vs-interactive dispatch directly.
"""

from __future__ import annotations

import pytest

from hype_frog.orchestration.crawl_runner_interactive import (
    CrawlRuntimeOptions,
    prompt_crawl_options_sync,
    resolve_crawl_runtime_options,
)
from hype_frog.orchestration.run_setup import RunSetup


def _build_run_setup(**overrides: object) -> RunSetup:
    base: dict[str, object] = dict(
        target_input="https://example.com",
        max_urls=None,
        max_psi_urls=None,
        high_value_slugs=[],
        crawl_mode="fast",
        render_wait_ms=1000,
        selector_wait_ms=500,
        workers_preset=None,
        request_delay_preset=None,
        full_suite_preset=None,
        hide_advanced_tabs_preset=None,
        previous_audit_path_preset=None,
        checkpoint_every_preset=None,
        resume_checkpoint_mode="no",
        check_external_link_status=False,
    )
    base.update(overrides)
    return RunSetup(**base)  # type: ignore[arg-type]


def _mock_inputs(monkeypatch: pytest.MonkeyPatch, values: list[str]) -> None:
    responses = iter(values)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))


def test_prompt_crawl_options_sync_gentle_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_inputs(monkeypatch, ["1", "1", "1", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.workers == 2
    assert options.request_delay == 4.0
    assert options.full_suite is False


def test_prompt_crawl_options_sync_faster_profile_and_full_suite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["3", "2", "1", "", "5"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.workers == 4
    assert options.request_delay == 1.5
    assert options.full_suite is True
    assert options.checkpoint_every == 5


def test_prompt_crawl_options_sync_blank_profile_defaults_balanced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["", "1", "1", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    from hype_frog.orchestration.crawl_runner_interactive import MAX_WORKERS

    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.workers == MAX_WORKERS


def test_prompt_crawl_options_sync_invalid_profile_defaults_balanced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["garbage", "1", "1", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    from hype_frog.orchestration.crawl_runner_interactive import MAX_WORKERS

    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.workers == MAX_WORKERS


def test_prompt_crawl_options_sync_invalid_suite_choice_defaults_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["2", "garbage", "1", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.full_suite is True


def test_prompt_crawl_options_sync_previous_path_falls_back_to_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["2", "1", "1", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "/env/previous.xlsx",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.previous_audit_path == "/env/previous.xlsx"


def test_prompt_crawl_options_sync_previous_path_explicit_input_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["2", "1", "1", "/typed/previous.xlsx", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "/env/previous.xlsx",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.previous_audit_path == "/typed/previous.xlsx"


def test_prompt_crawl_options_sync_invalid_checkpoint_defaults_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["2", "1", "1", "", "not-a-number"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.checkpoint_every == 0


def test_prompt_crawl_options_sync_tabs_choice_show_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["2", "1", "2", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.hide_advanced_tabs is False


def test_prompt_crawl_options_sync_tabs_choice_blank_defaults_hide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["2", "1", "", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.hide_advanced_tabs is True


def test_prompt_crawl_options_sync_tabs_choice_invalid_defaults_hide(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _mock_inputs(monkeypatch, ["2", "1", "garbage", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    options = prompt_crawl_options_sync(_build_run_setup())
    assert options.hide_advanced_tabs is True


def test_prompt_crawl_options_sync_tabs_choice_skipped_when_preset_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: an explicit --show-all-tabs override must not still ask the
    question during an otherwise-interactive run."""
    # Only 4 inputs — if the tabs prompt fired anyway, this would consume the
    # wrong input for a later question and the test would fail loudly.
    _mock_inputs(monkeypatch, ["2", "1", "", "0"])
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "",
    )
    setup = _build_run_setup(hide_advanced_tabs_preset=False)
    options = prompt_crawl_options_sync(setup)
    assert options.hide_advanced_tabs is False


@pytest.mark.asyncio
async def test_resolve_crawl_runtime_options_uses_preset_when_provided() -> None:
    setup = _build_run_setup(
        workers_preset=6,
        request_delay_preset=0.25,
        full_suite_preset=True,
        previous_audit_path_preset="/preset/prev.xlsx",
        checkpoint_every_preset=10,
    )
    options = await resolve_crawl_runtime_options(setup)
    assert options == CrawlRuntimeOptions(
        workers=6,
        request_delay=0.25,
        full_suite=True,
        previous_audit_path="/preset/prev.xlsx",
        checkpoint_every=10,
    )


@pytest.mark.asyncio
async def test_resolve_crawl_runtime_options_preset_falls_back_to_env_for_previous_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.get_hf_previous_audit_path",
        lambda: "/env/prev.xlsx",
    )
    setup = _build_run_setup(
        workers_preset=3,
        request_delay_preset=None,
        full_suite_preset=False,
        previous_audit_path_preset="",
        checkpoint_every_preset=None,
    )
    options = await resolve_crawl_runtime_options(setup)
    assert options.previous_audit_path == "/env/prev.xlsx"
    assert options.checkpoint_every == 0


@pytest.mark.asyncio
async def test_resolve_crawl_runtime_options_falls_back_to_interactive_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: no test previously reached the asyncio.to_thread(...)
    interactive-prompt fallback — every fixture set a workers_preset."""
    setup = _build_run_setup(workers_preset=None)
    expected = CrawlRuntimeOptions(
        workers=2,
        request_delay=4.0,
        full_suite=False,
        previous_audit_path="",
        checkpoint_every=0,
    )
    called_with: list[RunSetup] = []

    def fake_prompt(s: RunSetup) -> CrawlRuntimeOptions:
        called_with.append(s)
        return expected

    monkeypatch.setattr(
        "hype_frog.orchestration.crawl_runner_interactive.prompt_crawl_options_sync",
        fake_prompt,
    )
    options = await resolve_crawl_runtime_options(setup)
    assert options == expected
    assert called_with == [setup]
