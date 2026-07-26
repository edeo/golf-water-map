"""
Seed the courses table with a starter set of desert golf courses in
CA (Coachella Valley) and AZ (Scottsdale/Phoenix).

Irrigated acreage is a placeholder estimate (~100 acres, typical for an
18-hole desert course) until replaced with NDVI-derived figures -- see
README for the satellite-imagery approach to refine this.

et_network/et_station_id are set for real here:
- CA courses: network='CIMIS', station left NULL -- CIMIS is queried
  directly by each course's own lat/lon (see fetch_eto.py), so no
  station assignment is needed.
- AZ courses: network='AZMET', station='az27' (Desert Ridge) -- the
  nearest *active* AZMET station to the Scottsdale cluster. The
  station literally named "Scottsdale" (az18) is inactive, and
  Desert Ridge is itself sited on an urban golf course, which is a
  good analog for turf ET in this area.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "golf_water.db"
SCHEMA_PATH = ROOT / "schema.sql"

COURSES = [
    # name, state, lat, lon, acres, turf_type, kc, et_network, et_station_id
    ("Escena Golf Club", "CA", 33.8343817, -116.4973663, 100, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Tahquitz Creek Golf Resort", "CA", 33.799213, -116.485312, 110, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Indian Canyons Golf Resort - South", "CA", 33.7824754, -116.5345031, 105, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Cimarron Golf Resort", "CA", 33.8294565, -116.4836598, 95, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Desert Willow Golf Resort", "CA", 33.7665348, -116.3666744, 130, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Marriott's Shadow Ridge Golf Club", "CA", 33.7823947, -116.3842909, 100, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Shadow Hills Golf Club", "CA", 33.7573865, -116.2526102, 90, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Eagle Falls Golf Course", "CA", 33.7197264, -116.1844658, 100, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("Tradition Golf Club", "CA", 33.6702458, -116.2949825, 115, "bermuda_overseeded", 0.7, "CIMIS", None),
    ("TPC Scottsdale (Stadium Course)", "AZ", 33.6405764, -111.9089077, 130, "bermuda_overseeded", 0.65, "AZMET", "az27"),
    ("Scottsdale Silverado Golf Club", "AZ", 33.5357728, -111.9152637, 95, "bermuda_overseeded", 0.65, "AZMET", "az27"),
    ("Gainey Ranch Golf Club", "AZ", 33.5699716, -111.9159157, 100, "bermuda_overseeded", 0.65, "AZMET", "az27"),
    ("Troon North Golf Club", "AZ", 33.746226, -111.85877, 110, "bermuda", 0.6, "AZMET", "az27"),
    ("Grayhawk Golf Club", "AZ", 33.6780969, -111.8971717, 120, "bermuda_overseeded", 0.65, "AZMET", "az27"),
    ("McCormick Ranch Golf Club", "AZ", 33.5495151, -111.9203231, 110, "bermuda_overseeded", 0.65, "AZMET", "az27"),
]


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.executemany(
        """INSERT INTO courses
           (name, state, latitude, longitude, irrigated_acres, turf_type, kc, et_network, et_station_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        COURSES,
    )
    conn.commit()
    print(f"Inserted {len(COURSES)} courses into {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
