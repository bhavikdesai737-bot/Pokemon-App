"""Async Playwright scraper for CardLadder.

Run from backend:
    venv\\Scripts\\python.exe scrapers\\cardladder.py 155-XY-P
"""

import asyncio
import json
import logging
import os
import re
import sys
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


logger = logging.getLogger(__name__)

CARDLADDER_URL = os.getenv("CARDLADDER_URL", "https://www.cardladder.com")
DEFAULT_CARD_NUMBER = os.getenv("CARDLADDER_CARD_NUMBER", "155-XY-P")
SEARCH_SELECTORS = (
    "input[type='search']",
    "input[placeholder*='Search' i]",
    "input[aria-label*='Search' i]",
    "input[name*='search' i]",
    "input",
)
FIELD_SELECTORS = {
    "title": ".card-title",
    "price": ".price",
    "grade": ".grade",
}
GRADED_PATTERN = re.compile(r"\b(PSA|ACE|BGS|CGC|SGC)\s*(\d+(?:\.\d+)?)\b", re.IGNORECASE)


def _clean_text(value):
    if not value:
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
        logger.info("Unable to parse CardLadder price: %r", value)
        return None, currency

    number = match.group(1).replace(",", "")
    try:
        if currency == "USD":
            dollars, _, cents = number.partition(".")
            return int(dollars) * 100 + int((cents + "00")[:2]), currency
        return int(float(number)), currency
    except ValueError:
        logger.info("Unable to parse CardLadder price: %r", value)
        return None, currency


def _parse_grading(title, grade_text):
    combined = " ".join(filter(None, [title, grade_text]))
    match = GRADED_PATTERN.search(combined)
    if match:
        return match.group(1).upper(), _parse_grade(match.group(2))

    grade = _parse_grade(grade_text)
    return (None, grade) if grade is not None else (None, None)


def _parse_grade(value):
    text = _clean_text(value)
    if not text:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None

    grade = float(match.group(1))
    return int(grade) if grade.is_integer() else grade


async def _first_visible_locator(page, selectors):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=3_000)
            logger.info("Matched CardLadder selector: %s", selector)
            return locator
        except PlaywrightTimeoutError:
            logger.debug("CardLadder selector not visible: %s", selector)

    return None


async def _safe_networkidle(page, timeout=20_000):
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
    except PlaywrightTimeoutError:
        logger.debug("Timed out waiting for networkidle; continuing with visible DOM")


async def _search_card(page, card_number):
    logger.info("Searching CardLadder for %s", card_number)
    search_input = await _first_visible_locator(page, SEARCH_SELECTORS)
    if search_input is None:
        logger.warning("No visible CardLadder search input found")
        return False

    await search_input.fill(card_number)
    await search_input.press("Enter")
    try:
        await page.wait_for_url(lambda url: card_number.lower() in url.lower(), timeout=5_000)
        logger.info("CardLadder search changed URL to: %s", page.url)
    except PlaywrightTimeoutError:
        logger.debug("CardLadder search did not change URL; waiting for result content")

    await _safe_networkidle(page)
    return True


async def _extract_listing_from_title(title_locator, index):
    raw = await title_locator.evaluate(
        """(titleEl) => {
            const clean = (value) => value ? value.replace(/\\s+/g, " ").trim() : null;
            const container =
                titleEl.closest("a, article, li, [class*='result'], [class*='card']") ||
                titleEl.parentElement;
            const priceEl = container?.querySelector(".price");
            const gradeEl = container?.querySelector(".grade");
            const imageEl = container?.querySelector("img");
            const anchorEl = container?.matches("a[href]")
                ? container
                : container?.querySelector("a[href]") || titleEl.closest("a[href]");

            return {
                title: clean(titleEl.textContent),
                price: clean(priceEl?.textContent),
                grade: clean(gradeEl?.textContent),
                imageUrl: imageEl?.currentSrc || imageEl?.src || imageEl?.getAttribute("data-src") || null,
                productUrl: anchorEl?.href || null,
            };
        }"""
    )
    logger.debug("Raw CardLadder listing %s: %s", index, raw)
    return raw


def _normalize_listing(raw_listing):
    title = _clean_text(raw_listing.get("title"))
    price, currency = _parse_price(raw_listing.get("price"))
    grading_company, grade = _parse_grading(title, raw_listing.get("grade"))
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
        "image_url": urljoin(CARDLADDER_URL, image_url) if image_url else None,
        "url": urljoin(CARDLADDER_URL, product_url) if product_url else None,
        "product_url": urljoin(CARDLADDER_URL, product_url) if product_url else None,
        "listing_type": "graded" if grading_company or grade is not None else "raw",
        "source": "cardladder",
    }


async def _extract_cardladder_listings(page, limit=20):
    try:
        await page.locator(FIELD_SELECTORS["title"]).first.wait_for(state="visible", timeout=15_000)
    except PlaywrightTimeoutError:
        logger.warning("No visible CardLadder title results found")
        return []

    title_locators = page.locator(FIELD_SELECTORS["title"])
    count = await title_locators.count()
    logger.info("CardLadder title selector matched %s listings", count)

    listings = []
    seen = set()
    for index in range(min(count, limit)):
        title_locator = title_locators.nth(index)
        if not await title_locator.is_visible():
            continue

        raw_listing = await _extract_listing_from_title(title_locator, index)
        listing = _normalize_listing(raw_listing)
        dedupe_key = (
            listing["card_title"],
            listing["grading_company"],
            listing["grade"],
            listing["price"],
            listing["url"],
        )
        if dedupe_key in seen:
            logger.debug("Skipping duplicate CardLadder listing: %s", dedupe_key)
            continue

        seen.add(dedupe_key)
        listings.append(listing)

    logger.info("Extracted %s CardLadder listings", len(listings))
    return listings


async def get_cardladder_listings(card_number=DEFAULT_CARD_NUMBER, *, headless=True, limit=20):
    """Return CardLadder search results as structured JSON-compatible dictionaries."""
    normalized_card_number = _normalize_card_number(card_number)
    logger.info("Starting CardLadder scrape for %s", normalized_card_number)

    browser = None

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=headless)
            page = await browser.new_page(viewport={"width": 1440, "height": 1000})
            await page.goto(CARDLADDER_URL, wait_until="domcontentloaded", timeout=45_000)
            await _safe_networkidle(page)
            logger.info("Opened CardLadder page title=%s", await page.title())
            if not await _search_card(page, normalized_card_number):
                return []
            return await _extract_cardladder_listings(page, limit=limit)
    except PlaywrightTimeoutError:
        logger.warning("CardLadder scrape timed out for %s", normalized_card_number)
        return []
    except NotImplementedError:
        logger.warning("CardLadder Playwright is unavailable in this server event loop")
        return []
    except Exception:
        logger.exception("CardLadder scrape failed for %s", normalized_card_number)
        return []
    finally:
        if browser:
            await browser.close()


async def get_cardladder_price(card_number=DEFAULT_CARD_NUMBER):
    """Compatibility wrapper matching other scraper naming."""
    return await get_cardladder_listings(card_number)


async def get_cardladder_prices(card_number=DEFAULT_CARD_NUMBER):
    """Plural compatibility wrapper for CardLadder listings."""
    return await get_cardladder_listings(card_number)


async def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    requested_card_number = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CARD_NUMBER
    listings = await get_cardladder_listings(requested_card_number, headless=False)
    print(json.dumps(listings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
