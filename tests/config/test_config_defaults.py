"""config_defaults.py — threshold sanity, USER_CONFIG_KEYS consistency, CMS params."""

from __future__ import annotations

import pytest

from hype_frog import config_defaults


@pytest.fixture(autouse=True)
def _clear_runtime_overrides() -> None:
    config_defaults._RUNTIME_OVERRIDES.clear()
    yield
    config_defaults._RUNTIME_OVERRIDES.clear()


class TestThresholdMonotonicity:
    """Warning/critical (or recent/ageing/stale) bands must be ordered as documented."""

    def test_cwv_lcp_warning_below_critical(self) -> None:
        assert config_defaults.CWV_LCP_WARNING_THRESHOLD < config_defaults.CWV_LCP_CRITICAL_THRESHOLD

    def test_lab_tbt_warning_below_critical(self) -> None:
        assert config_defaults.LAB_TBT_WARNING_MS < config_defaults.LAB_TBT_CRITICAL_MS

    def test_content_age_bands_increase(self) -> None:
        assert (
            config_defaults.CONTENT_AGE_RECENT_DAYS
            < config_defaults.CONTENT_AGE_AGEING_DAYS
            < config_defaults.CONTENT_AGE_STALE_DAYS
        )

    def test_retry_delay_below_max(self) -> None:
        assert config_defaults.RETRY_BASE_DELAY_SECONDS < config_defaults.RETRY_MAX_DELAY_SECONDS


class TestUserConfigKeysConsistency:
    """Every USER_CONFIG_KEYS entry must be a real module-level constant, and vice versa
    for every constant that has a corresponding get_*() accessor."""

    def test_every_user_config_key_is_a_real_constant(self) -> None:
        for key in config_defaults.USER_CONFIG_KEYS:
            assert hasattr(config_defaults, key), f"{key} in USER_CONFIG_KEYS has no matching constant"

    def test_every_getter_backed_key_is_in_user_config_keys(self) -> None:
        getter_names = [
            name
            for name in vars(config_defaults)
            if name.startswith("get_") and callable(getattr(config_defaults, name))
        ]
        assert getter_names, "expected at least one get_* accessor in config_defaults"
        for getter_name in getter_names:
            key = getter_name.removeprefix("get_").upper()
            assert key in config_defaults.USER_CONFIG_KEYS, (
                f"{getter_name} has no matching USER_CONFIG_KEYS entry ({key})"
            )


class TestRuntimeOverrideRoundTrip:
    def test_override_applies_to_int_getter(self) -> None:
        config_defaults.apply_runtime_override("QUICK_WINS_MAX_RESULTS", 5)
        assert config_defaults.get_quick_wins_max_results() == 5

    def test_override_applies_to_float_getter(self) -> None:
        config_defaults.apply_runtime_override("CWV_LCP_CRITICAL_THRESHOLD", 9.9)
        assert config_defaults.get_cwv_lcp_critical_threshold() == 9.9

    def test_no_override_falls_back_to_module_constant(self) -> None:
        assert (
            config_defaults.get_large_image_size_kb()
            == config_defaults.LARGE_IMAGE_SIZE_KB
        )


class TestExcludedCmsActionQueryParams:
    def test_is_frozenset(self) -> None:
        assert isinstance(config_defaults.EXCLUDED_CMS_ACTION_QUERY_PARAMS, frozenset)

    def test_contains_baseline_woocommerce_entries(self) -> None:
        baseline = {"add-to-cart", "removed_item", "wc-ajax"}
        assert baseline <= config_defaults.EXCLUDED_CMS_ACTION_QUERY_PARAMS
