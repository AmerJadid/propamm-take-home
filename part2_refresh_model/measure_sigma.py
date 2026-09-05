"""Measure BNBUSDT volatility from Binance's public price history.

Run: uv run python part2_refresh_model/measure_sigma.py

For each bar size, pulls the most recent 1,000 closes, takes the standard
deviation of log close-to-close returns and divides by sqrt(bar seconds) to
express it as a move over one second. This is the SIGMA input to
refresh_model.py; it is the one number the brief does not give. Needs network
access; nothing else in the repo does.
"""

import json
import math
import statistics
import urllib.request
from itertools import pairwise

URL = "https://api.binance.com/api/v3/klines?symbol=BNBUSDT&interval={interval}&limit=1000"
BARS = {"1s": 1, "1m": 60, "5m": 300, "1h": 3600, "1d": 86_400}
YEAR = 365.25 * 86_400


def sigma_per_sqrt_second(interval: str, seconds: int) -> tuple[float, float]:
    """Returns (sigma over one second as a fraction, span of the sample in hours)."""
    with urllib.request.urlopen(URL.format(interval=interval), timeout=20) as response:
        rows = json.load(response)
    if not isinstance(rows, list) or len(rows) < 2:
        # Binance returns a {"code": ..., "msg": ...} object on errors
        raise RuntimeError(f"unexpected response from Binance: {str(rows)[:200]}")
    closes = [float(row[4]) for row in rows]
    log_returns = [math.log(b / a) for a, b in pairwise(closes)]
    span_hours = (rows[-1][0] - rows[0][0]) / 1000 / 3600
    return statistics.pstdev(log_returns) / math.sqrt(seconds), span_hours


def main() -> None:
    print(f"{'bars':>5}{'sample':>14}{'sigma / 1 s':>14}{'annualised':>12}")
    for interval, seconds in BARS.items():
        sigma, hours = sigma_per_sqrt_second(interval, seconds)
        span = f"{hours:,.1f} h" if hours < 72 else f"{hours / 24:,.0f} d"
        print(f"{interval:>5}{span:>14}{sigma * 1e4:>10.2f} bps{sigma * math.sqrt(YEAR):>11.0%}")
    print("\nThe 1 s row covers only ~17 minutes and is inflated by bid-ask bounce;")
    print("refresh_model.py uses 0.80 bps, the middle of the longer windows.")


if __name__ == "__main__":
    main()
