from __future__ import annotations

LIGHT_HEADER_COLOR = "E5E7EB"
TABLE_HEADER_COLOR = "ADD8E6"
VALUE_BLOCK_COLOR = "DCE3EA"
PANEL_BG_COLOR = "F5F7FA"
GOOD_COLOR = "C6EFCE"
WARN_COLOR = "FFEB9C"
ALERT_COLOR = "FFC7CE"
SOFT_ALERT_COLOR = "FFC1C1"
SOFT_WARN_COLOR = "FFCC99"

DASHBOARD_COLUMN_WIDTHS: dict[str, int] = {
    "A": 35,
    "B": 15,
    "C": 5,
    "D": 30,
    "E": 15,
    "F": 5,
    "G": 25,
    "H": 25,
    "I": 30,
    "J": 30,
    "K": 30,
}

STATUS_ROW_STYLE: list[tuple[str, str]] = [
    ("200 OK", GOOD_COLOR),
    ("3xx Redirects", SOFT_WARN_COLOR),
    ("4xx Errors", SOFT_ALERT_COLOR),
    ("5xx Errors", SOFT_ALERT_COLOR),
    ("Other", SOFT_WARN_COLOR),
]

SEVERITY_ROW_STYLE: list[tuple[str, str]] = [
    ("Critical", SOFT_ALERT_COLOR),
    ("Warning", SOFT_WARN_COLOR),
    ("Medium", SOFT_WARN_COLOR),
    ("Low", GOOD_COLOR),
]

QUICK_LINKS: list[tuple[str, str]] = [
    ("Fix Plan", "#FixPlan!A1"),
    ("Main URL Data", "#Main!A1"),
    ("Technical Diagnostics", "#'Technical Diagnostics'!A1"),
    ("Indexability", "#'Technical Diagnostics'!A1"),
    ("AEO Opportunities", "#'Content & AI Readiness'!A1"),
    ("AIOSEO Action Queue", "#AIOSEO!A1"),
]

DASHBOARD_TOOLTIPS: dict[str, str] = {
    "C5": "Total URLs crawled in this run. Calculated as the number of audited URL rows.",
    "C6": "Overall Health Score. Calculated as average SEO Health Score across Technical URLs; fallback to SEO Pass Rate if score data is unavailable.",
    "C7": "SEO Pass Rate %. Calculated as Pass URLs divided by Total URLs.",
    "C8": "Pass URL count. URL is pass when it has no Critical and no Warning issues.",
    "C9": "Critical URL count from Technical severity badge.",
    "C10": "Warning URL count from Technical severity badge.",
    "C11": "HTTP Error Rate %. Calculated as (4xx URLs + 5xx URLs) / Total URLs.",
    "C12": "Crawl Success Rate %. Calculated as 2xx URLs / Total URLs.",
    "C13": "Critical URL Rate %. Calculated as Critical URLs / Total URLs.",
    "C14": "Warning URL Rate %. Calculated as Warning URLs / Total URLs.",
    "C15": "Projected Health Score if all current To Do items are completed in this cycle.",
    "C16": "Projected Pass Rate if all current To Do items are completed in this cycle.",
    "C17": "Content Hub Readiness %. COUNTIF ``Complete`` in Action Required (col C) over URL rows (col F) minus header.",
    "O5": "Most widespread issue from FixPlan by affected URL count (primary blocker).",
    "O6": "Number of URLs impacted by the top blocking issue.",
    "O7": "Total URLs returning client/server errors (4xx + 5xx).",
    "O8": "Average Time to First Byte across Technical URLs (ms).",
    "H15": "Affected URL count for the highest-priority issue (linked to FixPlan).",
    "H16": "Affected URL count for the next issue in the priority list.",
    "H17": "Affected URL count for the next issue in the priority list.",
    "H18": "Affected URL count for the next issue in the priority list.",
    "H19": "Affected URL count for the next issue in the priority list.",
    "G23": "Owner responsible for remediation. Click to open FixPlan.",
    "H23": "Number of issue rows assigned to this owner.",
    "I23": "Total affected URLs across this owner's assigned issues.",
    "J23": "Count of critical issue types assigned to this owner.",
    "K23": "Count of warning issue types assigned to this owner.",
}

