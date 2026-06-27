"""
Hype Frog × Catppuccin Mocha theme palette.

Maps official Catppuccin Mocha base colours to hype-frog semantic roles
(brand, RAG, heatmaps, Excel fills) and provides HTML/CSS helpers.

Canonical documentation: docs/excel_reporting_standards.md
  (sections "Catppuccin Mocha theme" and "Catppuccin Mocha HTML theme").

Reference: https://github.com/catppuccin/catppuccin#mocha
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Google Fonts CDN — JetBrains Mono (reliable, no Nerd Font glyphs needed for reports).
JETBRAINS_MONO_CDN: Final[str] = (
    "https://fonts.googleapis.com/css2?"
    "family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap"
)

# Optional Nerd Font CDN (self-hosted TTF via jsDelivr) for terminals/IDEs — not used in HTML
# because Google Fonts does not ship Nerd Font patches.
JETBRAINS_MONO_NERD_CDN: Final[str] = (
    "https://cdn.jsdelivr.net/gh/ryanoasis/nerd-fonts@v3.2.1/"
    "patched-fonts/JetBrainsMono/Ligatures/Regular/"
    "JetBrainsMonoNerdFont-Regular.ttf"
)

THEME_NAME: Final[str] = "mocha"


@dataclass(frozen=True, slots=True)
class CatppuccinMocha:
    """Official Catppuccin Mocha palette (hex with # prefix)."""

    # Accents
    rosewater: str = "#f5e0dc"
    flamingo: str = "#f2cdcd"
    pink: str = "#f5c2e7"
    mauve: str = "#cba6f7"
    red: str = "#f38ba8"
    maroon: str = "#eba0ac"
    peach: str = "#fab387"
    yellow: str = "#f9e2af"
    green: str = "#a6e3a1"
    teal: str = "#94e2d5"
    sky: str = "#89dceb"
    sapphire: str = "#74c7ec"
    blue: str = "#89b4fa"
    lavender: str = "#b4befe"

    # Neutrals
    text: str = "#cdd6f4"
    subtext1: str = "#bac2de"
    subtext0: str = "#a6adc8"
    overlay2: str = "#9399b2"
    overlay1: str = "#7f849c"
    overlay0: str = "#6c7086"
    surface2: str = "#585b70"
    surface1: str = "#45475a"
    surface0: str = "#313244"
    base: str = "#1e1e2e"
    mantle: str = "#181825"
    crust: str = "#11111b"


@dataclass(frozen=True, slots=True)
class HypeFrogMochaSemantic:
    """Hype Frog role mapping on top of Catppuccin Mocha."""

    # Brand identity — frog pond on mocha base
    brand: str = "#1e1e2e"          # base — headers, nav bars
    brand_on: str = "#cdd6f4"       # text on brand surfaces
    accent: str = "#94e2d5"         # teal — frog-pond accent / CTAs
    frog_green: str = "#a6e3a1"    # signature hype-frog green

    # Surfaces (HTML dark report)
    page_bg: str = "#11111b"        # crust
    panel_bg: str = "#181825"       # mantle
    card_bg: str = "#1e1e2e"        # base
    border: str = "#313244"         # surface0
    text: str = "#cdd6f4"
    text_muted: str = "#a6adc8"

    # RAG / severity (HTML)
    good: str = "#a6e3a1"
    good_bg: str = "#1a2e1f"
    good_border: str = "#4a7c59"
    warning: str = "#f9e2af"
    warning_bg: str = "#2e2818"
    warning_border: str = "#8a7340"
    critical: str = "#f38ba8"
    critical_bg: str = "#2e1a22"
    critical_border: str = "#8a4058"
    observation: str = "#89b4fa"
    observation_bg: str = "#1a2233"
    neutral_bg: str = "#181825"

    # Excel-friendly light fills (openpyxl — no # prefix in exports below)
    excel_brand: str = "1E1E2E"
    excel_brand_on: str = "CDD6F4"
    excel_blue: str = "74C7EC"
    excel_frog_green: str = "A6E3A1"
    rag_red: str = "F5DCE3"
    rag_red_font: str = "8B2942"
    rag_amber: str = "FEF3D4"
    rag_amber_font: str = "7A5C00"
    rag_green: str = "DFF5DD"
    rag_green_font: str = "2D6A3A"
    rag_red_soft: str = "F8E0E8"
    rag_amber_soft: str = "FFF0CC"
    rag_neutral: str = "45475A"
    zebra_band: str = "313244"
    heatmap_low: str = "F38BA8"
    heatmap_mid: str = "F9E2AF"
    heatmap_high: str = "A6E3A1"
    data_bar_blue: str = "74C7EC"


MOCHA: Final[CatppuccinMocha] = CatppuccinMocha()
SEMANTIC: Final[HypeFrogMochaSemantic] = HypeFrogMochaSemantic()


def resolve_brand_colour(override: str | None) -> str:
    """Return explicit override or mocha default brand colour."""
    cleaned = (override or "").strip()
    if cleaned and cleaned.lstrip("#").upper() != "1E293B":
        return cleaned if cleaned.startswith("#") else f"#{cleaned}"
    return SEMANTIC.brand


def resolve_accent_colour(override: str | None) -> str:
    """Return explicit override or mocha default accent colour."""
    cleaned = (override or "").strip()
    if cleaned and cleaned.lstrip("#").upper() != "2563EB":
        return cleaned if cleaned.startswith("#") else f"#{cleaned}"
    return SEMANTIC.accent


def html_font_links() -> str:
    """Return <link> tags for JetBrains Mono via Google Fonts CDN."""
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        f'<link href="{JETBRAINS_MONO_CDN}" rel="stylesheet">'
    )


