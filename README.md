# 💧 AquaTwin — flash-drought early warning for farmers in arid regions

AquaTwin warns smallholder farmers **up to 6 weeks ahead** that a dry spell is coming and tells them
**what to do**, in Kazakh, Russian or English, via Telegram.

Pilot: 8 irrigated districts of Turkistan and Kyzylorda regions, Kazakhstan (Aral Sea basin).
Bot: [@AquaTwin_Bot](https://t.me/AquaTwin_Bot).

## Status (11 October 2026)

| What | State |
|---|---|
| Live data for 8 districts (ECMWF via Open-Meteo) | Works at any hour; checked on 11.10.2026 |
| Risk from 51 ECMWF ensemble scenarios | Works |
| ECMWF AIFS AI ensemble shown next to it (2 weeks) | Works; does not affect the risk level |
| Dashboard and Telegram bot in kk / ru / en | Work; 43 offline tests pass on Python 3.10 and 3.12 |
| Replay of real history (no internet needed) | Works for any date from 1991 to 2025 |
| History check 1991–2025 | Done, see `reports/` |
| Deployment on Render | Files are ready (`render.yaml`); not deployed yet |
| Own trained ML model | Not built |
| NVIDIA Earth-2 runs | Not done: needs a GPU with 40 GB of memory |
| Advice reviewed by an agronomist, farmer interviews | Not done |

## How it works

```
ERA5 1991–2025 (in data/baseline/) ─► norm of the 14-day water balance, per day of year
Recent observations (ERA5 + IFS) ──┐
ECMWF EC46: 51 scenarios, 6 weeks ─┴► water balance per scenario ─► percentile ─► dry spell? ─► risk level
ECMWF AIFS (AI): 51 scenarios, 2 weeks ─► the same, shown for comparison                       │
                                                                                                │
                                     Streamlit dashboard (map, corridor of scenarios) ◄─────────┤
                                     Telegram bot (location ► advice kk/ru/en) ◄────────────────┘
```

* **Indicator:** 14-day climatic water balance = precipitation − reference evapotranspiration
  (FAO-56 ET0), in mm. A low balance means the atmosphere takes far more water than rain brings,
  so crops need more irrigation water.
* **Percentile:** today's balance compared with 1991–2020 for the same time of year (±15 days).
* **Dry spell in a scenario:** the percentile falls from ≥ 40 to ≤ 20 within 20 days and stays there
  for 7 days. The 40/20/20 thresholds come from Ford & Labosier (2017), who defined them for soil
  moisture; applying them to the water balance is our adaptation. The 7 days were calibrated on
  1991–2014 (`reports/calibration.json`).
* **Risk levels:** 🟤 ongoing (percentile now ≤ 10) · 🔴 high (≥ 50 % of scenarios have a dry spell) ·
  🟡 moderate (≥ 25 %, or percentile now ≤ 20) · 🟢 low.
* **Why not soil moisture:** the first version used ERA5-Land soil moisture. In these irrigated
  desert districts the model's soil sits at its minimum every summer, so the percentile was noise.

Data is free via [Open-Meteo](https://open-meteo.com) (non-commercial licence). If the APIs cannot be
reached, the app shows the last saved result and then a **replay of real history**, clearly labelled.
There is no synthetic data anywhere in the product.

## What the history check found (`reports/`)

All numbers are from ERA5 reanalysis for the 8 pilot districts, irrigation season 1 April – 30 September.

* 399 dry spells in 35 seasons; 1.3 per district per season in 1991–2014 and 1.7 in 2015–2025.
* By period: 0.7 per district per season in 1991–2000, 1.4 in 2001–2010, 1.9 in 2011–2020, 1.9 in 2021–2025.
* In 2021–2025, 22 % of season days were at or below the 10th percentile of 1991–2020 (7 % in 1991–2020).
* 2021 is the driest season of the 35 in Kyzylorda, Maktaaral and Zhetysay, and the second driest in
  Ordabasy, Sairam and Shardara.
* The longest dry spell of 2021–2025: Maktaaral, from 21 May 2021, 61 days. It is the default replay episode.

These are facts about the reanalysis, not yet checked against station data or official drought reports.

## Run

```bash
pip install -r requirements.txt

# Dashboard
streamlit run app.py                     # opens http://localhost:8501

# Telegram bot
export TELEGRAM_TOKEN=123456:ABC...      # from @BotFather; Windows: set TELEGRAM_TOKEN=...
python bot.py                            # add --replay to demonstrate without internet

# Tests (no network needed)
python -m pytest -q tests
```

Bot usage: `/start` → choose language → **Send location**, or `/district maktaaral`,
or `/replay 2021-05-07 maktaaral` for a past date.

Maintenance scripts:

```bash
python scripts/build_baseline.py         # re-download data/baseline/ (ERA5, 35 years, 8 districts)
python scripts/save_fixtures.py          # re-record the API responses used by the tests
pip install -r requirements-dev.txt && python scripts/history.py   # rebuild reports/
```

## Deploy on Render

`render.yaml` describes two free web services: `aquatwin-dashboard` and `aquatwin-bot`.
In Render: **New → Blueprint**, pick this repository, then set `TELEGRAM_TOKEN` for the bot service.
The bot switches to webhook mode on Render by itself. Free services sleep after 15 minutes without
requests and take about a minute to wake up, so open both a few minutes before a demo.

## Project structure

| Path | What it does |
|---|---|
| `aquatwin/config.py` | Pilot districts, thresholds, irrigation season |
| `aquatwin/data.py` | Open-Meteo clients, baseline files, snapshot, replay, fallback chain |
| `aquatwin/balance.py` | Water balance and scenario paths |
| `aquatwin/drought.py` | Percentiles, dry-spell detection, probability, risk level |
| `aquatwin/advice.py` | Risk → farmer message in kk / ru / en |
| `app.py` | Streamlit dashboard |
| `bot.py` | Telegram bot (polling locally, webhook on Render) |
| `data/baseline/` | ERA5 daily ET0 and precipitation, 1991–2025, per district |
| `reports/` | Output of `scripts/history.py` |
| `tests/` | 43 offline tests, including one on recorded real API responses |
| `AQUATWIN_TZ_V2.md` | Specification (in Russian); it overrides the older `AQUATWIN_SPEC.md` |

## Honest limitations

* District-level (25–36 km grids), not field-level.
* The 6-week forecast has not been verified against past forecasts: no archive of them is available
  to us yet. The probability thresholds (50 % and 25 %) are initial values.
* Precipitation differs a lot between weather models, so the indicator is less certain in spring,
  when rain decides the balance. In summer there is almost no rain and this matters little.
* The ECMWF AIFS AI ensemble is shown for comparison only; we have not verified it on past seasons.
* Advice texts are generic and have not been reviewed by an agronomist. Kazakh texts need a native
  speaker's review.
* The irrigation season (April–September) is one setting for all districts and crops.

## Roadmap

1. **Evidence:** archive our own daily forecasts, train and honestly score an ML model
   (`ML_MODULE_SPEC.md`), review advice with an agronomist, interview farmers.
2. **NVIDIA Earth-2 / Earth2Studio:** run sub-seasonal AI ensembles (FuXi-S2S, DLESyM) ourselves as a
   second 6-week forecast source. The risk engine already takes any "date × scenario" table.
3. **Downscaling to fields** with CorrDiff: needs regional training data and far more compute.
4. Subscriptions, a view for water users' associations and akimats, more districts.
