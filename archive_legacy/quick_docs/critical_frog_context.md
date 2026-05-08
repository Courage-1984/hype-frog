Please gather the most critical source files from the `hype-frog` codebase to be audited by a Principal Staff Engineer. I need to verify our strict architectural invariants: Playwright async safety, aiohttp bounded concurrency, append-only pipeline data mutability, and openpyxl string sanitization.

Please locate the primary files that handle the following responsibilities and output their FULL source code wrapped in XML `<file name="path/to/file.py">` tags:

1.  **Crawler Engine:** The main fetcher implementation showing how `aiohttp` and `playwright.async_api` are orchestrated, including retry logic and concurrency limits (e.g., `src/hype_frog/crawler/fetcher.py` or `engine.py`).
2.  **Pipeline Orchestration:** The code responsible for taking extracted data, applying rules, and assembling the final row dictionaries for the reporter (e.g., `src/hype_frog/pipeline/row_assembly.py` or `main_pipeline.py`).
3.  **Excel Reporter:** The main openpyxl logic handling string sanitization, workbook creation, and writing the `main_data` dictionaries to the spreadsheet (e.g., `src/hype_frog/reporter/excel_writer.py` or `workbook_builder.py`).
4.  **Core Logging:** The shared logging configuration to verify no `print()` statements are being used in hot paths (e.g., `src/hype_frog/core/logger.py`).

Output ONLY the raw XML blocks for these files so I can copy and paste them for an external audit.


