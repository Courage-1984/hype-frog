"""Unit tests for :mod:`hype_frog.main` — the CLI entry-point dispatch layer.

Covers ``run()``'s structured-vs-legacy routing and both ``_run_structured``/
``_run_legacy`` command trees. Every downstream subsystem (validation, semantic/
Playwright install, GSC auth, quick-test/full-smoke gates, the async orchestrator
entry point) is mocked at the ``hype_frog.main`` (or, for lazily-imported names,
their origin module) boundary — this file tests routing/dispatch logic only, not
the subsystems themselves, which have their own test suites.

Existing coverage before this file: only ``_parse_args`` (via
``tests/core/test_cli.py``, ``tests/core/test_cli_parser.py``) and
``cli_parser.py`` itself (``tests/test_cli_parser.py``). ``run()``,
``_run_legacy()``, and ``_run_structured()`` — the actual dispatch functions —
had zero direct tests.
"""

from __future__ import annotations

import argparse
from unittest.mock import AsyncMock, MagicMock

import pytest

from hype_frog import main as main_module
from hype_frog.cli_parser import parse_cli
from hype_frog.core.env_config import EnvConfigError


def _legacy_args(**overrides: object) -> argparse.Namespace:
    ns = parse_cli([]).legacy
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


def _structured_args(command: str, **overrides: object) -> argparse.Namespace:
    trailing = {
        "auth": ["gsc"],
        "setup": ["semantic"],
        "test": ["quick"],
    }.get(command, [])
    ns = parse_cli([command, *trailing]).structured
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


# ---------------------------------------------------------------------------
# _run_legacy
# ---------------------------------------------------------------------------


def test_run_legacy_validate_exits_with_validation_return_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_validate = MagicMock(return_value=1)
    monkeypatch.setattr(main_module, "run_validation_cli", mock_validate)
    args = _legacy_args(validate=True, validate_url="https://example.com/", psi_probe_url="https://probe/")

    with pytest.raises(SystemExit) as exc:
        main_module._run_legacy(args)

    assert exc.value.code == 1
    mock_validate.assert_called_once_with(
        target_url="https://example.com/", psi_probe_url="https://probe/"
    )


def test_run_legacy_install_semantic_success_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "install_semantic_model", MagicMock(return_value=(True, "ok")))
    args = _legacy_args(install_semantic=True)

    with pytest.raises(SystemExit) as exc:
        main_module._run_legacy(args)

    assert exc.value.code == 0


def test_run_legacy_install_semantic_failure_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "install_semantic_model", MagicMock(return_value=(False, "bad")))
    args = _legacy_args(install_semantic=True)

    with pytest.raises(SystemExit) as exc:
        main_module._run_legacy(args)

    assert exc.value.code == 1


def test_run_legacy_install_playwright_success_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.install_playwright_chromium",
        MagicMock(return_value=(True, "installed")),
    )
    args = _legacy_args(install_playwright=True)

    with pytest.raises(SystemExit) as exc:
        main_module._run_legacy(args)

    assert exc.value.code == 0


def test_run_legacy_gsc_auth_never_raises_systemexit_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main_module, "ensure_gsc_oauth_token", MagicMock(return_value=(True, "token.json"))
    )
    args = _legacy_args(gsc_auth=True)

    main_module._run_legacy(args)  # must return normally, no SystemExit


