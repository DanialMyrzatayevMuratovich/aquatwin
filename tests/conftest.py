import datetime as dt
import json
import pathlib

import numpy as np
import pandas as pd
import pytest

from aquatwin import config, data

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "live_maktaaral.json"
N_MEMBERS = 51


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """No test touches the network or the project's snapshot folder."""
    def refuse(*args, **kwargs):
        raise data.requests.ConnectionError("network is blocked in tests")
    monkeypatch.setattr(data.requests, "get", refuse)
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data.time, "sleep", lambda s: None)


@pytest.fixture
def live_api(monkeypatch):
    """Answers `data._get` from responses recorded by scripts/save_fixtures.py."""
    recorded = json.loads(FIXTURE.read_text())
    by_key = {(c["url"], c["models"]): c["response"] for c in recorded["calls"]}
    state = {"fail_models": set()}

    def fake_get(url, params):
        if params.get("models") in state["fail_models"]:
            raise data.DataError("simulated outage")
        return by_key[(url, params.get("models"))]

    monkeypatch.setattr(data, "_get", fake_get)
    state["today"] = dt.date.fromisoformat(recorded["today"])
    return state


def synthetic_region(recent_et0: float = 5.0, dry_members: int = 0, as_of: str = "2026-07-01",
                     dry_et0: float = 6.0) -> dict:
    """A rainless climate with ET0 ~ N(5, 0.5): a 14-day balance of -70 mm sits at the median.

    Scenarios with ET0 = `dry_et0` fall to the bottom of the distribution within days.
    """
    rng = np.random.default_rng(0)
    idx = pd.date_range("1991-01-01", "2020-12-31", freq="D")
    baseline = pd.DataFrame({"et0": 5.0 + rng.normal(0, 0.5, len(idx)), "precip": 0.0}, index=idx)
    end = pd.Timestamp(as_of)
    rec_idx = pd.date_range(end=end, periods=config.RECENT_DAYS, freq="D")
    recent = pd.DataFrame({"et0": recent_et0, "precip": 0.0}, index=rec_idx)
    fc_idx = pd.date_range(end + dt.timedelta(days=1), periods=44, freq="D")
    cols = [f"m{i:02d}" for i in range(N_MEMBERS)]
    fc_et0 = pd.DataFrame(5.0, index=fc_idx, columns=cols)
    fc_et0.iloc[:, :dry_members] = dry_et0
    return {"baseline": baseline, "recent": recent, "fc_et0": fc_et0, "fc_precip": fc_et0 * 0.0,
            "ai_et0": None, "ai_precip": None, "source": "live", "as_of": end, "scales": {}}
