"""Authenticated async Playwright scraper for Collectr graded Pokemon prices.

Run from backend:
    venv\\Scripts\\python.exe save_collectr_login.py
    venv\\Scripts\\python.exe scrapers\\collectr.py 155-XY-P
"""

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from auth.collectr_auth import CollectrAuthError, require_collectr_storage_state_path


logger = logging.getLogger(__name__)

COLLECTR_URL = os.getenv("COLLECTR_URL", "https://app.getcollectr.com")
DEFAULT_CARD_NUMBER = os.getenv("COLLECTR_CARD_NUMBER", "155-XY-P")
DEBUG_DIR = Path(__file__).resolve().parent.parent / "debug"

COLLECTR_SEARCH_OPTION_NAME = os.getenv(
    "COLLECTR_SEARCH_OPTION_NAME",
    "Hoopa (JP) Hoopa (JP) XY",
)
RESULT_SELECTORS = (
    "[data-testid*='card' i]",
    "[data-testid*='result' i]",
    "[class*='result' i]",
    "[class*='card' i]",
    "main article",
    "main li",
    "main a[href]",
)
TITLE_SELECTORS = (
    "[data-testid*='title' i]",
    ".card-title",
    "[class*='title' i]",
    "h1",
    "h2",
    "h3",
    "a[href]",
)
PRICE_SELECTORS = (
    "[data-testid*='price' i]",
    ".price",
    "[class*='price' i]",
    "[class*='value' i]",
)
GRADE_SELECTORS = (
    "[data-testid*='grade' i]",
    ".grade",
    "[class*='grade' i]",
    "[class*='psa' i]",
    "[class*='ace' i]",
)

GRADED_PATTERN = re.compile(r"\b(PSA|ACE|BGS|CGC|SGC)\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)
COMPANY_PATTERN = re.compile(r"\b(PSA|ACE|BGS|CGC|SGC)\b", re.IGNORECASE)
LOGIN_URL_PATTERN = re.compile(r"/(login|signin|sign-in|auth)\b", re.IGNORECASE)


class CollectrScrapeError(RuntimeError):
    """Raised when Collectr scraping fails after authentication is available."""

    def __init__(self, message, *, current_url=None):
        super().__init__(message)
        self.current_url = current_url


class CollectrUnavailableError(CollectrScrapeError):
    """Raised when Collectr is serving an outage or maintenance page."""


def _clean_text(value):
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value)).strip() or None


def _normalize_card_number(value):
    return str(value or "").strip().replace("/", "-").upper()


def _parse_price(value):
    text = _clean_text(value)
    if not text:
        return None, None

    currency = "USD"
    if "JPY" in text.upper() or "¥" in text:
        currency = "JPY"
    elif "EUR" in text.upper() or "€" in text:
        currency = "EUR"
    elif "GBP" in text.upper() or "£" in text:
        currency = "GBP"

    match = re.search(r"(\d+(?:[,\d]*)(?:\.\d+)?)", text)
    if not match:
        return None, currency

    number = match.group(1).replace(",", "")
    try:
        if currency == "USD":
            dollars, _, cents = number.partition(".")
            return int(dollars) * 100 + int((cents + "00")[:2]), currency
        return int(float(number)), currency
    except ValueError:
        logger.warning("Unable to parse Collectr price: %r", value)
        return None, currency


def _parse_grade(value):
    text = _clean_text(value)
    if not text:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None

    grade = float(match.group(1))
    return int(grade) if grade.is_integer() else grade


def _parse_grading(title, grade_text):
    combined = " ".join(filter(None, [title, grade_text]))
    graded_match = GRADED_PATTERN.search(combined)
    if graded_match:
        return graded_match.group(1).upper(), _parse_grade(graded_match.group(2))

    company_match = COMPANY_PATTERN.search(combined)
    return company_match.group(1).upper() if company_match else None, _parse_grade(grade_text)


async def _safe_networkidle(page, timeout=15_000):
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        logger.info("Collectr page did not reach networkidle within %sms; continuing", timeout)


