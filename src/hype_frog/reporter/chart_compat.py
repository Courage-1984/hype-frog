"""openpyxl chart compatibility helpers for Microsoft Excel."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from openpyxl.chart import BarChart, DoughnutChart

_APP_XML_PATH = "docProps/app.xml"
_OPENPYXL_APP_RE = re.compile(
    r"<Application>Microsoft Excel Compatible / Openpyxl [^<]+</Application>"
)


def configure_openpyxl_chart_for_excel(chart: BarChart | DoughnutChart) -> None:
    """Apply settings so Excel renders openpyxl charts (not empty rounded boxes).

    Hidden source columns/rows are excluded when ``plotVisOnly`` is true (openpyxl
    default). openpyxl 3.1.4+ also stamps app.xml in a way that breaks chart layout
    unless patched at save time (see ``patch_xlsx_app_xml_for_excel_compatibility``).
    """
    chart.visible_cells_only = False
    chart.style = 2
    chart.roundedCorners = False
    if chart.title is not None:
        chart.title.overlay = False
    if chart.legend is not None:
        chart.legend.overlay = False
    if isinstance(chart, BarChart):
        chart.x_axis.delete = False
        chart.y_axis.delete = False


def patch_xlsx_app_xml_for_excel_compatibility(path: str | Path) -> None:
    """Rewrite docProps/app.xml so Excel uses native chart layout (openpyxl #3.1.4+)."""
    target = Path(path)
    if not target.is_file():
        return
    buffer = io.BytesIO()
    with zipfile.ZipFile(target, "r") as zin, zipfile.ZipFile(
        buffer, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == _APP_XML_PATH:
                text = _OPENPYXL_APP_RE.sub(
                    "<Application>Microsoft Excel</Application>",
                    data.decode("utf-8"),
                )
                data = text.encode("utf-8")
            zout.writestr(info, data)
    target.write_bytes(buffer.getvalue())


__all__ = [
    "configure_openpyxl_chart_for_excel",
    "patch_xlsx_app_xml_for_excel_compatibility",
]
