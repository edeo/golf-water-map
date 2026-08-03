"""
For each course in the DB, fetch yesterday's (or a given date's) ETo and
write an estimated water-use row to daily_water_use.

Net irrigation demand (inches) = max(0, ETo_inches * Kc - precip_inches)
Water use (gallons) = net irrigation demand * irrigated_acres * 27,154
  (27,154 gallons = 1 acre-inch of water)

precip_inches only comes from AZMET (AZ courses) -- CIMIS's coordinate-based
lookup doesn't include precipitation, so CA courses always get precip=0,
i.e. pure demand with no rainfall offset.

Defaults to yesterday rather than today: both CIMIS and AZMET finalize
a day's readings after that day ends, so querying the current date
always comes back empty.

Usage:
    python scripts/compute_water_use.py                # yesterday
    python scripts/compute_water_use.py 2026-07-20      # specific date
"""
import sqlite3
import sys
from datetime import date as date_cls, timedelta
from pathlib import Path

from fetch_eto import fetch_eto

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "golf_water.db"
GALLONS_PER_ACRE_INCH = 27154.0


def migrate(conn):
    """Idempotent schema updates for databases created before precip tracking."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(daily_water_use)")}
    if "precip_inches" not in columns:
        conn.execute("ALTER TABLE daily_water_use ADD COLUMN precip_inches REAL")
    conn.execute("DROP VIEW IF EXISTS latest_water_use")
    conn.execute("""
        CREATE VIEW latest_water_use AS
        SELECT c.course_id, c.name, c.state, c.latitude, c.longitude,
               c.irrigated_acres, c.turf_type,
               d.date, d.eto_inches, d.precip_inches, d.gallons, d.acre_feet
        FROM courses c
        JOIN daily_water_use d ON d.course_id = c.course_id
        WHERE d.date = (SELECT MAX(date) FROM daily_water_use d2 WHERE d2.course_id = c.course_id)
    """)
    conn.commit()


def compute_for_date(target_date: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    migrate(conn)
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
        precip = weather.get("precip_inches") or 0.0

        net_inches = max(0.0, eto * c["kc"] - precip)
        gallons = net_inches * c["irrigated_acres"] * GALLONS_PER_ACRE_INCH
        acre_feet = (net_inches * c["irrigated_acres"]) / 12.0

        conn.execute(
            """INSERT OR REPLACE INTO daily_water_use
               (course_id, date, eto_inches, precip_inches, gallons, acre_feet)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (c["course_id"], target_date, eto, precip, gallons, acre_feet),
        )
        rows_written += 1
        rain_note = f", rain={precip:.2f}in offset" if precip else ""
        print(f"  {c['name']}: ETo={eto:.2f}in{rain_note} -> {gallons:,.0f} gal")

    conn.commit()
    conn.close()
    print(f"Done. {rows_written}/{len(courses)} courses updated for {target_date}.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else (date_cls.today() - timedelta(days=1)).isoformat()
    print(f"Computing water use estimates for {target}...")
    compute_for_date(target)
