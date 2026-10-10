import numpy as np
import pandas as pd
import pytest

from aquatwin import advice, balance, config, data, drought, nearest_region
from conftest import N_MEMBERS, synthetic_region


def _pct(values, start="2026-06-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values)), dtype=float)


def test_percentiles_monotonic():
    clim = balance.clim_balance(synthetic_region()["baseline"])
    s = pd.Series([-80.0, -70.0, -60.0], index=pd.to_datetime(["2026-07-01"] * 3))
    p = drought.percentiles(s, clim).values
    assert p[0] < 5 and 40 < p[1] < 60 and p[2] > 95


def test_percentiles_frame_matches_series():
    clim = balance.clim_balance(synthetic_region()["baseline"])
    idx = pd.date_range("2026-07-01", periods=3)
    df = pd.DataFrame({"a": [-80.0, -70.0, -60.0], "b": [-60.0, np.nan, -80.0]}, index=idx)
    out = drought.percentiles(df, clim)
    assert np.allclose(out["a"], drought.percentiles(df["a"], clim))
    assert np.isnan(out.loc[idx[1], "b"])


def test_flash_drought_detected():
    onset = drought.detect_onset(_pct([60] * 20 + [45, 30, 15, 10, 8, 8, 8, 8]), start_idx=20)
    assert onset == pd.Timestamp("2026-06-23")


def test_slow_drying_is_not_flash():
    slow = list(np.linspace(60, 41, 10)) + list(np.linspace(39, 21, 25)) + [15] * 10
    assert drought.detect_onset(_pct(slow)) is None


def test_short_dip_is_not_a_dry_spell():
    dip = [60] * 20 + [15, 15, 50, 50, 50, 50, 50, 50]
    assert drought.detect_onset(_pct(dip), start_idx=20) is None


def test_dry_spell_at_the_end_of_the_forecast_counts():
    assert drought.detect_onset(_pct([60] * 20 + [15, 12]), start_idx=20) == pd.Timestamp("2026-06-21")


def test_ongoing():
    a = drought.assess(synthetic_region(recent_et0=6.0))
    assert a.level == "ongoing" and a.current_pct <= config.ONGOING_PCT


def test_member_paths_shape():
    region = synthetic_region(dry_members=10)
    paths = balance.member_paths(region["recent"], region["fc_et0"], region["fc_precip"])
    assert paths.shape == (44, N_MEMBERS) and not paths.isna().any().any()
    # the first forecast day sums 13 observed days and one forecast day
    assert paths.iloc[0]["m00"] == pytest.approx(-(13 * 5.0 + 6.0))
    assert paths.iloc[0]["m50"] == pytest.approx(-14 * 5.0)
    assert paths.iloc[-1]["m00"] == pytest.approx(-14 * 6.0)


@pytest.mark.parametrize("dry, level", [(0, "low"), (13, "moderate"), (26, "high"), (51, "high")])
def test_probability_levels(dry, level):
    a = drought.assess(synthetic_region(dry_members=dry))
    assert (a.n_dry, a.n_members, a.level) == (dry, N_MEMBERS, level)
    assert a.p_dry == pytest.approx(dry / N_MEMBERS)
    assert (a.onset_date is not None) == (dry >= 13)
    if dry >= 13:
        assert 0 < a.days_to_onset <= config.FD_WINDOW_DAYS


def test_timeline_has_observed_and_forecast_corridor():
    tl = drought.assess(synthetic_region(dry_members=26)).timeline
    fc = tl[tl["kind"] == "forecast"]
    assert len(tl[tl["kind"] == "observed"]) == config.RECENT_DAYS - config.BALANCE_DAYS + 1
    assert len(fc) == 44 and (fc["p10"] <= fc["percentile"]).all() and (fc["percentile"] <= fc["p90"]).all()


def test_message_in_season_has_actions_and_probability():
    region = config.REGIONS[0]
    a = drought.assess(synthetic_region(dry_members=26))
    for lang in ("en", "ru", "kk"):
        m = advice.message(a, region, lang)
        assert region[lang] in m and advice.LABELS[lang]["todo"] in m
        assert "26" in m and "51" in m and advice.ACTIONS[lang]["high"][0] in m
    assert "26 из 51 сценария ECMWF" in advice.message(a, region, "ru")


def test_offseason_message():
    region = config.REGIONS[0]
    a = drought.assess(synthetic_region(dry_members=26, as_of="2026-11-10"))
    assert not a.in_season
    for lang in ("en", "ru", "kk"):
        m = advice.message(a, region, lang)
        assert advice.LABELS[lang]["todo"] not in m
        assert advice.LABELS[lang]["offseason"].format(season=advice.season_label()) in m


def test_surplus_wording_when_rain_exceeds_evaporation():
    region = synthetic_region()
    region["recent"] = region["recent"].assign(precip=8.0)
    a = drought.assess(region)
    m = advice.message(a, config.REGIONS[0], "ru")
    assert a.deficit_mm < 0 and "Избыток влаги" in m and "Дефицит" not in m


def test_messages_are_safe_for_telegram_markdown():
    for dry in (0, 13, 26):
        for as_of in ("2026-07-01", "2026-11-10"):
            a = drought.assess(synthetic_region(dry_members=dry, as_of=as_of))
            for region in config.REGIONS:
                for lang in ("en", "ru", "kk"):
                    m = advice.message(a, region, lang)
                    assert m.count("*") % 2 == 0 and not set("_`[") & set(m)


def test_replay_all_regions_and_messages():
    """Replay needs no network: it reads the baseline files shipped with the repository."""
    for region in config.REGIONS:
        a = drought.assess(data.load_region(region, mode="replay", replay_date="2021-06-15"))
        assert a.level in drought.LEVELS and a.source == "replay" and a.n_members == 1
        assert a.as_of == pd.Timestamp("2021-06-15") and 0 <= a.current_pct <= 100
        for lang in ("en", "ru", "kk"):
            m = advice.message(a, region, lang)
            assert region[lang] in m and "15.06.2021" in m
            assert "ECMWF" not in m  # one real path is not a probability


def test_replay_date_outside_baseline_is_rejected():
    with pytest.raises(ValueError):
        data.load_region(config.REGIONS[0], mode="replay", replay_date="2026-01-01")


def test_nearest_region():
    r, km = nearest_region(40.7, 68.5)
    assert r["id"] == "maktaaral" and km < 20
