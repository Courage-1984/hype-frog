"""Public crawler engine re-export surface."""

from __future__ import annotations

import hype_frog.crawler.engine as engine
from hype_frog.crawler.client import create_session
from hype_frog.crawler.fetcher import fetch_and_parse
from hype_frog.crawler.gsc_engine import fetch_gsc_page_metrics
from hype_frog.crawler.link_checks import check_url_status_light, check_url_status_light_limited
from hype_frog.crawler.psi_engine import fetch_psi_metrics_batch
from hype_frog.crawler.sitemap import parse_sitemap


def test_engine_all_exports_are_importable() -> None:
    for name in engine.__all__:
        assert hasattr(engine, name)


def test_engine_reexports_match_canonical_implementations() -> None:
    assert engine.create_session is create_session
    assert engine.fetch_and_parse is fetch_and_parse
    assert engine.parse_sitemap is parse_sitemap
    assert engine.check_url_status_light is check_url_status_light
    assert engine.check_url_status_light_limited is check_url_status_light_limited
    assert engine.fetch_gsc_page_metrics is fetch_gsc_page_metrics
    assert engine.fetch_psi_metrics_batch is fetch_psi_metrics_batch
