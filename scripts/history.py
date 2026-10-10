"""History check: what does the dry-spell rule find in 1991-2025?

    pip install -r requirements-dev.txt
    python scripts/history.py

Reads data/baseline/ only (no network) and writes to reports/:
  dry_spell_catalog.csv   every dry spell: district, onset, duration, depth
  seasons_ranking.csv     irrigation seasons ranked by dryness, per district
  calibration.json        how often the rule fires, the thresholds chosen, the replay episode
  events_per_year.png, events_by_month.png, case_<district>_<year>.png

Calibration rule (fixed before looking at results): keep the literature thresholds
(40 -> 20 within 20 days) and lengthen only our own parameter, the number of days the
percentile must stay low, until 1991-2014 gives 0.5-1.5 dry spells per district per
irrigation season. 2015-2025 is then used only to check that number.

Replay episode: the longest in-season dry spell of 2021-2025. The first rule we wrote down,
"largest drop in mm", was rejected after one run: it picks the end of very wet spells
(April 2022 after a record-wet March), not droughts. Both picks are kept in calibration.json.
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aquatwin import balance, config, data, drought  # noqa: E402

REPORTS = ROOT / "reports"
COOLDOWN_DAYS = 30
TRAIN, CHECK = (1991, 2014), (2015, 2025)
TARGET = (0.5, 1.5)          # dry spells per district per irrigation season
MIN_DRY_GRID = (5, 7, 10, 14, 21)
REPLAY_YEARS = (2021, 2025)
REPLAY_LEAD_DAYS = 14        # the replay starts this many days before the onset


def district_series(region: dict) -> tuple[pd.Series, pd.Series]:
    """14-day water balance (mm) and its percentile for 1991-2025."""
    base = data.load_baseline(region)
    b14 = balance.rolling_balance(balance.daily_balance(base))
    return b14, drought.percentiles(b14, balance.clim_balance(base))


def in_season(index: pd.DatetimeIndex) -> np.ndarray:
    md = index.month * 100 + index.day
    (m1, d1), (m2, d2) = config.SEASON_START, config.SEASON_END
    return np.asarray((md >= m1 * 100 + d1) & (md <= m2 * 100 + d2))


def find_onsets(pct: pd.Series, min_dry: int) -> list[int]:
    """Positions of dry-spell onsets (same rule as drought.detect_onset) with a cool-down between events."""
    v = pct.to_numpy()
    low = v <= config.FD_LOW_PCT
    prev_max = pct.rolling(config.FD_WINDOW_DAYS, min_periods=1).max().shift(1).to_numpy()
    # the percentile stays low for `min_dry` days (or to the end of the series)
    stays = pd.Series(low[::-1].astype(float)).rolling(min_dry, min_periods=1).min().to_numpy()[::-1] == 1.0
    out, block_until = [], -1
    for i in np.flatnonzero(low & (prev_max >= config.FD_HIGH_PCT) & stays):
        if i > block_until:
            out.append(int(i))
            block_until = i + COOLDOWN_DAYS
    return out


def catalog(series: dict, min_dry: int) -> pd.DataFrame:
    rows = []
    for rid, (b14, pct) in series.items():
        v, season = pct.to_numpy(), in_season(pct.index)
        for i in find_onsets(pct, min_dry):
            lo = max(0, i - config.FD_WINDOW_DAYS)
            wet = lo + int(np.argmax(v[lo:i]))
            end = i
            while end + 1 < len(v) and v[end + 1] <= config.FD_LOW_PCT:
                end += 1
            rows.append({"district": rid, "onset": pct.index[i].date().isoformat(), "year": pct.index[i].year,
                         "month": pct.index[i].month, "in_season": bool(season[i]), "days_dry": end - i + 1,
                         "min_pct": round(float(v[i:end + 1].min()), 1),
                         "pct_before": round(float(v[wet]), 1),
                         "drop_mm": round(float(b14.iloc[wet] - b14.iloc[i]), 1)})
    return pd.DataFrame(rows)


def per_season(cat: pd.DataFrame, years: tuple[int, int]) -> float:
    """Dry spells per district per irrigation season in the given years."""
    n = len(cat[cat["in_season"] & cat["year"].between(*years)])
    return n / (len(config.REGIONS) * (years[1] - years[0] + 1))


def seasons_ranking(series: dict) -> pd.DataFrame:
    rows = []
    for rid, (_, pct) in series.items():
        s = pct[in_season(pct.index)]
        g = s.groupby(s.index.year)
        t = pd.DataFrame({"mean_pct": g.mean().round(1), "days_le_20": g.apply(lambda x: int((x <= 20).sum())),
                          "days_le_10": g.apply(lambda x: int((x <= 10).sum()))})
        t["rank_driest"] = t["mean_pct"].rank(method="min").astype(int)
        t.insert(0, "district", rid)
        rows.append(t.rename_axis("year").reset_index())
    return pd.concat(rows, ignore_index=True)


def plots(cat: pd.DataFrame, series: dict, episode: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    season = cat[cat["in_season"]]
    fig, ax = plt.subplots(figsize=(10, 4))
    counts = season.groupby("year").size().reindex(range(config.BASELINE_START, config.BASELINE_END + 1), fill_value=0)
    ax.bar(counts.index, counts.values, color="#d6372b")
    ax.set(title=f"Dry spells in the irrigation season, {len(config.REGIONS)} pilot districts",
           xlabel="Year", ylabel="Dry spells (all districts)")
    fig.tight_layout(); fig.savefig(REPORTS / "events_per_year.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    months = cat.groupby("month").size().reindex(range(1, 13), fill_value=0)
    (m1, _), (m2, _) = config.SEASON_START, config.SEASON_END
    ax.bar(months.index, months.values, color=["#d6372b" if m1 <= m <= m2 else "#bbbbbb" for m in months.index])
    ax.set(title="Dry-spell onsets by month, 1991-2025 (red = irrigation season)", xlabel="Month", ylabel="Onsets",
           xticks=range(1, 13))
    fig.tight_layout(); fig.savefig(REPORTS / "events_by_month.png", dpi=150); plt.close(fig)

    rid, year = episode["district"], int(episode["onset"][:4])
    pct = series[rid][1]
    s = pct[f"{year}-03-01":f"{year}-10-31"]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(s.index, s.values, color="#222222", lw=2)
    ax.axhspan(0, config.FD_LOW_PCT, color="#d6372b", alpha=0.12)
    ax.axhline(config.FD_HIGH_PCT, color="gray", ls="--", lw=1)
    for onset in pd.to_datetime(cat[cat["district"] == rid]["onset"]):
        if s.index[0] <= onset <= s.index[-1]:
            ax.axvline(onset, color="#d6372b", lw=1.5)
    ax.axvline(pd.Timestamp(episode["replay_date"]), color="#1f77b4", lw=1.5, ls=":")
    name = next(r["en"] for r in config.REGIONS if r["id"] == rid)
    ax.set(title=f"{name}, {year}: 14-day water-balance percentile vs 1991-2020\n"
                 "red = dry-spell onsets, dotted blue = where the replay starts",
           ylabel="Percentile (low = dry)", ylim=(0, 100), xlim=(s.index[0], s.index[-1]))
    fig.tight_layout(); fig.savefig(REPORTS / f"case_{rid}_{year}.png", dpi=150); plt.close(fig)


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    series = {r["id"]: district_series(r) for r in config.REGIONS}

    tried = {d: round(per_season(catalog(series, d), TRAIN), 2) for d in MIN_DRY_GRID}
    in_target = [d for d in MIN_DRY_GRID if TARGET[0] <= tried[d] <= TARGET[1]]
    chosen = in_target[0] if in_target else min(MIN_DRY_GRID, key=lambda d: abs(tried[d] - np.mean(TARGET)))
    cat = catalog(series, chosen).sort_values(["onset", "district"]).reset_index(drop=True)
    cat.to_csv(REPORTS / "dry_spell_catalog.csv", index=False)

    ranking = seasons_ranking(series)
    ranking.to_csv(REPORTS / "seasons_ranking.csv", index=False)

    recent = cat[cat["in_season"] & cat["year"].between(*REPLAY_YEARS)]
    top = recent.sort_values(["days_dry", "drop_mm"], ascending=False).iloc[0]
    rejected = recent.sort_values("drop_mm", ascending=False).iloc[0]
    episode = {"district": top["district"], "onset": top["onset"], "days_dry": int(top["days_dry"]),
               "min_pct": float(top["min_pct"]), "drop_mm": float(top["drop_mm"]),
               "replay_date": (pd.Timestamp(top["onset"]) - pd.Timedelta(REPLAY_LEAD_DAYS, "D")).date().isoformat(),
               "rule": f"longest in-season dry spell of {REPLAY_YEARS[0]}-{REPLAY_YEARS[1]}",
               "rejected_first_rule": {"rule": "largest drop_mm", "district": rejected["district"],
                                       "onset": rejected["onset"], "drop_mm": float(rejected["drop_mm"]),
                                       "why": "the drop follows a very wet spell (percentile before = "
                                              f"{rejected['pct_before']}), so it measures rain ending, not drought"}}

    season_pct = pd.concat([pct[in_season(pct.index)] for _, pct in series.values()])
    share = lambda years, t: round(100 * float((season_pct[season_pct.index.year.isin(range(years[0], years[1] + 1))] <= t).mean()), 1)
    summary = {
        "rule": {"high_pct": config.FD_HIGH_PCT, "low_pct": config.FD_LOW_PCT, "window_days": config.FD_WINDOW_DAYS,
                 "cooldown_days": COOLDOWN_DAYS, "season": [list(config.SEASON_START), list(config.SEASON_END)]},
        "target_per_district_season": list(TARGET),
        "min_dry_days_tried_on_1991_2014": tried,
        "min_dry_days_chosen": chosen,
        "config_value_now": config.FD_MIN_DRY_DAYS,
        "dry_spells_per_district_season": {"1991-2014": round(per_season(cat, TRAIN), 2),
                                           "2015-2025": round(per_season(cat, CHECK), 2)},
        "dry_spells_per_district_season_by_period": {f"{a}-{b}": round(per_season(cat, (a, b)), 2)
                                                     for a, b in ((1991, 2000), (2001, 2010), (2011, 2020), (2021, 2025))},
        "dry_spells_total": {"all_months": int(len(cat)), "in_season": int(cat["in_season"].sum())},
        "median_drop_mm_in_season": float(cat[cat["in_season"]]["drop_mm"].median()),
        "share_of_season_days_pct": {"le_10": {"1991-2020": share((1991, 2020), 10), "2021-2025": share((2021, 2025), 10)},
                                     "le_20": {"1991-2020": share((1991, 2020), 20), "2021-2025": share((2021, 2025), 20)}},
        "driest_season_by_district": {rid: int(g.sort_values("mean_pct").iloc[0]["year"])
                                      for rid, g in ranking.groupby("district")},
        "rank_of_2021_by_district": {rid: int(g[g["year"] == 2021]["rank_driest"].iloc[0])
                                     for rid, g in ranking.groupby("district")},
        "replay_episode": episode,
    }
    (REPORTS / "calibration.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    plots(cat, series, episode)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if chosen != config.FD_MIN_DRY_DAYS:
        print(f"\nNOTE: config.FD_MIN_DRY_DAYS is {config.FD_MIN_DRY_DAYS}; calibration suggests {chosen}.")
    if episode["replay_date"] != config.REPLAY_DEFAULT_DATE:
        print(f"NOTE: config.REPLAY_DEFAULT_DATE is {config.REPLAY_DEFAULT_DATE}; the rule picks {episode['replay_date']}.")


if __name__ == "__main__":
    main()