def test_run_legacy_gsc_auth_never_raises_systemexit_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression-worthy asymmetry: the legacy ``--gsc-auth`` path prints an
    error but does not exit non-zero, unlike every other legacy branch."""
    monkeypatch.setattr(main_module, "ensure_gsc_oauth_token", MagicMock(return_value=(False, "")))
    args = _legacy_args(gsc_auth=True)

    main_module._run_legacy(args)  # must still return normally


def test_run_legacy_full_smoke_test_exits_with_gate_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "run_full_smoke_gate", AsyncMock(return_value=0))
    args = _legacy_args(full_smoke_test=True)

    with pytest.raises(SystemExit) as exc:
        main_module._run_legacy(args)

    assert exc.value.code == 0


def test_run_legacy_full_smoke_test_fast_forces_skip_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_gate = AsyncMock(return_value=0)
    monkeypatch.setattr(main_module, "run_full_smoke_gate", mock_gate)
    args = _legacy_args(full_smoke_test_fast=True)

    with pytest.raises(SystemExit):
        main_module._run_legacy(args)

    options = mock_gate.call_args.args[0]
    assert options.skip_preflight is True
    assert options.skip_pytest is True


def test_run_legacy_quick_test_exits_with_gate_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "run_quick_test_gate", AsyncMock(return_value=1))
    args = _legacy_args(quick_test=True)

    with pytest.raises(SystemExit) as exc:
        main_module._run_legacy(args)

    assert exc.value.code == 1


def test_run_legacy_regen_report_combined_with_quick_test_rejected() -> None:
    args = _legacy_args(regen_report=True, quick_test=True)

    with pytest.raises(SystemExit, match="cannot be combined"):
        main_module._run_legacy(args)


def test_run_legacy_regen_report_combined_with_validate_rejected() -> None:
    args = _legacy_args(regen_report=True, validate=True)

    with pytest.raises(SystemExit, match="cannot be combined"):
        main_module._run_legacy(args)


def test_run_legacy_regen_report_alone_falls_through_to_async_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_async_main = AsyncMock()
    monkeypatch.setattr(main_module, "_async_main", mock_async_main)
    args = _legacy_args(regen_report=True)

    main_module._run_legacy(args)

    mock_async_main.assert_called_once()


def test_run_legacy_default_falls_through_to_async_main(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_async_main = AsyncMock()
    monkeypatch.setattr(main_module, "_async_main", mock_async_main)
    args = _legacy_args()

    main_module._run_legacy(args)

    mock_async_main.assert_called_once()
    call_kwargs = mock_async_main.call_args.kwargs
    assert "cli_overrides" in call_kwargs


# ---------------------------------------------------------------------------
# _run_structured
# ---------------------------------------------------------------------------


def test_run_structured_validate_exits_with_validation_return_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "run_validation_cli", MagicMock(return_value=0))
    args = _structured_args("validate")

    with pytest.raises(SystemExit) as exc:
        main_module._run_structured(args)

    assert exc.value.code == 0


def test_run_structured_auth_gsc_success_returns_normally(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module, "ensure_gsc_oauth_token", MagicMock(return_value=(True, "token.json"))
    )
    args = _structured_args("auth")

    main_module._run_structured(args)  # no SystemExit


def test_run_structured_auth_gsc_failure_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unlike the legacy ``--gsc-auth`` flag, the structured ``auth gsc``
    subcommand DOES exit non-zero on failure."""
    monkeypatch.setattr(main_module, "ensure_gsc_oauth_token", MagicMock(return_value=(False, "")))
    args = _structured_args("auth")

    with pytest.raises(SystemExit) as exc:
        main_module._run_structured(args)

    assert exc.value.code == 1


def test_run_structured_auth_unknown_subcommand_exits() -> None:
    args = _structured_args("auth")
    args.auth_command = "bogus"

    with pytest.raises(SystemExit, match="Unknown auth command"):
        main_module._run_structured(args)


def test_run_structured_setup_semantic_success_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "install_semantic_model", MagicMock(return_value=(True, "ok")))
    args = _structured_args("setup", setup_command="semantic")

    with pytest.raises(SystemExit) as exc:
        main_module._run_structured(args)

    assert exc.value.code == 0


def test_run_structured_setup_playwright_success_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.install_playwright_chromium",
        MagicMock(return_value=(True, "installed")),
    )
    args = _structured_args("setup", setup_command="playwright")

    with pytest.raises(SystemExit) as exc:
        main_module._run_structured(args)

    assert exc.value.code == 0


def test_run_structured_setup_unknown_subcommand_exits() -> None:
    args = _structured_args("setup")
    args.setup_command = "bogus"

    with pytest.raises(SystemExit, match="Unknown setup command"):
        main_module._run_structured(args)


def test_run_structured_test_quick_exits_with_gate_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "run_quick_test_gate", AsyncMock(return_value=0))
    args = _structured_args("test", test_command="quick")

    with pytest.raises(SystemExit) as exc:
        main_module._run_structured(args)

    assert exc.value.code == 0


def test_run_structured_test_fast_flag_forces_skip_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_gate = AsyncMock(return_value=0)
    monkeypatch.setattr(main_module, "run_quick_test_gate", mock_gate)
    args = _structured_args("test", test_command="quick", fast=True)

    with pytest.raises(SystemExit):
        main_module._run_structured(args)

    options = mock_gate.call_args.args[0]
    assert options.skip_preflight is True
    assert options.skip_pytest is True


def test_run_structured_test_full_smoke_exits_with_gate_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "run_full_smoke_gate", AsyncMock(return_value=1))
    args = _structured_args("test", test_command="full-smoke")

    with pytest.raises(SystemExit) as exc:
        main_module._run_structured(args)

    assert exc.value.code == 1


