"""
Fetch daily reference evapotranspiration (ETo) from CIMIS (California)
and AZMET (Arizona).

CIMIS -- queried directly by lat/lon coordinate via the Spatial CIMIS
System (SCS), so no station assignment is needed for CA courses. Confirmed
against the current API docs at https://cimis.water.ca.gov/web-api/rest-api/latest
(CIMIS moved off its old single-endpoint API to five separate REST
endpoints behind Azure API Management). Coordinate requests go to
GetDataBySpatialCoordinates and auth is via the Ocp-Apim-Subscription-Key
header, NOT a query-string appKey -- the old /api/data + appKey= approach
is a decommissioned endpoint that gets rejected by CIMIS's edge WAF before
it's even parsed. Register a free key at https://cimis.water.ca.gov/, then
set the CIMIS_APP_KEY environment variable. Coordinates outside California
return ERR1034.

AZMET -- station-based, public API, no key required. Confirmed endpoint
format from AZMET's own PDF ("Programmatic Access to Hourly and Daily
AZMet Data with a Web API"):
    https://api.azmet.arizona.edu/v1/observations/daily/{stationID}/{startDate}/{timeInterval}
e.g. https://api.azmet.arizona.edu/v1/observations/daily/az27/2026-07-20T00:00/P0DT0H
stationID is one of AZMET's ~30 station codes (see AZMET_STATIONS below
for the ones relevant to the Scottsdale/Phoenix courses). Confirmed
against a live response: the record lives at data['data'][0], and ETo in
inches is under 'eto_pen_mon_in' (ASCE Penman-Monteith).
"""
import os
import requests

CIMIS_APP_KEY = os.environ.get("CIMIS_APP_KEY", "")
CIMIS_SPATIAL_COORDS_URL = "https://et.water.ca.gov/SpatialWeb/GetDataBySpatialCoordinates"
AZMET_URL = "https://api.azmet.arizona.edu/v1/observations/daily"

# Both CIMIS and AZMET sit behind bot-detecting edge protection that
# rejects requests' default "python-requests/x.y.z" User-Agent outright.
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
        "coordinates": f"lat={lat},lng={lon}",
        "startDate": date,
        "endDate": date,
        "dataItems": "day-asce-eto",
        "unitOfMeasure": "E",
    }
    headers = {**REQUEST_HEADERS, "Ocp-Apim-Subscription-Key": CIMIS_APP_KEY}
    resp = requests.get(CIMIS_SPATIAL_COORDS_URL, params=params, headers=headers, timeout=30)
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
