import threading, time
import requests

class RateLimitedSession:
    """requests.Session that spaces calls out and retries 429s / network errors."""
    def __init__(self, rps, name):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "live-arb-scanner (paper trading research)"
        self.gap = 1.0 / rps; self.next = 0.0; self.lock = threading.Lock(); self.name = name

    def get(self, url, params=None, tries=5):
        for attempt in range(tries):
            with self.lock:
                now = time.time(); t = max(now, self.next); self.next = t + self.gap
            time.sleep(max(0.0, t - now))
            try:
                r = self.s.get(url, params=params, timeout=15)
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(1.5 * (attempt + 1)); continue
                r.raise_for_status()
                return r.json()
            except requests.RequestException:
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"{self.name}: failed after {tries} tries: {url}")
