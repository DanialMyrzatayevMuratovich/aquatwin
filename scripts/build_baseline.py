"""Download the ERA5 baseline (daily ET0 and precipitation, 1991-2025) for every pilot district.

    python scripts/build_baseline.py            # only missing districts
    python scripts/build_baseline.py --force    # re-download everything

The files in data/baseline/ are committed, so servers never make these heavy requests.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from aquatwin import config, data  # noqa: E402

PAUSE_S = 15  # keeps 8 long requests under Open-Meteo's per-minute limit


def main() -> None:
    force = "--force" in sys.argv
    data.BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    fetched = 0
    for region in config.REGIONS:
        path = data.baseline_path(region["id"])
        if path.exists() and not force:
            print(f"{region['id']}: exists, skipped")
            continue
        if fetched:
            time.sleep(PAUSE_S)
        df = data.fetch_baseline(region["lat"], region["lon"])
        if df.isna().any().any():
            raise SystemExit(f"{region['id']}: baseline has gaps, not saved")
        df.to_csv(path, index_label="date", float_format="%.2f")
        fetched += 1
        print(f"{region['id']}: {len(df)} days {df.index[0].date()}..{df.index[-1].date()}, "
              f"{path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
