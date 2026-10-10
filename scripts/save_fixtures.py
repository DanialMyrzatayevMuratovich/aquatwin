"""Record real API responses for the offline test in tests/test_live_fixture.py.

    python scripts/save_fixtures.py            # district: maktaaral

Re-run it when Open-Meteo changes a response format; the test then checks the new shape.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aquatwin import config, data  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "live_maktaaral.json"


def main() -> None:
    region = next(r for r in config.REGIONS if r["id"] == "maktaaral")
    today = data.utc_today()
    calls = []
    original = data._get

    def recording(url, params):
        js = original(url, params)
        calls.append({"url": url, "models": params.get("models"), "response": js})
        return js

    data._get = recording
    result = data.live_region(region, today)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"today": today.isoformat(), "calls": calls}))
    print(f"{len(calls)} responses, as_of {result['as_of'].date()}, {OUT.stat().st_size // 1024} KB -> {OUT}")


if __name__ == "__main__":
    main()
