# Desert Golf Course Water Use Map

Estimates daily irrigation water use for desert golf courses in California
and Arizona, using the standard formula:

    gallons = ETo_inches x Kc x irrigated_acres x 27,154

- **ETo** (reference evapotranspiration) comes from CIMIS (CA) or AZMET (AZ)
- **Kc** (crop coefficient) is set per course based on turf type/season
- **27,154** = gallons per acre-inch of water

Map rendering uses `datasette-cluster-map`, which auto-plots any table/view
with `latitude`/`longitude` columns.

## Setup

```bash
pip install -r requirements.txt
python scripts/seed_courses.py          # creates data/golf_water.db, loads 15 starter courses
```

## Weather source assignment (already done)

- **CIMIS (CA courses):** no station-matching needed at all. CIMIS's
  Spatial CIMIS System (SCS) supports querying ETo directly by lat/lon
  coordinate, so each CA course queries its own exact location. This is
  more accurate than nearest-station matching and is what
  `fetch_cimis_eto_by_coords()` does. Still requires a free `CIMIS_APP_KEY`
  (register at https://cimis.water.ca.gov/) -- station/coordinate metadata
  is public, but the actual weather-data endpoint needs a key.
- **AZMET (AZ courses):** station-based. The station literally named
  "Scottsdale" (az18) is inactive, so all six Scottsdale-area courses are
  assigned to **Desert Ridge (az27)**, the nearest active AZMET station --
  itself sited on an urban golf course (33.69, -111.96), a good analog for
  turf ET in that area. No API key needed for AZMET.

**Note on AZMET's exact field name:** I confirmed AZMET's real API endpoint
format from their own documentation (`/v1/observations/daily/{stationID}/{startDate}/{timeInterval}`,
e.g. `.../daily/az27/2026-07-20T00:00/P0DT0H`), but couldn't make a live
test call from this environment (their site blocks automated fetches).
AZMET publishes both an "ASCE Penman-Monteith" and their own "original"
daily ETo in inches -- `fetch_azmet_eto()` guesses at the JSON field name;
run it once against a real date and adjust the key in `scripts/fetch_eto.py`
if it doesn't match.

If you add courses elsewhere in CA or AZ later, CA ones need no station
assignment (just `et_network='CIMIS'`); AZ ones need whichever AZMET
station is nearest -- full list at https://azmet.arizona.edu/about/station-metadata.

## Run the daily calculation

```bash
export CIMIS_APP_KEY=your_key_here
cd scripts
python compute_water_use.py              # today
python compute_water_use.py 2026-07-20    # backfill a specific date
```

This populates `daily_water_use`. Run it daily (cron or GitHub Actions,
same pattern as your blog pipeline) to build up history.

## View the map

```bash
datasette data/golf_water.db --metadata metadata.json
```

Open the `latest_water_use` view — it renders as a map automatically, with
marker size/popup showing each course's most recent gallons estimate.

## Deploy to Fly.io

Same pattern as your Datasette blog pipeline:

```bash
datasette publish fly data/golf_water.db \
  --app golf-water-map \
  --metadata metadata.json \
  --install datasette-cluster-map
```

For the daily refresh in production, add a GitHub Actions workflow that
runs `compute_water_use.py` on a schedule, commits the updated `.db` file
(or writes to a Litestream-replicated volume), and re-publishes — mirroring
whatever your blog pipeline already does for scheduled updates.

## Refining acreage estimates

Irrigated acreage is currently a flat guess (~90-130 acres/course). For a
real figure, delineate irrigated turf from satellite NDVI (Sentinel-2 via
Google Earth Engine, free) per course polygon rather than relying on public
records, which are inconsistent.

## Files

```
schema.sql                    - courses + daily_water_use tables, latest_water_use view
scripts/seed_courses.py       - loads 15 starter CA/AZ courses with real coordinates
scripts/fetch_eto.py          - CIMIS + AZMET API calls
scripts/compute_water_use.py  - ties it together, writes daily estimates
metadata.json                 - Datasette config (map plugin + canned queries)
```
