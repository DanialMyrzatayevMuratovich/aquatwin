"""Dry-spell (flash drought) risk engine.

1. Turn the 14-day water balance into day-of-year percentiles against the 1991-2020 ERA5 norm.
2. In every ensemble scenario look for a dry spell: the percentile falls from >=40 to <=20
   within 20 days and stays there (thresholds of Ford & Labosier 2017, adapted).
3. Risk level = share of scenarios with a dry spell.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import balance, config

LEVELS = ("low", "moderate", "high", "ongoing")


def _reference(clim: pd.Series, window: int):
    """Sorted norm values for a day of year (wraps around the new year)."""
    doys, vals = clim.index.dayofyear.values, clim.values
    cache: dict[int, np.ndarray] = {}

    def ref(doy: int) -> np.ndarray:
        if doy not in cache:
            diff = np.abs(doys - doy)
            cache[doy] = np.sort(vals[np.minimum(diff, 366 - diff) <= window])
        return cache[doy]
    return ref


def percentiles(values: pd.Series | pd.DataFrame, clim: pd.Series,
                window: int = config.CLIM_WINDOW_DAYS) -> pd.Series | pd.DataFrame:
    """Percentile (0-100) of each value relative to the norm around the same day of year."""
    ref = _reference(clim, window)
    out = np.full(values.shape, np.nan)
    for i, ts in enumerate(values.index):
        r = ref(ts.dayofyear)
        if len(r):
            out[i] = 100.0 * np.searchsorted(r, values.values[i], side="right") / len(r)
    out[np.isnan(values.values)] = np.nan
    return type(values)(out, index=values.index, **({"columns": values.columns} if out.ndim == 2 else {}))


def detect_onset(pct: pd.Series, start_idx: int = 0) -> pd.Timestamp | None:
    """First date (at/after start_idx) where a dry spell starts.

    The percentile is <= LOW after being >= HIGH within the previous WINDOW days, and it
    stays <= LOW for MIN_DRY_DAYS (or until the end of the series if fewer days remain).
    """
    vals = pct.values
    for i in range(max(start_idx, 1), len(vals)):
        if not vals[i] <= config.FD_LOW_PCT:
            continue
        lo = max(0, i - config.FD_WINDOW_DAYS)
        if not np.max(vals[lo:i]) >= config.FD_HIGH_PCT:
            continue
        if np.all(vals[i:i + config.FD_MIN_DRY_DAYS] <= config.FD_LOW_PCT):
            return pct.index[i]
    return None


def in_season(date: pd.Timestamp) -> bool:
    return config.SEASON_START <= (date.month, date.day) <= config.SEASON_END


def scan_ensemble(obs_pct: pd.Series, paths_pct: pd.DataFrame) -> dict:
    """Dry-spell statistics over scenarios: onset dates, their share, and the percentile corridor."""
    lead = obs_pct.iloc[-config.FD_WINDOW_DAYS:]
    onsets = []
    for member in paths_pct.columns:
        onset = detect_onset(pd.concat([lead, paths_pct[member]]), start_idx=len(lead))
        if onset is not None:
            onsets.append(onset)
    n = paths_pct.shape[1]
    q = paths_pct.quantile([0.1, 0.5, 0.9], axis=1).T
    return {"n_members": n, "n_dry": len(onsets), "p_dry": len(onsets) / n, "onsets": onsets,
            "timeline": pd.DataFrame({"percentile": q[0.5], "p10": q[0.1], "p90": q[0.9]})}


@dataclass
class Assessment:
    level: str
    current_pct: float
    deficit_mm: float
    norm_mm: float
    anomaly_pct: float | None
    p_dry: float
    n_members: int
    n_dry: int
    onset_date: pd.Timestamp | None
    days_to_onset: int | None
    in_season: bool
    source: str
    as_of: pd.Timestamp
    timeline: pd.DataFrame = field(repr=False)
    ai: dict | None = field(default=None, repr=False)

    def summary(self) -> dict:
        return {
            "level": self.level,
            "current_pct": round(self.current_pct, 1),
            "deficit_mm": round(self.deficit_mm),
            "norm_mm": round(self.norm_mm),
            "p_dry": round(100 * self.p_dry) if self.n_members > 1 else None,
            "ai_p_dry": round(100 * self.ai["p_dry"]) if self.ai else None,
            "onset_date": self.onset_date.date().isoformat() if self.onset_date is not None else None,
            "days_to_onset": self.days_to_onset,
            "in_season": self.in_season,
            "source": self.source,
            "as_of": self.as_of.date().isoformat(),
        }


def assess(region_data: dict) -> Assessment:
    recent, as_of = region_data["recent"], region_data["as_of"]
    clim = balance.clim_balance(region_data["baseline"])

    obs = balance.rolling_balance(balance.daily_balance(recent))
    obs_pct = percentiles(obs, clim)
    current = float(obs_pct.iloc[-1])
    deficit = float(-obs.iloc[-1])
    norm = balance.norm_deficit(clim, as_of)
    anomaly = 100.0 * (deficit - norm) / norm if norm >= 10 else None

    paths = balance.member_paths(recent, region_data["fc_et0"], region_data["fc_precip"])
    ens = scan_ensemble(obs_pct, percentiles(paths, clim))

    ai = None
    if region_data.get("ai_et0") is not None:
        ai_paths = balance.member_paths(recent, region_data["ai_et0"], region_data["ai_precip"])
        ai = scan_ensemble(obs_pct, percentiles(ai_paths, clim))
        del ai["onsets"]

    p = ens["p_dry"]
    onset = days = None
    if p >= config.P_MODERATE and current > config.ONGOING_PCT:  # no start date once the drought is under way
        onset = pd.Series(ens["onsets"]).sort_values().iloc[(ens["n_dry"] - 1) // 2]
        days = int((onset - as_of).days)

    if current <= config.ONGOING_PCT:
        level = "ongoing"
    elif p >= config.P_HIGH:
        level = "high"
    elif p >= config.P_MODERATE or current <= config.FD_LOW_PCT:
        level = "moderate"
    else:
        level = "low"

    timeline = pd.concat([
        pd.DataFrame({"percentile": obs_pct, "p10": np.nan, "p90": np.nan, "kind": "observed"}),
        ens["timeline"].assign(kind="forecast"),
    ])
    return Assessment(level, current, deficit, norm, anomaly, p, ens["n_members"], ens["n_dry"], onset, days,
                      in_season(as_of), region_data["source"], as_of, timeline, ai)
