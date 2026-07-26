-- Golf course water use tracker schema

CREATE TABLE IF NOT EXISTS courses (
    course_id       INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    state           TEXT NOT NULL,          -- 'CA' or 'AZ'
    latitude        REAL NOT NULL,
    longitude       REAL NOT NULL,
    irrigated_acres REAL NOT NULL,          -- estimated irrigated turf area
    turf_type       TEXT NOT NULL DEFAULT 'bermuda_overseeded',
    kc              REAL NOT NULL,          -- crop coefficient for turf_type
    et_station_id   TEXT,                   -- AZMET station code (e.g. 'az27'); NULL for CIMIS courses, which query by lat/lon directly
    et_network      TEXT                    -- 'CIMIS' or 'AZMET'
);

CREATE TABLE IF NOT EXISTS daily_water_use (
    course_id       INTEGER NOT NULL REFERENCES courses(course_id),
    date            TEXT NOT NULL,          -- YYYY-MM-DD
    eto_inches      REAL,                   -- reference ET for that day
    tmax_f          REAL,
    tmin_f          REAL,
    wind_mph        REAL,
    gallons         REAL,                   -- estimated water use = ETo * Kc * area, converted
    acre_feet       REAL,
    PRIMARY KEY (course_id, date)
);

-- Convenience view for the map / latest-day lookups
CREATE VIEW IF NOT EXISTS latest_water_use AS
SELECT c.course_id, c.name, c.state, c.latitude, c.longitude,
       c.irrigated_acres, c.turf_type,
       d.date, d.eto_inches, d.gallons, d.acre_feet
FROM courses c
JOIN daily_water_use d ON d.course_id = c.course_id
WHERE d.date = (SELECT MAX(date) FROM daily_water_use d2 WHERE d2.course_id = c.course_id);
