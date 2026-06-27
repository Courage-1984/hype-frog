# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for hype-frog standalone Windows executable.

Build with:
    uv run python build_exe.py
  or directly:
    uv run pyinstaller --clean hype_frog.spec

Output: dist/hype-frog.exe  (~200-400 MB depending on optional extras installed)
"""
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# ---------------------------------------------------------------------------
# Collect packages that use dynamic/plugin imports.
# collect_all() returns (datas, binaries, hiddenimports) for each package.
# ---------------------------------------------------------------------------
spacy_datas,    spacy_binaries,    spacy_hiddenimports    = collect_all("spacy")
aiohttp_datas,  aiohttp_binaries,  aiohttp_hiddenimports  = collect_all("aiohttp")
pw_datas,       pw_binaries,       pw_hiddenimports       = collect_all("playwright")
rl_datas,       rl_binaries,       rl_hiddenimports       = collect_all("reportlab")

# pdf_exporter imports reportlab lazily inside a try/except; collect_all ensures
# the frozen exe bundles fonts and platypus modules even when static analysis misses them.
spacy_hiddenimports = [
    name for name in spacy_hiddenimports if not name.startswith("spacy.tests")
]

# spaCy NER model — bundled so --install-semantic is not needed in the exe
try:
    en_core_datas, en_core_binaries, en_core_hiddenimports = collect_all("en_core_web_sm")
except Exception:
    # en_core_web_sm not installed in the build env; semantic AEO will be unavailable
    en_core_datas, en_core_binaries, en_core_hiddenimports = [], [], []

a = Analysis(
    ["src/hype_frog/main.py"],
    pathex=["src"],
    binaries=(
        spacy_binaries
        + en_core_binaries
        + pw_binaries
        + rl_binaries
        + aiohttp_binaries
    ),
    datas=(
        spacy_datas
        + en_core_datas
        + pw_datas
        + rl_datas
        + aiohttp_datas
    ),
    hiddenimports=(
        spacy_hiddenimports
        + en_core_hiddenimports
        + pw_hiddenimports
        + rl_hiddenimports
        + aiohttp_hiddenimports
        + [
            # google auth / Search Console
            "google.auth.transport.requests",
            "google.auth.transport.urllib3",
            "google.oauth2.credentials",
            "google_auth_oauthlib.flow",
            "googleapiclient.discovery",
            "googleapiclient.http",
            # scipy — sparse graph / matrix operations
            "scipy.sparse.csgraph._validation",
            "scipy._lib.messagestream",
            "scipy.special.cython_special",
            # pandas internal C extensions (tslibs only; hashtable helpers renamed in pandas 2.x)
            "pandas._libs.tslibs.timezones",
            "pandas._libs.tslibs.np_datetime",
            # pydantic v2 compat layer
            "pydantic.v1",
            # lxml / beautifulsoup4
            "lxml.etree",
            "lxml._elementpath",
            "bs4.builder._lxml",
            # misc
            "simhash",
            "networkx",
            "dateutil",
            "dateutil.tz",
            # reportlab PDF export (lazy-imported in pdf_exporter)
            "reportlab.lib.colors",
            "reportlab.lib.pagesizes",
            "reportlab.lib.styles",
            "reportlab.lib.units",
            "reportlab.platypus",
            "reportlab.pdfbase._fontdata",
            "reportlab.graphics.charts.barcharts",
            "reportlab.graphics.charts.piecharts",
            # yaml config loading
            "yaml",
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # UI toolkits not needed
        "tkinter",
        "_tkinter",
        # plotting not needed
        "matplotlib",
        "PIL",
        # interactive / notebook tools not needed
        "IPython",
        "jupyter",
        "notebook",
        "ipykernel",
        # docs tooling not needed
        "sphinx",
        # dev/test tooling not needed
        "_pytest",
        "pytest",
        "mypy",
        "ruff",
        "spacy.tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="hype-frog",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # set False if UPX is not installed
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # CLI tool — keep console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
