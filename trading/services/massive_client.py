"""Client for the Massive (formerly Polygon.io) market data REST API.

Designed so a bad response or a slow API never takes the app down:
- every request has a timeout
- calls are throttled to stay under the plan's per-minute limit
- 429 / 5xx responses are retried with exponential backoff
- failures surface as MassiveError, and update_prices() isolates them per stock
- only missing days are fetched, and rows are bulk-inserted
"""

import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import requests
from decouple import config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://api.massive.com"


class MassiveError(Exception):
    """Raised when Massive returns an error or unusable data."""


class RateLimiter:
    """Spaces calls evenly so we never exceed `calls_per_minute`."""

    def __init__(self, calls_per_minute):
        self.interval = 60.0 / calls_per_minute if calls_per_minute > 0 else 0
        self._next_allowed = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.monotonic()
            delay = self._next_allowed - now
            if delay > 0:
                time.sleep(delay)
            self._next_allowed = max(now, self._next_allowed) + self.interval


class MassiveClient:
    def __init__(self, api_key=None, calls_per_minute=None, timeout=15, max_retries=3):
        self.api_key = api_key or config("MASSIVE_DEFAULT_KEY", default=None)
        if not self.api_key:
            raise MassiveError("MASSIVE_DEFAULT_KEY is not set in .env")

        # Free plan allows 5 calls/minute; raise MASSIVE_CALLS_PER_MINUTE on a paid plan.
        if calls_per_minute is None:
            calls_per_minute = config("MASSIVE_CALLS_PER_MINUTE", default=5, cast=int)
        self.rate_limiter = RateLimiter(calls_per_minute)
        self.timeout = timeout

        retry = Retry(
            total=max_retries,
            backoff_factor=2,  # 2s, 4s, 8s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _get(self, url, params=None):
        self.rate_limiter.wait()
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise MassiveError(f"Request to Massive failed: {exc}") from exc

        if response.status_code != 200:
            raise MassiveError(f"Massive returned HTTP {response.status_code}: {response.text[:200]}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise MassiveError("Massive returned invalid JSON") from exc

        if payload.get("status") not in ("OK", "DELAYED"):
            raise MassiveError(f"Massive error: {payload.get('error') or payload.get('message') or payload}")
        return payload

    def get_daily_bars(self, symbol, start, end, adjusted=True):
        """Return daily OHLCV bars for `symbol` between `start` and `end` (inclusive), oldest first."""
        url = f"{BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/1/day/{start:%Y-%m-%d}/{end:%Y-%m-%d}"
        params = {"adjusted": str(adjusted).lower(), "sort": "asc", "limit": 50000}

        bars = []
        while url:
            payload = self._get(url, params)
            for row in payload.get("results") or []:
                try:
                    bars.append({
                        "date": datetime.fromtimestamp(row["t"] / 1000, tz=timezone.utc).date(),
                        "open": Decimal(str(row["o"])),
                        "high": Decimal(str(row["h"])),
                        "low": Decimal(str(row["l"])),
                        "close": Decimal(str(row["c"])),
                        "volume": int(row["v"]),
                    })
                except (KeyError, TypeError, ValueError):
                    logger.warning("Skipping malformed bar for %s: %s", symbol, row)
            # next_url already carries the query params
            url = payload.get("next_url")
            params = None
        return bars


def update_prices(stocks=None, lookback_days=400, client=None):
    """Fetch and store missing daily prices for each active stock.

    One failing ticker is logged and skipped, so it can't stop the rest.
    Returns {"saved": rows_inserted, "failed": [symbols]}.
    """
    from trading.models import PriceData, Stock

    client = client or MassiveClient()
    if stocks is None:
        stocks = Stock.objects.filter(is_active=True)

    today = date.today()
    saved, failed = 0, []

    for stock in stocks:
        last = PriceData.objects.filter(stock=stock).order_by("-date").values_list("date", flat=True).first()
        start = last + timedelta(days=1) if last else today - timedelta(days=lookback_days)
        if start > today:
            continue

        try:
            bars = client.get_daily_bars(stock.symbol, start, today)
        except MassiveError as exc:
            logger.error("Could not fetch prices for %s: %s", stock.symbol, exc)
            failed.append(stock.symbol)
            continue

        created = PriceData.objects.bulk_create(
            [PriceData(stock=stock, **bar) for bar in bars],
            ignore_conflicts=True,
        )
        saved += len(created)
        logger.info("%s: stored %d bars", stock.symbol, len(bars))

    return {"saved": saved, "failed": failed}