def html_theme_css(brand_colour: str, accent_colour: str) -> str:
    """Return the mocha-specific CSS block for HTML executive reports."""
    s = SEMANTIC
    m = MOCHA
    font_stack = (
        "'JetBrains Mono', 'SF Mono', 'Cascadia Code', Consolas, monospace"
    )
    sans_stack = (
        "'JetBrains Mono', -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    )
    return f"""
  body {{
    font-family: {sans_stack};
    line-height: 1.55;
    color: {s.text};
    background: {s.page_bg};
  }}
  h1 {{ font-size: 1.5em; color: {s.frog_green}; margin-bottom: 4px; }}
  h2 {{
    font-size: 1.15em;
    margin: 28px 0 10px;
    padding: 6px 10px;
    background: {brand_colour};
    color: {s.brand_on};
    border-radius: 3px;
    border: 1px solid {s.border};
  }}
  h3 {{ font-size: 0.95em; color: {accent_colour}; margin: 16px 0 6px; }}

  .header {{ border-bottom: 3px solid {accent_colour}; padding-bottom: 12px; margin-bottom: 16px; }}
  .header .subtitle {{ color: {s.text_muted}; font-size: 0.85em; }}
  .prepared-by {{ color: {m.overlay1}; font-size: 0.8em; margin-top: 4px; }}

  .kpi-card {{
    background: {s.card_bg};
    border: 1px solid {s.border};
  }}
  .kpi-card.good {{ background: {s.good_bg}; border-color: {s.good_border}; }}
  .kpi-card.warning {{ background: {s.warning_bg}; border-color: {s.warning_border}; }}
  .kpi-card.critical {{ background: {s.critical_bg}; border-color: {s.critical_border}; }}
  .kpi-card.neutral {{ background: {s.neutral_bg}; border-color: {s.border}; }}
  .kpi-value {{ color: {s.frog_green}; }}
  .kpi-label {{ color: {s.text_muted}; }}

  .sev-seg.critical {{ background: {s.critical}; color: {m.crust}; }}
  .sev-seg.warning {{ background: {s.warning}; color: {m.crust}; }}
  .sev-seg.observation {{ background: {s.observation}; color: {m.crust}; }}
  .sev-legend {{ color: {s.text_muted}; }}
  .dot.critical {{ background: {s.critical}; }}
  .dot.warning {{ background: {s.warning}; }}
  .dot.observation {{ background: {s.observation}; }}

  .data-table th, .data-table td {{ border-color: {s.border}; }}
  .data-table th {{ background: {brand_colour}; color: {s.brand_on}; }}
  .data-table tr.good td {{ background: {s.good_bg}; }}
  .data-table tr.warning td {{ background: {s.warning_bg}; }}
  .data-table tr.critical td {{ background: {s.critical_bg}; }}
  .data-table tr.neutral td {{ background: {s.neutral_bg}; }}
  .data-table tr.total-row td {{ background: {m.surface0}; color: {s.text}; font-weight: 700; }}
  .data-table td.good {{ background: {s.good_bg}; color: {s.good}; }}
  .data-table td.warning {{ background: {s.warning_bg}; color: {s.warning}; }}
  .data-table td.critical {{ background: {s.critical_bg}; color: {s.critical}; }}
  .data-table .url-cell {{ font-family: {font_stack}; }}

  .badge.critical {{ background: {s.critical_bg}; color: {s.critical}; border: 1px solid {s.critical_border}; }}
  .badge.warning {{ background: {s.warning_bg}; color: {s.warning}; border: 1px solid {s.warning_border}; }}
  .badge.observation {{ background: {s.observation_bg}; color: {s.observation}; border: 1px solid {s.border}; }}

  .narrative {{
    background: {s.panel_bg};
    border-left: 4px solid {accent_colour};
    color: {s.text};
  }}
  .muted {{ color: {s.text_muted}; }}

  footer {{ border-top-color: {s.border}; color: {m.overlay1}; }}
"""


def excel_palette_overrides() -> dict[str, str]:
    """Return openpyxl hex overrides (no #) for HF_EXCEL_THEME=mocha."""
    e = SEMANTIC
    return {
        "STD_NAVY": e.excel_brand,
        "STD_WHITE": e.excel_brand_on,
        "STD_BLUE": e.excel_blue,
        "STD_FROG_GREEN": e.excel_frog_green,
        "RAG_RED": e.rag_red,
        "RAG_RED_FONT": e.rag_red_font,
        "RAG_AMBER": e.rag_amber,
        "RAG_AMBER_FONT": e.rag_amber_font,
        "RAG_GREEN": e.rag_green,
        "RAG_GREEN_FONT": e.rag_green_font,
        "RAG_RED_SOFT": e.rag_red_soft,
        "RAG_AMBER_SOFT": e.rag_amber_soft,
        "RAG_NEUTRAL": e.rag_neutral,
        "ZEBRA_BAND": e.zebra_band,
        "HEATMAP_LOW": e.heatmap_low,
        "HEATMAP_MID": e.heatmap_mid,
        "HEATMAP_HIGH": e.heatmap_high,
        "DATA_BAR_BLUE": e.data_bar_blue,
    }


__all__ = [
    "JETBRAINS_MONO_CDN",
    "JETBRAINS_MONO_NERD_CDN",
    "THEME_NAME",
    "CatppuccinMocha",
    "HypeFrogMochaSemantic",
    "MOCHA",
    "SEMANTIC",
    "resolve_brand_colour",
    "resolve_accent_colour",
    "html_font_links",
    "html_theme_css",
    "excel_palette_overrides",
]
