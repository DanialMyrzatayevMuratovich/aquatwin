import datetime as dt

import pandas as pd
import pytest

from aquatwin import config, data, drought

MAKTAARAL = config.REGIONS[0]


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


def test_utc_date(monkeypatch):
    """00:30 on 11 October in Kazakhstan (UTC+5) is still 10 October for the API."""
    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            moment = dt.datetime(2026, 10, 10, 19, 30, tzinfo=dt.timezone.utc)
            return moment.astimezone(tz) if tz else moment.astimezone(dt.timezone(dt.timedelta(hours=5)))

    monkeypatch.setattr(data.dt, "datetime", Clock)
    assert Clock.now().date() == dt.date(2026, 10, 11)
    assert data.utc_today() == dt.date(2026, 10, 10)


def test_requests_use_the_utc_date(monkeypatch):
    seen = []

    def fake_get(url, params):
        seen.append(params)
        raise data.DataError("stop after the first request")

    monkeypatch.setattr(data, "utc_today", lambda: dt.date(2026, 10, 10))
    monkeypatch.setattr(data, "_get", fake_get)
    assert data.load_region(MAKTAARAL)["source"] == "replay"
    archive = [p for p in seen if "end_date" in p]
    assert archive and all(p["end_date"] == "2026-10-09" for p in archive)


def test_error_reason_kept(monkeypatch):
    calls = []

    def get(url, params, timeout):
        calls.append(url)
        return FakeResponse(400, {"error": True, "reason": "Parameter 'end_date' is out of allowed range"})

    monkeypatch.setattr(data.requests, "get", get)
    with pytest.raises(data.DataError, match="end_date"):
        data._get(data.ARCHIVE_URL, {})
    assert len(calls) == 1  # a client error is not retried


def test_retry_on_rate_limit(monkeypatch):
    answers = [FakeResponse(429, {"error": True, "reason": "limit"}), FakeResponse(503, {}),
               FakeResponse(200, {"daily": {"time": []}})]
    monkeypatch.setattr(data.requests, "get", lambda url, params, timeout: answers.pop(0))
    assert data._get(data.ARCHIVE_URL, {}) == {"daily": {"time": []}}
    assert not answers


def test_gives_up_after_three_attempts(monkeypatch):
    calls = []

    def get(url, params, timeout):
        calls.append(url)
        raise data.requests.Timeout("slow")

    monkeypatch.setattr(data.requests, "get", get)
    with pytest.raises(data.DataError, match="Timeout"):
        data._get(data.ARCHIVE_URL, {})
    assert len(calls) == 3


def _obs(days, et0, end="2026-10-09"):
    idx = pd.date_range(end=end, periods=days, freq="D")
    return pd.DataFrame({"et0": float(et0), "precip": 0.0}, index=idx)


def test_recent_merge_and_scale():
    era = _obs(60, 5.0, end="2026-10-04")   # ERA5 lags by several days
    ifs = _obs(65, 5.5)                     # IFS reaches yesterday and runs 10 % high
    merged, k = data.merge_recent(era, ifs)
    assert k == pytest.approx(5.0 / 5.5)
    assert len(merged) == 65 and merged.index[-1] == pd.Timestamp("2026-10-09")
    assert merged["et0"].iloc[:60].eq(5.0).all()                     # ERA5 has priority
    assert merged["et0"].iloc[-5:].tolist() == pytest.approx([5.0] * 5)  # the IFS tail is scaled


def test_scale_is_clipped_and_needs_enough_days():
    _, k = data.merge_recent(_obs(60, 5.0, end="2026-10-04"), _obs(65, 10.0))
    assert k == config.SCALE_CLIP[0]
    _, k = data.merge_recent(_obs(10, 5.0, end="2026-10-04"), _obs(65, 10.0))
    assert k == 1.0


def test_gap_in_observations_is_an_error():
    ifs = _obs(65, 5.0).drop(pd.date_range("2026-09-01", periods=10))
    with pytest.raises(data.DataError, match="gap"):
        data.merge_recent(ifs.iloc[:0], ifs)


def test_real_api_fixture(live_api):
    """Recorded Open-Meteo responses are parsed and give a full assessment."""
    region = data.load_region(MAKTAARAL, today=live_api["today"])
    assert region["source"] == "live"
    assert region["as_of"] == pd.Timestamp(live_api["today"]) - dt.timedelta(days=1)
    assert region["fc_et0"].shape[1] == 51 and len(region["fc_et0"]) >= 40
    assert region["fc_et0"].index[0] == region["as_of"] + dt.timedelta(days=1)
    assert not region["fc_et0"].isna().any().any() and not region["recent"].isna().any().any()
    assert all(config.SCALE_CLIP[0] <= k <= config.SCALE_CLIP[1] for k in region["scales"].values())

    a = drought.assess(region)
    assert a.level in drought.LEVELS and a.n_members == 51 and 0 <= a.current_pct <= 100
    assert a.ai is not None and a.ai["n_members"] == 51 and len(a.ai["timeline"]) >= 10
    fc = a.timeline[a.timeline["kind"] == "forecast"]
    assert fc["percentile"].between(0, 100).all()


def test_ai_ensemble_optional(live_api):
    with_ai = drought.assess(data.load_region(MAKTAARAL, today=live_api["today"]))
    live_api["fail_models"].add("ecmwf_aifs025")
    region = data.load_region(MAKTAARAL, today=live_api["today"])
    without_ai = drought.assess(region)
    assert region["source"] == "live" and without_ai.ai is None
    assert (without_ai.level, without_ai.n_dry) == (with_ai.level, with_ai.n_dry)


def test_snapshot_roundtrip_and_fallback(live_api, monkeypatch):
    live = data.load_region(MAKTAARAL, today=live_api["today"])
    live_api["fail_models"].add("ecmwf_ec46")           # the forecast source goes down
    snap = data.load_region(MAKTAARAL, today=live_api["today"])
    assert snap["source"] == "snapshot" and snap["as_of"] == live["as_of"]
    for key in ("recent", "fc_et0", "fc_precip", "ai_et0", "ai_precip"):
        pd.testing.assert_frame_equal(snap[key], live[key], check_freq=False)
    assert drought.assess(snap).level == drought.assess(live).level

    monkeypatch.setattr(config, "SNAPSHOT_MAX_AGE_H", -1)  # the snapshot is now too old
    assert data.load_region(MAKTAARAL, today=live_api["today"])["source"] == "replay"


def test_live_falls_back_to_replay_without_network():
    region = data.load_region(MAKTAARAL)
    assert region["source"] == "replay" and region["as_of"] == pd.Timestamp(config.REPLAY_DEFAULT_DATE)
    assert drought.assess(region).level in drought.LEVELS
