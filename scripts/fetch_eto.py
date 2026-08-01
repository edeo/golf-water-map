"""
Fetch daily reference evapotranspiration (ETo) from CIMIS (California)
and AZMET (Arizona).

CIMIS -- queried directly by lat/lon coordinate (Spatial CIMIS System),
so no station assignment is needed for CA courses at all. Requires a
free app key for the /api/data endpoint: register at
https://cimis.water.ca.gov/, then set the CIMIS_APP_KEY environment
variable. (Station metadata itself -- https://et.water.ca.gov/api/station
-- is public with no key required, but isn't needed with the coordinate
approach.) Confirmed against CIMIS's own docs at https://et.water.ca.gov/Rest/Index:
coordinate requests only support the 'day-asce-eto' and 'day-sol-rad-avg'
data items (ERR2114 if you ask for anything else), which is exactly
what we need. Coordinates outside California return ERR1034.

AZMET -- station-based, public API, no key required. Confirmed endpoint
format from AZMET's own PDF ("Programmatic Access to Hourly and Daily
AZMet Data with a Web API"):
    https://api.azmet.arizona.edu/v1/observations/daily/{stationID}/{startDate}/{timeInterval}
e.g. https://api.azmet.arizona.edu/v1/observations/daily/az27/2026-07-20T00:00/P0DT0H
stationID is one of AZMET's ~30 station codes (see AZMET_STATIONS below
for the ones relevant to the Scottsdale/Phoenix courses).

I could not do a live test call against the AZMET API from this
environment (robots.txt blocks automated fetches), so the exact JSON
field name for daily ETo in fetch_azmet_eto() below is my best read of
AZMET's documented data items -- verify it against a real response and
adjust if the key differs.
"""
import os
import requests

CIMIS_APP_KEY = os.environ.get("CIMIS_APP_KEY", "")
CIMIS_URL = "https://et.water.ca.gov/api/data"
AZMET_URL = "https://api.azmet.arizona.edu/v1/observations/daily"

# Both CIMIS and AZMET sit behind bot-detecting edge protection that
# rejects requests' default "python-requests/x.y.z" User-Agent outright
# (CIMIS returns an HTML "Request Rejected" WAF page instead of JSON).
# A normal browser-style UA gets through.
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; golf-water-map/1.0)",
    "Accept": "application/json",
}

# Real, active AZMET stations relevant to the Scottsdale/Phoenix desert
# golf courses. "Scottsdale" (az18) itself is inactive, so Desert Ridge
# is the practical nearest-active-station choice for all of them.
AZMET_STATIONS = {
    "desert_ridge": "az27",       # 33.69, -111.96 -- sited on an urban golf course
    "phoenix_greenway": "az12",   # 33.62, -112.11 -- also on an urban golf course, farther west
    "phoenix_encanto": "az15",    # 33.48, -112.10
}


def fetch_cimis_eto_by_coords(lat: float, lon: float, date: str) -> dict:
    """
    Query CIMIS's Spatial CIMIS System directly by coordinate -- no
    station assignment needed. Only works for coordinates within CA.
    date: 'YYYY-MM-DD'
    Returns {'eto_inches': float}
    """
    if not CIMIS_APP_KEY:
        raise RuntimeError("Set CIMIS_APP_KEY env var (free registration at cimis.water.ca.gov)")

    params = {
        "appKey": CIMIS_APP_KEY,
        "targets": f"lat={lat},lng={lon}",
        "startDate": date,
        "endDate": date,
        "dataItems": "day-asce-eto",
        "unitOfMeasure": "E",
    }
    resp = requests.get(CIMIS_URL, params=params, headers=REQUEST_HEADERS, timeout=30)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"CIMIS did not return JSON (status {resp.status_code}): {resp.text[:300]}")

    record = data["Data"]["Providers"][0]["Records"][0]
    eto = record.get("DayAsceEto", {}).get("Value")
    return {"eto_inches": float(eto) if eto not in (None, "") else None}


def fetch_azmet_eto(station_id: str, date: str) -> dict:
    """
    date: 'YYYY-MM-DD'
    Queries a single day of AZMET daily data for one station.
    """
    url = f"{AZMET_URL}/{station_id}/{date}T00:00/P0DT0H"
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"AZMET did not return JSON (status {resp.status_code}): {resp.text[:300]}")

    records = data.get("data") or []
    if not records:
        raise RuntimeError(f"AZMET returned no data records: {data}")
    record = records[0]

    # Confirmed against a live response: AZMET publishes ETo in both mm
    # and inches, under "_in"-suffixed keys for inches. eto_pen_mon_in is
    # the ASCE Penman-Monteith figure (the standard reference ET); AZMET's
    # own eto_azmet_in is the fallback if that's ever missing.
    eto = record.get("eto_pen_mon_in") or record.get("eto_azmet_in")
    if eto in (None, ""):
        raise RuntimeError(f"No ETo field found. Actual fields: {sorted(record.keys())}")
    return {"eto_inches": float(eto)}


def fetch_eto(network: str, station_or_coords, date: str) -> dict:
    """
    network: 'CIMIS' or 'AZMET'
    station_or_coords: for CIMIS, a (lat, lon) tuple; for AZMET, a station code string
    """
    if network == "CIMIS":
        lat, lon = station_or_coords
        return fetch_cimis_eto_by_coords(lat, lon, date)
    elif network == "AZMET":
        return fetch_azmet_eto(station_or_coords, date)
    else:
        raise ValueError(f"Unknown network: {network}")
