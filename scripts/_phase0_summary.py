import json
from pathlib import Path

p = Path("scripts/_phase0_inspect_output.json")
d = json.loads(p.read_text(encoding="utf-8-sig"))
print("FILE:", d["path"])
print("TOTALS:", d["totals"])
print("NAMED_RANGES:", len(d["named_ranges"]))
for s in d["sheets"]:
    match = "OK" if s["detected_header_row"] == s["code_expected_header_row"] else "MISMATCH"
    line = (
        f"{s['state']:7} | {s['name'][:38]:38} | "
        f"hdr r{s['detected_header_row']} (code r{s['code_expected_header_row']}) {match} | "
        f"{s['used_range']} | merges={s['merged_count']} links={s['hyperlink_count']} "
        f"charts={s['chart_count']} formulas={s['formula_count']} freeze={s['freeze_panes']}"
    )
    print(line)
    print("  HEADERS:", ", ".join(s["headers"][:12]))
    if s["detected_header_row"] != s["code_expected_header_row"]:
        print("  ** header row mismatch **")
