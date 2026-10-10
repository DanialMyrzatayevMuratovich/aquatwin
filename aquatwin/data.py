"""Data access: ERA5 baseline, recent observations, ECMWF EC46 and AIFS ensembles.

All sources are free via Open-Meteo (non-commercial use). `load_region()` never
raises on network problems: it falls back to the last good snapshot and then to
a replay of real history from the baseline files shipped with the repository.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import logging
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE_DIR = ROOT / "data" / "baseline"
CACHE_DIR = ROOT / "data_cache"
TIMEOUT = 20
RETRY_PAUSES = (1, 3)  # seconds between the three attempts
DAILY = f"{config.ET0_VAR},{config.PRECIP_VAR}"


class DataError(RuntimeError):
    """The data API refused the request or returned unusable data."""


def utc_today() -> dt.date:
    """Open-Meteo validates dates in UTC, so the local date must never be used."""
    return dt.datetime.now(dt.timezone.utc).date()


def _get(url: str, params: dict) -> dict:
    """GET with retries on timeouts, 429 and 5xx; client errors keep the API's reason."""
    error = DataError("no attempt made")
    for attempt in range(len(RETRY_PAUSES) + 1):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            try:
                js = r.json()
            except ValueError:
                js = {}
            if r.status_code == 200 and not js.get("error"):
                return js
            error = DataError(js.get("reason") or f"HTTP {r.status_code}")
            if r.status_code != 429 and r.status_code < 500:
                break
        except requests.RequestException as e:
            error = DataError(f"{type(e).__name__}: {e}")
        if attempt < len(RETRY_PAUSES):
            log.warning("%s failed (%s), retrying", url, error)
            time.sleep(RETRY_PAUSES[attempt])
    log.warning("%s failed: %s", url, error)
    raise error


def _frame(js: dict) -> pd.DataFrame:
    daily = js.get("daily") or {}
    if "time" not in daily:
        raise DataError("no daily block in response")
    cols = {k: v for k, v in daily.items() if k != "time"}
    return pd.DataFrame(cols, index=pd.to_datetime(daily["time"])).astype(float)


def _obs(js: dict) -> pd.DataFrame:
    """Daily observations as columns et0, precip (mm/day)."""
    f = _frame(js)
    try:
        return f.rename(columns={config.ET0_VAR: "et0", config.PRECIP_VAR: "precip"})[["et0", "precip"]]
    except KeyError as e:
        raise DataError(f"variable missing in response: {e}") from e


def _members(js: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ensemble response -> (et0, precip), each date x member (m00 = control run)."""
    f = _frame(js)
    out = []
    for var in (config.ET0_VAR, config.PRECIP_VAR):
        cols = [c for c in f if c.startswith(var)]
        if not cols:
            raise DataError(f"{var} missing in response")
        part = f[cols].copy()
        part.columns = ["m" + (c[len(var):].replace("_member", "") or "00") for c in cols]
        out.append(part)
    return out[0], out[1]


def _future(et0: pd.DataFrame, precip: pd.DataFrame, as_of: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Days after `as_of`, trimmed to the last day filled for every member, without gaps."""
    ok = (et0.notna() & precip.notna()).all(axis=1)
    ok = ok[ok.index > as_of]
    if not ok.any():
        raise DataError("forecast has no filled days")
    days = ok.loc[:ok[ok].index[-1]]
    if not days.all() or days.index[0] != as_of + dt.timedelta(days=1):
        raise DataError("forecast does not continue the observations day by day")
    return et0.loc[days.index], precip.loc[days.index]


# ---------------------------------------------------------------- baseline
def baseline_path(region_id: str) -> pathlib.Path:
    return BASELINE_DIR / f"{region_id}.csv.gz"


def fetch_baseline(lat: float, lon: float) -> pd.DataFrame:
    return _obs(_get(ARCHIVE_URL, {
        "latitude": lat, "longitude": lon,
        "start_date": f"{config.BASELINE_START}-01-01", "end_date": f"{config.BASELINE_END}-12-31",
        "daily": DAILY, "models": "era5", "timezone": "auto",
    }))


@functools.lru_cache(maxsize=None)
def _read_baseline(path: pathlib.Path) -> pd.DataFrame:
    return pd.read_csv(path, index_col="date", parse_dates=True)


def load_baseline(region: dict) -> pd.DataFrame:
    """ERA5 daily et0 and precip for 1991-2025; shipped with the repo, fetched only if missing."""
    path = baseline_path(region["id"])
    if not path.exists():
        df = fetch_baseline(region["lat"], region["lon"])
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index_label="date", float_format="%.2f")
    return _read_baseline(path)