async def _assert_logged_in(page):
    current_url = page.url
    if LOGIN_URL_PATTERN.search(current_url):
        raise CollectrAuthError(
            "Collectr session expired: redirected to login page. "
            "Run `venv\\Scripts\\python.exe save_collectr_login.py` from the backend folder to refresh it."
        )

    body_text = ""
    try:
        body_text = (await page.locator("body").inner_text(timeout=3_000)).lower()
    except Exception:
        logger.debug("Unable to inspect Collectr page body for login state", exc_info=True)

    login_markers = ("log in", "sign in", "continue with google")
    strong_login_markers = ("welcome back", "sign in with google", "create account")
    if any(marker in body_text for marker in strong_login_markers):
        raise CollectrAuthError(
            "Collectr session expired: login UI is visible. "
            "Run `venv\\Scripts\\python.exe save_collectr_login.py` from the backend folder to refresh it."
        )
    if any(marker in body_text for marker in login_markers) and not await _has_collectr_search_option(page):
        logger.warning(
            "Collectr page mentions login keywords without an obvious search box yet; continuing scrape url=%s",
            current_url,
        )


async def _page_body_text(page, limit=None):
    try:
        body_text = await page.evaluate(
            """(limit) => {
                const text = document.body && document.body.innerText ? document.body.innerText : "";
                return limit ? text.slice(0, limit) : text;
            }""",
            limit,
        )
        return body_text or ""
    except Exception:
        logger.debug("Collectr unable to read page body text", exc_info=True)
        return ""


async def _assert_collectr_available(page):
    current_url = page.url
    body_text = (await _page_body_text(page)).lower()
    outage_markers = (
        "technical difficulties",
        "service unavailable",
        "temporarily unavailable",
        "temporarily down",
    )

    if "/service-unavailable" in current_url.lower() or any(marker in body_text for marker in outage_markers):
        logger.error("Collectr outage page detected: url=%s", current_url)
        raise CollectrUnavailableError(
            "Collectr is temporarily unavailable",
            current_url=current_url,
        )


async def _first_visible_locator(page, selectors, timeout=3_000):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            logger.info("Collectr selector matched: %s", selector)
            return locator
        except PlaywrightTimeoutError:
            logger.debug("Collectr selector not visible: %s", selector)
    return None


async def _try_open_collectr_search(page):
    """Collectr may hide search behind a button or shortcut until focused."""
    shortcuts = ("Control+k", "Meta+k", "/")
    for key in shortcuts:
        try:
            await page.keyboard.press(key)
            await page.wait_for_timeout(400)
        except Exception:
            logger.debug("Collectr search shortcut %s failed", key, exc_info=True)

    button_selectors = (
        "button[aria-label*='Search' i]",
        "button[title*='Search' i]",
        "[data-testid*='search' i]",
        "svg.lucide-search",
    )
    for selector in button_selectors:
        try:
            button = page.locator(selector).first
            if await button.count() and await button.is_visible():
                await button.click(timeout=3_000)
                await page.wait_for_timeout(500)
                logger.info("Collectr opened search via selector: %s", selector)
                return
        except Exception:
            logger.debug("Collectr search opener not clickable: %s", selector, exc_info=True)


async def _save_collectr_debug_artifacts(page, reason):
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    safe_reason = re.sub(r"[^a-z0-9_-]+", "-", reason.lower()).strip("-") or "collectr"
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base_path = DEBUG_DIR / f"collectr-{safe_reason}-{timestamp}"
    screenshot_path = base_path.with_suffix(".png")
    html_path = base_path.with_suffix(".html")

    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info("Saved Collectr debug screenshot: %s", screenshot_path)
    except Exception:
        logger.debug("Unable to save Collectr debug screenshot", exc_info=True)

    try:
        html_path.write_text(await page.content(), encoding="utf-8")
        logger.info("Saved Collectr debug HTML: %s", html_path)
    except Exception:
        logger.debug("Unable to save Collectr debug HTML", exc_info=True)

    return {
        "screenshot": str(screenshot_path),
        "html": str(html_path),
    }


async def _has_collectr_search_option(page):
    try:
        return await page.get_by_role("option", name=COLLECTR_SEARCH_OPTION_NAME).count() > 0
    except Exception:
        return False


