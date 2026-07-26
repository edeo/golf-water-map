"""
For each course in the DB, fetch today's (or a given date's) ETo and
write an estimated water-use row to daily_water_use.

Water use (gallons) = ETo_inches * Kc * irrigated_acres * 27,154
  (27,154 gallons = 1 acre-inch of water)

Usage:
    python scripts/compute_water_use.py                # today
    python scripts/compute_water_use.py 2026-07-20      # specific date
"""
import sqlite3
import sys
from datetime import date as date_cls
from pathlib import Path

from fetch_eto import fetch_eto

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "golf_water.db"
GALLONS_PER_ACRE_INCH = 27154.0


def compute_for_date(target_date: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    courses = conn.execute("SELECT * FROM courses").fetchall()

    rows_written = 0
    for c in courses:
        if not c["et_network"]:
            print(f"  skip {c['name']}: no et_network set")
            continue
        if c["et_network"] == "AZMET" and not c["et_station_id"]:
            print(f"  skip {c['name']}: AZMET course with no et_station_id set")
            continue

        target = (c["latitude"], c["longitude"]) if c["et_network"] == "CIMIS" else c["et_station_id"]
        try:
            weather = fetch_eto(c["et_network"], target, target_date)
        except Exception as e:
            print(f"  ERROR fetching ETo for {c['name']}: {e}")
            continue

        eto = weather.get("eto_inches")
        if eto is None:
            print(f"  no ETo value returned for {c['name']} on {target_date}")
            continue

        gallons = eto * c["kc"] * c["irrigated_acres"] * GALLONS_PER_ACRE_INCH
        acre_feet = (eto * c["kc"] * c["irrigated_acres"]) / 12.0

        conn.execute(
            """INSERT OR REPLACE INTO daily_water_use
               (course_id, date, eto_inches, gallons, acre_feet)
               VALUES (?, ?, ?, ?, ?)""",
            (c["course_id"], target_date, eto, gallons, acre_feet),
        )
        rows_written += 1
        print(f"  {c['name']}: ETo={eto:.2f}in -> {gallons:,.0f} gal")

    conn.commit()
    conn.close()
    print(f"Done. {rows_written}/{len(courses)} courses updated for {target_date}.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else date_cls.today().isoformat()
    print(f"Computing water use estimates for {target}...")
    compute_for_date(target)