# ---------------------------------------------------------------- live sources
def scale_factor(ref: pd.Series, other: pd.Series, min_days: int = config.SCALE_MIN_DAYS) -> float:
    """Ratio that brings `other` to the level of `ref` over their common days (1.0 if too few)."""
    idx = ref.dropna().index.intersection(other.dropna().index)
    if len(idx) < min_days or other[idx].sum() <= 0:
        log.warning("only %d common days, ET0 is not scaled", len(idx))
        return 1.0
    return float(np.clip(ref[idx].sum() / other[idx].sum(), *config.SCALE_CLIP))


def merge_recent(era: pd.DataFrame, ifs: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """ERA5 where it exists (same model as the baseline); the latest days from IFS with ET0 scaled."""
    era, ifs = era.dropna(), ifs.dropna()
    k = scale_factor(era["et0"], ifs["et0"])
    tail = ifs.loc[~ifs.index.isin(era.index)].copy()
    tail["et0"] *= k
    out = pd.concat([era, tail]).sort_index().asfreq("D").interpolate(limit=3)
    out = out.loc[out.first_valid_index():out.last_valid_index()]
    if out.empty or out.isna().any().any():
        raise DataError("gap in recent observations")
    return out, k


def fetch_recent(lat: float, lon: float, today: dt.date) -> tuple[pd.DataFrame, float]:
    base = {
        "latitude": lat, "longitude": lon,
        "start_date": (today - dt.timedelta(days=config.RECENT_DAYS)).isoformat(),
        "end_date": (today - dt.timedelta(days=1)).isoformat(),  # today's sums are not complete yet
        "daily": DAILY, "timezone": "auto",
    }
    ifs = _obs(_get(ARCHIVE_URL, base))
    try:
        era = _obs(_get(ARCHIVE_URL, {**base, "models": "era5"}))
    except DataError:
        era = ifs.iloc[:0]
    return merge_recent(era, ifs)


def fetch_forecast(lat: float, lon: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ECMWF EC46 sub-seasonal ensemble, including past days for ET0 scaling."""
    return _members(_get(SEASONAL_URL, {
        "latitude": lat, "longitude": lon, "daily": DAILY, "models": "ecmwf_ec46",
        "forecast_days": config.FORECAST_DAYS, "past_days": config.EC46_PAST_DAYS, "timezone": "auto",
    }))


def fetch_ai_ensemble(lat: float, lon: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """ECMWF AIFS: an AI weather model ensemble, two weeks ahead."""
    return _members(_get(ENSEMBLE_URL, {
        "latitude": lat, "longitude": lon, "daily": DAILY, "models": "ecmwf_aifs025",
        "forecast_days": config.AI_FORECAST_DAYS, "past_days": config.AI_PAST_DAYS, "timezone": "auto",
    }))


def live_region(region: dict, today: dt.date) -> dict:
    lat, lon = region["lat"], region["lon"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        f_recent = pool.submit(fetch_recent, lat, lon, today)
        f_fc = pool.submit(fetch_forecast, lat, lon)
        f_ai = pool.submit(fetch_ai_ensemble, lat, lon)
    recent, k_ifs = f_recent.result()
    as_of = recent.index[-1]
    et0, precip = f_fc.result()
    k_fc = scale_factor(recent["et0"], et0.mean(axis=1))
    fc_et0, fc_precip = _future(et0 * k_fc, precip, as_of)
    out = {"baseline": load_baseline(region), "recent": recent, "fc_et0": fc_et0, "fc_precip": fc_precip,
           "ai_et0": None, "ai_precip": None, "source": "live", "as_of": as_of,
           "scales": {"ifs": round(k_ifs, 3), "ec46": round(k_fc, 3)}}
    try:
        ai_et0, ai_precip = _future(*f_ai.result(), as_of)
        # No past days to compare with observations, so AIFS ET0 is brought to the EC46 level
        # over their first common week; what happens in week two stays the AI model's own.
        week = slice(0, config.AI_ANCHOR_DAYS)
        k_ai = scale_factor(fc_et0.iloc[week].mean(axis=1), ai_et0.iloc[week].mean(axis=1), config.AI_ANCHOR_DAYS)
        out["ai_et0"], out["ai_precip"] = ai_et0 * k_ai, ai_precip
        out["scales"]["aifs"] = round(k_ai, 3)
    except Exception as e:  # the AI layer is optional: without it the assessment is the same
        log.warning("AI ensemble unavailable for %s: %s", region["id"], e)
    return out


# ---------------------------------------------------------------- replay
def replay_region(region: dict, date: dt.date | str | None = None) -> dict:
    """Real history as of `date`: what happened next stands in for the forecast. Not a forecast."""
    base = load_baseline(region)
    as_of = pd.Timestamp(date or config.REPLAY_DEFAULT_DATE).normalize()
    recent = base.loc[as_of - dt.timedelta(days=config.RECENT_DAYS - 1):as_of]
    actual = base.loc[as_of + dt.timedelta(days=1):as_of + dt.timedelta(days=config.FORECAST_DAYS - 2)]
    if len(recent) < config.RECENT_DAYS or len(actual) < config.FORECAST_DAYS - 2:
        raise ValueError(f"replay date {as_of.date()} is outside the baseline period")
    return {"baseline": base, "recent": recent, "fc_et0": actual[["et0"]].rename(columns={"et0": "actual"}),
            "fc_precip": actual[["precip"]].rename(columns={"precip": "actual"}),
            "ai_et0": None, "ai_precip": None, "source": "replay", "as_of": as_of, "scales": {}}


# ---------------------------------------------------------------- snapshot
_FRAMES = ("recent", "fc_et0", "fc_precip", "ai_et0", "ai_precip")


def _snapshot_path(region_id: str) -> pathlib.Path:
    return CACHE_DIR / f"last_good_{region_id}.json"


def save_snapshot(region_id: str, data: dict) -> None:
    payload = {"saved_at": dt.datetime.now(dt.timezone.utc).isoformat(), "as_of": data["as_of"].isoformat(),
               "scales": data["scales"]}
    for key in _FRAMES:
        payload[key] = None if data[key] is None else json.loads(data[key].to_json(orient="split", date_format="iso"))
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        _snapshot_path(region_id).write_text(json.dumps(payload))
    except OSError as e:
        log.warning("could not save snapshot for %s: %s", region_id, e)


def load_snapshot(region: dict) -> dict | None:
    """The last good live result, if it is younger than SNAPSHOT_MAX_AGE_H."""
    try:
        payload = json.loads(_snapshot_path(region["id"]).read_text())
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(payload["saved_at"])
        if age > dt.timedelta(hours=config.SNAPSHOT_MAX_AGE_H):
            return None
        out = {"baseline": load_baseline(region), "source": "snapshot", "as_of": pd.Timestamp(payload["as_of"]),
               "scales": payload["scales"]}
        for key in _FRAMES:
            p = payload[key]
            out[key] = None if p is None else pd.DataFrame(p["data"], index=pd.to_datetime(p["index"]), columns=p["columns"])
        return out
    except (OSError, ValueError, KeyError, TypeError):
        return None


# ---------------------------------------------------------------- public API
def load_region(region: dict, today: dt.date | None = None, mode: str = "live",
                replay_date: dt.date | str | None = None) -> dict:
    """Region data for `drought.assess()`.

    Keys: baseline, recent, fc_et0, fc_precip, ai_et0, ai_precip, source, as_of, scales.
    mode="live" falls back to the last good snapshot and then to a replay of history.
    """
    if mode == "replay":
        return replay_region(region, replay_date)
    try:
        data = live_region(region, today or utc_today())
        save_snapshot(region["id"], data)
        return data
    except DataError as e:
        log.warning("live data unavailable for %s: %s", region["id"], e)
    except Exception:  # an unexpected response shape must not take the dashboard or the bot down
        log.exception("unexpected error while loading %s", region["id"])
    return load_snapshot(region) or replay_region(region)
