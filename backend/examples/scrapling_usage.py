"""
StealthyFetcher + adaptive selectors (scrapling).

Also available: Fetcher, AsyncFetcher, DynamicFetcher — import from
``scrapling.fetchers`` when you need plain HTTP, async, or dynamic loads.

StealthyFetcher needs extra packages beyond ``pip install scrapling``:
curl_cffi, patchright (run ``patchright install chromium``), msgspec,
browserforge, playwright (optional; patchright drives the browser).

Run:
  backend\\venv\\Scripts\\python.exe backend/examples/scrapling_usage.py
"""

from scrapling.fetchers import StealthyFetcher

StealthyFetcher.adaptive = True

p = StealthyFetcher.fetch(
    "https://example.com",
    headless=True,
    network_idle=True,
)

# Persist selector hints so structure drift is easier to recover from
products = p.css(".product", auto_save=True)

# If the site’s DOM changes later, adaptive matching can still find nodes
products = p.css(".product", adaptive=True)

if __name__ == "__main__":
    print(products)