def test_run_structured_test_unknown_subcommand_exits() -> None:
    args = _structured_args("test", test_command="quick")
    args.test_command = "bogus"

    with pytest.raises(SystemExit, match="Unknown test command"):
        main_module._run_structured(args)


def test_run_structured_crawl_rejects_verbose_and_quiet_together() -> None:
    args = _structured_args("crawl", verbose=True, quiet=True)

    with pytest.raises(SystemExit, match="Cannot combine --verbose and --quiet"):
        main_module._run_structured(args)


def test_run_structured_crawl_no_url_uses_startup_context(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_validate_env = MagicMock()
    monkeypatch.setattr(main_module, "validate_environment", mock_validate_env)
    monkeypatch.setattr(main_module, "_async_main", AsyncMock())
    args = _structured_args("crawl")  # no --url -> structured_crawl_run_config returns None

    main_module._run_structured(args)

    mock_validate_env.assert_called_once_with(context="startup")


def test_run_structured_crawl_accurate_mode_uses_accurate_crawl_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_validate_env = MagicMock()
    monkeypatch.setattr(main_module, "validate_environment", mock_validate_env)
    monkeypatch.setattr(main_module, "_async_main", AsyncMock())
    args = _structured_args("crawl", url="https://example.com/", mode="accurate")

    main_module._run_structured(args)

    mock_validate_env.assert_called_once_with(context="accurate_crawl")


def test_run_structured_crawl_fast_mode_uses_crawl_context(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_validate_env = MagicMock()
    monkeypatch.setattr(main_module, "validate_environment", mock_validate_env)
    monkeypatch.setattr(main_module, "_async_main", AsyncMock())
    args = _structured_args("crawl", url="https://example.com/", mode="fast")

    main_module._run_structured(args)

    mock_validate_env.assert_called_once_with(context="crawl")


def test_run_structured_unknown_command_exits() -> None:
    args = _structured_args("validate")
    args.command = "bogus"

    with pytest.raises(SystemExit, match="Unknown command"):
        main_module._run_structured(args)


# ---------------------------------------------------------------------------
# run() — top-level entry: env validation, playwright path config, PSI delay
# override, structured-vs-legacy dispatch
# ---------------------------------------------------------------------------


def test_run_exits_one_when_environment_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module,
        "require_valid_environment",
        MagicMock(side_effect=EnvConfigError("missing key")),
    )
    with pytest.raises(SystemExit) as exc:
        main_module.run([])

    assert exc.value.code == 1


def test_run_dispatches_to_run_structured_for_structured_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "require_valid_environment", MagicMock())
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", MagicMock(return_value=None)
    )
    mock_run_structured = MagicMock()
    monkeypatch.setattr(main_module, "_run_structured", mock_run_structured)

    main_module.run(["validate"])

    mock_run_structured.assert_called_once()


def test_run_dispatches_to_run_legacy_for_legacy_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "require_valid_environment", MagicMock())
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", MagicMock(return_value=None)
    )
    mock_run_legacy = MagicMock()
    monkeypatch.setattr(main_module, "_run_legacy", mock_run_legacy)

    main_module.run(["--validate"])

    mock_run_legacy.assert_called_once()


def test_run_applies_psi_delay_override_for_structured_crawl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "require_valid_environment", MagicMock())
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", MagicMock(return_value=None)
    )
    monkeypatch.setattr(main_module, "_run_structured", MagicMock())
    mock_override = MagicMock()
    monkeypatch.setattr(main_module, "apply_runtime_override", mock_override)

    main_module.run(["crawl", "--psi-delay", "3.5"])

    mock_override.assert_called_once_with("PSI_BASE_DELAY_SECONDS", 3.5)


def test_run_skips_psi_delay_override_when_negative(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "require_valid_environment", MagicMock())
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", MagicMock(return_value=None)
    )
    monkeypatch.setattr(main_module, "_run_structured", MagicMock())
    mock_override = MagicMock()
    monkeypatch.setattr(main_module, "apply_runtime_override", mock_override)

    main_module.run(["crawl", "--psi-delay", "-1"])

    mock_override.assert_not_called()


def test_run_applies_psi_delay_override_for_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "require_valid_environment", MagicMock())
    monkeypatch.setattr(
        "hype_frog.crawler.fetcher.configure_playwright_browsers_path", MagicMock(return_value=None)
    )
    monkeypatch.setattr(main_module, "_run_legacy", MagicMock())
    mock_override = MagicMock()
    monkeypatch.setattr(main_module, "apply_runtime_override", mock_override)

    main_module.run(["--psi-delay", "2.0", "--validate"])

    mock_override.assert_called_once_with("PSI_BASE_DELAY_SECONDS", 2.0)
