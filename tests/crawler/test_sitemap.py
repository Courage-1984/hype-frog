"""Sitemap XML parsing (urlset, index recursion, error handling) with mocked HTTP."""

from __future__ import annotations

from hype_frog.crawler.sitemap import parse_sitemap

_URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://x.test/a</loc>
    <lastmod>2026-01-01</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://x.test/b</loc>
  </url>
</urlset>
"""

_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://x.test/child.xml</loc></sitemap>
</sitemapindex>
"""

_URLSET_WITH_IMAGES = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <url>
    <loc>https://x.test/with-images</loc>
    <image:image>
      <image:loc>https://x.test/img1.jpg</image:loc>
    </image:image>
    <image:image>
      <image:loc>https://x.test/img2.jpg</image:loc>
    </image:image>
  </url>
  <url>
    <loc>https://x.test/no-images</loc>
  </url>
</urlset>
"""


class _FakeResponse:
    def __init__(self, status: int, text: str) -> None:
        self.status = status
        self._text = text

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    async def text(self) -> str:
        return self._text


class _FakeSession:
    def __init__(self, mapping: dict[str, tuple[int, str]]) -> None:
        self._mapping = mapping

    def get(self, url: str, **_kwargs: object) -> _FakeResponse:
        status, text = self._mapping.get(url, (404, ""))
        return _FakeResponse(status, text)


async def test_parse_urlset_returns_urls_and_metadata() -> None:
    session = _FakeSession({"https://x.test/sitemap.xml": (200, _URLSET)})
    urls, meta, files_meta = await parse_sitemap("https://x.test/sitemap.xml", session)

    assert urls == ["https://x.test/a", "https://x.test/b"]
    assert meta["https://x.test/a"]["changefreq"] == "daily"
    assert meta["https://x.test/a"]["priority"] == "0.8"
    assert meta["https://x.test/a"]["lastmod"] == "2026-01-01"
    assert meta["https://x.test/b"]["lastmod"] is None
    assert files_meta["https://x.test/sitemap.xml"]["kind"] == "urlset"
    assert files_meta["https://x.test/sitemap.xml"]["url_count"] == 2


async def test_parse_sitemap_index_recurses_into_children() -> None:
    session = _FakeSession(
        {
            "https://x.test/index.xml": (200, _INDEX),
            "https://x.test/child.xml": (200, _URLSET),
        }
    )
    urls, meta, files_meta = await parse_sitemap("https://x.test/index.xml", session)

    assert set(urls) == {"https://x.test/a", "https://x.test/b"}
    assert files_meta["https://x.test/index.xml"]["is_index"] is True
    assert files_meta["https://x.test/child.xml"]["is_index"] is False


async def test_parse_sitemap_handles_http_error_gracefully() -> None:
    session = _FakeSession({"https://x.test/missing.xml": (500, "")})
    urls, meta, files_meta = await parse_sitemap("https://x.test/missing.xml", session)

    assert urls == []
    assert meta == {}
    assert files_meta == {}


async def test_parse_urlset_extracts_image_image_locs() -> None:
    session = _FakeSession({"https://x.test/images.xml": (200, _URLSET_WITH_IMAGES)})
    _urls, meta, _files_meta = await parse_sitemap("https://x.test/images.xml", session)

    assert meta["https://x.test/with-images"]["image_count"] == 2
    assert meta["https://x.test/with-images"]["first_image_url"] == "https://x.test/img1.jpg"
    assert meta["https://x.test/no-images"]["image_count"] == 0
    assert meta["https://x.test/no-images"]["first_image_url"] is None


async def test_parse_sitemap_dedupes_repeated_locs() -> None:
    dup = _URLSET.replace("https://x.test/b", "https://x.test/a")
    session = _FakeSession({"https://x.test/dup.xml": (200, dup)})
    urls, _meta, _files = await parse_sitemap("https://x.test/dup.xml", session)

    assert urls == ["https://x.test/a"]
