"""Workbook sheet helpers (subpackages; avoid eager imports that cycle with excel_engine)."""


def __getattr__(name: str):
    if name == "apply_workbook_toc_and_links":
        from hype_frog.reporter.sheets.toc import apply_workbook_toc_and_links

        return apply_workbook_toc_and_links
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["apply_workbook_toc_and_links"]