async def _submit_search(page, card_number):
    await _assert_collectr_available(page)
    await _try_open_collectr_search(page)

    logger.info("Collectr typing search query: %s", card_number)
    await page.keyboard.type(card_number, delay=30)
    option = page.get_by_role("option", name=COLLECTR_SEARCH_OPTION_NAME)
    try:
        await option.wait_for(state="visible", timeout=25_000)
        logger.info("Collectr search option found: %s", COLLECTR_SEARCH_OPTION_NAME)
    except PlaywrightTimeoutError:
        await _assert_collectr_available(page)
        snippet = await _page_body_text(page, limit=400)
        await _save_collectr_debug_artifacts(page, "search-option-missing")
        logger.error(
            "Collectr search option missing: url=%s option=%r snippet=%r",
            page.url,
            COLLECTR_SEARCH_OPTION_NAME,
            snippet,
        )
        raise CollectrScrapeError(
            f"Collectr search failed: search option not found: {COLLECTR_SEARCH_OPTION_NAME}",
            current_url=page.url,
        )

    await option.click()
    logger.info("Collectr search option clicked for %s", card_number)
    await _safe_networkidle(page)
    try:
        await page.wait_for_function(
            "() => document.body && /price|PSA|ACE|raw|population|market/i.test(document.body.innerText || '')",
            timeout=15_000,
        )
    except PlaywrightTimeoutError:
        logger.info("Collectr results text did not appear within timeout; continuing extraction")


async def _result_containers(page):
    for selector in RESULT_SELECTORS:
        locator = page.locator(selector)
        count = await locator.count()
        logger.debug("Collectr result selector %s matched %s nodes", selector, count)
        if count:
            logger.info("Collectr results found: selector=%s count=%s", selector, count)
            return selector, locator
    logger.info("Collectr results found: selector=None count=0")
    return None, None


async def _extract_raw_listing(container):
    return await container.evaluate(
        """(node, selectors) => {
            const clean = (value) => value ? value.replace(/\\s+/g, " ").trim() : null;
            const firstText = (selectorList) => {
                for (const selector of selectorList) {
                    const element = node.matches(selector) ? node : node.querySelector(selector);
                    const text = clean(element?.textContent);
                    if (text) return text;
                }
                return null;
            };
            const image = node.querySelector("img");
            const anchor = node.matches("a[href]") ? node : node.querySelector("a[href]");

            return {
                title: firstText(selectors.title),
                price: firstText(selectors.price),
                grade: firstText(selectors.grade),
                allText: clean(node.textContent),
                imageUrl: image?.currentSrc || image?.src || image?.getAttribute("data-src") || null,
                productUrl: anchor?.href || null
            };
        }""",
        {
            "title": TITLE_SELECTORS,
            "price": PRICE_SELECTORS,
            "grade": GRADE_SELECTORS,
        },
    )


def _normalize_listing(raw_listing):
    title = _clean_text(raw_listing.get("title")) or _clean_text(raw_listing.get("allText"))
    price, currency = _parse_price(raw_listing.get("price") or raw_listing.get("allText"))
    grade_text = raw_listing.get("grade") or raw_listing.get("allText")
    grading_company, grade = _parse_grading(title, grade_text)
    image_url = raw_listing.get("imageUrl")
    product_url = raw_listing.get("productUrl")

    return {
        "card_title": title,
        "name": title,
        "grading_company": grading_company,
        "grade": grade,
        "certification_number": None,
        "graded_population": None,
        "population_higher": None,
        "price": price,
        "currency": currency,
        "image_url": urljoin(COLLECTR_URL, image_url) if image_url else None,
        "url": urljoin(COLLECTR_URL, product_url) if product_url else None,
        "product_url": urljoin(COLLECTR_URL, product_url) if product_url else None,
        "listing_type": "graded" if grading_company or grade is not None else "raw",
        "source": "collectr",
    }


def _looks_relevant(listing, card_number):
    if not listing["name"] and listing["price"] is None:
        return False

    haystack = _normalize_card_number(" ".join(str(value or "") for value in listing.values()))
    target = _normalize_card_number(card_number)
    return target in haystack or bool(listing["grading_company"] or listing["grade"] is not None)


async def _extract_collectr_listings(page, card_number, limit):
    selector, containers = await _result_containers(page)
    if containers is None:
        return []

    listings = []
    seen = set()
    count = await containers.count()
    for index in range(min(count, limit)):
        container = containers.nth(index)
        try:
            if not await container.is_visible():
                continue
            raw_listing = await _extract_raw_listing(container)
        except Exception:
            logger.debug("Skipping unreadable Collectr result at index=%s", index, exc_info=True)
            continue

        listing = _normalize_listing(raw_listing)
        if not _looks_relevant(listing, card_number):
            logger.debug("Skipping unrelated Collectr listing: %s", listing)
            continue

        dedupe_key = (
            listing["card_title"],
            listing["grading_company"],
            listing["grade"],
            listing["price"],
            listing["url"],
        )
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        listings.append(listing)

    prices_extracted = sum(1 for listing in listings if listing.get("price") is not None)
    logger.info("Collectr number of prices extracted: %s", prices_extracted)
    return listings


