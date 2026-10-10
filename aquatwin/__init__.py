"""AquaTwin — flash-drought early warning for farmers in arid regions."""
import math

from .config import REGIONS


def nearest_region(lat: float, lon: float) -> tuple[dict, float]:
    """Closest pilot district and distance in km."""
    def dist(r):
        p1, p2 = math.radians(lat), math.radians(r["lat"])
        dphi, dl = p2 - p1, math.radians(r["lon"] - lon)
        h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 6371 * 2 * math.asin(math.sqrt(h))
    best = min(REGIONS, key=dist)
    return best, dist(best)
