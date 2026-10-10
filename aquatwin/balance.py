"""Climatic water balance: precipitation minus reference evapotranspiration.

The drought indicator is the balance summed over BALANCE_DAYS (mm). Low values
mean the atmosphere takes far more water than rain brings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def daily_balance(df: pd.DataFrame) -> pd.Series:
    """precip - et0, mm/day."""
    return df["precip"] - df["et0"]


def rolling_balance(daily: pd.Series, days: int = config.BALANCE_DAYS) -> pd.Series:
    return daily.rolling(days).sum().dropna()


def clim_balance(baseline: pd.DataFrame) -> pd.Series:
    """Rolling balance over the norm period (CLIM_START..CLIM_END)."""
    b = rolling_balance(daily_balance(baseline))
    return b[(b.index.year >= config.CLIM_START) & (b.index.year <= config.CLIM_END)]


def member_paths(recent: pd.DataFrame, fc_et0: pd.DataFrame, fc_precip: pd.DataFrame,
                 days: int = config.BALANCE_DAYS) -> pd.DataFrame:
    """Rolling balance for every forecast date and scenario (date x member).

    Each scenario is continued from the observations, so the first forecast days
    mix observed and forecast values. The index is computed per scenario, never
    on the ensemble mean: averaging smears rain over many days and hides dry spells.
    """
    tail = daily_balance(recent).iloc[-(days - 1):]
    fc = fc_precip - fc_et0
    head = pd.DataFrame(np.repeat(tail.values[:, None], fc.shape[1], axis=1), index=tail.index, columns=fc.columns)
    return pd.concat([head, fc]).rolling(days).sum().loc[fc.index]


def norm_deficit(clim: pd.Series, date: pd.Timestamp, window: int = config.CLIM_WINDOW_DAYS) -> float:
    """Median deficit (et0 - precip, mm) of the norm around the same day of year."""
    diff = np.abs(clim.index.dayofyear.values - date.dayofyear)
    diff = np.minimum(diff, 366 - diff)
    return float(-np.median(clim.values[diff <= window]))
