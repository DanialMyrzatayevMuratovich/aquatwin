"""Pilot region configuration.

District centres are approximate (good enough for 9-36 km weather grids).
"""

REGIONS = [
    # name_en, name_ru, name_kk, lat, lon
    {"id": "maktaaral", "en": "Maktaaral", "ru": "Мактааральский", "kk": "Мақтаарал", "lat": 40.67, "lon": 68.55},
    {"id": "zhetysay", "en": "Zhetysay", "ru": "Жетысайский", "kk": "Жетісай", "lat": 40.78, "lon": 68.33},
    {"id": "shardara", "en": "Shardara", "ru": "Шардаринский", "kk": "Шардара", "lat": 41.25, "lon": 67.97},
    {"id": "sairam", "en": "Sairam", "ru": "Сайрамский", "kk": "Сайрам", "lat": 42.23, "lon": 69.88},
    {"id": "ordabasy", "en": "Ordabasy", "ru": "Ордабасинский", "kk": "Ордабасы", "lat": 42.60, "lon": 69.25},
    {"id": "otyrar", "en": "Otyrar", "ru": "Отырарский", "kk": "Отырар", "lat": 42.78, "lon": 68.36},
    {"id": "turkistan", "en": "Turkistan", "ru": "Туркестан", "kk": "Түркістан", "lat": 43.30, "lon": 68.25},
    {"id": "kyzylorda", "en": "Kyzylorda", "ru": "Кызылорда", "kk": "Қызылорда", "lat": 44.85, "lon": 65.50},
]

# Drought indicator: 14-day climatic water balance = precipitation - reference
# evapotranspiration (FAO-56 ET0), in mm. Low balance = the atmosphere takes far
# more water than rain brings.
ET0_VAR = "et0_fao_evapotranspiration"
PRECIP_VAR = "precipitation_sum"
BALANCE_DAYS = 14

# Baseline files hold 1991-2025 (ERA5); the norm is the WMO standard period.
BASELINE_START, BASELINE_END = 1991, 2025
CLIM_START, CLIM_END = 1991, 2020
CLIM_WINDOW_DAYS = 15  # +/- days around day-of-year for percentile baseline

RECENT_DAYS = 75      # 60 days on the chart + 14 for the rolling window
FORECAST_DAYS = 46    # ECMWF EC46 sub-seasonal horizon (the API returns 44 filled days)
EC46_PAST_DAYS = 60   # overlap with observations used to scale forecast ET0
AI_FORECAST_DAYS = 16  # ECMWF AIFS ensemble (the API returns 14 filled days)
AI_PAST_DAYS = 3
AI_ANCHOR_DAYS = 7     # AIFS ET0 is scaled to EC46 over the first common week
SCALE_CLIP = (0.80, 1.25)
SCALE_MIN_DAYS = 30

# Dry spell (flash drought) in a scenario: the balance percentile falls from
# >= FD_HIGH_PCT to <= FD_LOW_PCT within FD_WINDOW_DAYS and stays there for
# FD_MIN_DRY_DAYS. Thresholds follow Ford & Labosier (2017), who defined them for
# soil moisture; applying them to the water balance is our adaptation.
FD_HIGH_PCT = 40
FD_LOW_PCT = 20
FD_WINDOW_DAYS = 20
FD_MIN_DRY_DAYS = 7  # calibrated on 1991-2014, see reports/calibration.json

# Risk levels. P_* are shares of ensemble scenarios with a dry spell; they are
# initial values and cannot be calibrated until past forecasts are archived.
ONGOING_PCT = 10
P_HIGH, P_MODERATE = 0.50, 0.25

# Irrigation season (month, day); to be confirmed with an agronomist.
SEASON_START, SEASON_END = (4, 1), (9, 30)

SNAPSHOT_MAX_AGE_H = 48
REPLAY_DEFAULT_DATE = "2021-05-07"  # 14 days before the longest dry spell of 2021-2025, see reports/calibration.json