async def _collectr_scrape_async_impl(
    normalized_card_number: str,
    headless: bool,
    limit: int,
    storage_state: str,
):
    """Run Playwright on a fresh asyncio loop (used from a worker thread for Windows/Uvicorn)."""
    browser = None
    page = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            logger.info("Collectr browser launched")

            context = await browser.new_context(
                storage_state=storage_state,
                viewport={"width": 1440, "height": 1000},
            )
            page = await context.new_page()

            # Load the app shell first; direct /search deep links may not mount the search UI reliably.
            home_url = f"{COLLECTR_URL.rstrip('/')}/"
            await page.goto(home_url, wait_until="domcontentloaded", timeout=45_000)
            await _safe_networkidle(page)
            await _assert_collectr_available(page)
            await _assert_logged_in(page)
            logger.info("Collectr home opened: url=%s title=%s", page.url, await page.title())

            await _submit_search(page, normalized_card_number)
            await _assert_collectr_available(page)
            await _assert_logged_in(page)
            logger.info("Collectr after search: url=%s title=%s", page.url, await page.title())

            listings = await _extract_collectr_listings(page, normalized_card_number, limit)
            if not listings:
                search_url = f"{COLLECTR_URL.rstrip('/')}/search?q={quote(normalized_card_number)}"
                await page.goto(search_url, wait_until="domcontentloaded", timeout=45_000)
                await _safe_networkidle(page)
                await _assert_collectr_available(page)
                await _assert_logged_in(page)
                listings = await _extract_collectr_listings(page, normalized_card_number, limit)

            logger.info(
                "Collectr scrape complete for %s; listings=%s prices=%s",
                normalized_card_number,
                len(listings),
                sum(1 for listing in listings if listing.get("price") is not None),
            )
            return listings
    except Exception:
        if page:
            await _save_collectr_debug_artifacts(page, "scrape-failure")
        raise
    finally:
        if browser:
            await browser.close()


def _collectr_scrape_in_thread(
    normalized_card_number: str,
    headless: bool,
    limit: int,
    storage_state: str,
):
    """Worker-thread entry: Playwright async needs a loop that supports subprocess (Windows)."""
    return asyncio.run(
        _collectr_scrape_async_impl(
            normalized_card_number,
            headless,
            limit,
            storage_state,
        )
    )


async def get_collectr_prices(card_number=DEFAULT_CARD_NUMBER, *, headless=True, limit=20):
    """Return raw Collectr scraper results using a required logged-in session."""
    normalized_card_number = _normalize_card_number(card_number)
    logger.info("Starting Collectr scrape for %s", normalized_card_number)
    storage_state = require_collectr_storage_state_path()
    logger.info("Collectr storage state loaded: %s", storage_state)

    try:
        return await asyncio.to_thread(
            _collectr_scrape_in_thread,
            normalized_card_number,
            headless,
            limit,
            storage_state,
        )
    except CollectrAuthError:
        logger.exception("Collectr authentication failed for %s", normalized_card_number)
        raise
    except PlaywrightTimeoutError as exc:
        logger.exception("Collectr scrape timed out for %s", normalized_card_number)
        raise CollectrScrapeError(f"Collectr scrape timed out for {normalized_card_number}") from exc
    except NotImplementedError as exc:
        logger.exception("Collectr Playwright failed to launch for %s", normalized_card_number)
        raise CollectrScrapeError(
            "Collectr Playwright failed to launch. If this persists on Windows, reinstall Playwright browsers."
        ) from exc
    except CollectrScrapeError:
        logger.exception("Collectr scraper returned a classified error for %s", normalized_card_number)
        raise
    except Exception as exc:
        logger.exception("Collectr scrape failed for %s", normalized_card_number)
        current_url = getattr(exc, "current_url", None) or getattr(exc.__cause__, "current_url", None)
        raise CollectrScrapeError(
            f"Collectr scrape failed for {normalized_card_number}: {exc}",
            current_url=current_url,
        ) from exc


async def get_collectr_price(card_number=DEFAULT_CARD_NUMBER):
    """Compatibility wrapper matching singular scraper naming."""
    return await get_collectr_prices(card_number)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    requested_card_number = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CARD_NUMBER
    listings = await get_collectr_prices(requested_card_number, headless=False)
    print(json.dumps(listings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
