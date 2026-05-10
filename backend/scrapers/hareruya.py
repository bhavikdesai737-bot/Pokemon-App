"""Hareruya price source."""

import logging
import re
from urllib.parse import quote, urljoin

from scrapling import Fetcher


logger = logging.getLogger(__name__)

BASE_URL = "https://www.hareruya2.com"

PRODUCT_SELECTORS = (
    ".product-card-wrapper",
    ".card-wrapper",
    ".grid__item .card-wrapper",
    ".product-item",
)
NAME_SELECTORS = (
    ".InfoSection .card__heading.h5",
    ".card__heading.h5",
    ".card__heading",
    ".product-name",
    ".product_name",
    "img[alt]",
)
PRICE_SELECTORS = (
    ".PriceInventoryBlock .figure",
    ".price__regular .figure",
    ".price .figure",
    ".price-item",
)
URL_SELECTORS = (
    "a.full-unstyled-link[href]",
    "a[href*='/products/']",
    "a[href]",
)
STOCK_SELECTORS = (
    ".product__inventory",
    ".SoldoutBadge",
    ".badge",
    ".soldout-button",
)
CONDITION_PATTERNS = (
    re.compile(r"状態\s*(A-|A|B-|B|C)"),
    re.compile(r"PSA\s*(\d+)", re.IGNORECASE),
)
GRADED_PATTERN = re.compile(r"\b(PSA|ACE)\s*(\d+)", re.IGNORECASE)


def _clean_text(value):
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip() or None


def _normalize_for_match(value):
    return str(value or "").replace("/", "-").upper()


def _element_text(element):
    if not element:
        return None
    try:
        return _clean_text(element.get_all_text(" ", strip=True))
    except AttributeError:
        return _clean_text(getattr(element, "text", None))


def _attr(element, name):
    if not element:
        return None
    return element.attrib.get(name)


def _product_text(product):
    text = _element_text(product) or ""
    image = _select_first(product, ("img[alt]",))
    if image:
        text = f"{text} {_clean_text(_attr(image, 'alt')) or ''}"
    return text


def _select_first(parent, selectors):
    for selector in selectors:
        elements = parent.css(selector)
        if elements:
            logger.debug("Hareruya selector matched: %s", selector)
            return elements[0]
    logger.debug("Hareruya selectors had no match: %s", selectors)
    return None


def _empty_result():
    return []


def _extract_price_yen(product):
    element = _select_first(product, PRICE_SELECTORS)
    price_text = _element_text(element)

    if not price_text:
        return None

    digits = re.sub(r"[^\d]", "", price_text)
    return int(digits) if digits else None


def _extract_name(product):
    element = _select_first(product, NAME_SELECTORS)
    if element and getattr(element, "tag", None) == "img":
        return _clean_text(_attr(element, "alt"))
    if element:
        return _element_text(element)

    image = _select_first(product, ("img[alt]",))
    if image:
        logger.debug("Hareruya name fallback matched img alt")
        return _clean_text(_attr(image, "alt"))

    return None


def _extract_condition_grade(product):
    text = _product_text(product)

    for pattern in CONDITION_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue

        if pattern.pattern.startswith("PSA"):
            return None
        return match.group(1)

    logger.info("Missing Hareruya condition grade for listing: %s", text[:200])
    return None


def _extract_grading(product):
    text = _product_text(product)
    match = GRADED_PATTERN.search(text)
    if not match:
        return None

    return {
        "company": match.group(1).upper(),
        "grade": int(match.group(2)),
    }


def _extract_url(product):
    element = _select_first(product, URL_SELECTORS)
    href = _attr(element, "href")
    return urljoin(BASE_URL, href) if href else None


def _extract_stock_status(product):
    element = _select_first(product, STOCK_SELECTORS)
    raw_stock = _element_text(element) if element else _product_text(product)
    stock_text = (raw_stock or "").lower()

    if any(text in raw_stock for text in ("在庫なし", "売り切れ")) or "sold out" in stock_text:
        return "out_of_stock", raw_stock
    if any(text in raw_stock for text in ("在庫あり", "カート")) or "in stock" in stock_text:
        return "in_stock", raw_stock

    return "unknown", raw_stock


def _extract_image_url(product):
    image = _select_first(product, ("img",))
    if not image:
        listing_text = _product_text(product)
        logger.info("Missing Hareruya image for listing: %s", listing_text[:200] if listing_text else None)
        return None

    src = _attr(image, "src") or _attr(image, "data-src")
    return urljoin(BASE_URL, src) if src else None


def _matches_card_number(product, card_number):
    target = _normalize_for_match(card_number)
    return target in _normalize_for_match(_product_text(product))


def _parse_listing(product):
    grading = _extract_grading(product)
    stock_status, raw_stock = _extract_stock_status(product)

    listing = {
        "name": _extract_name(product),
        "price": _extract_price_yen(product),
        "currency": "JPY",
        "condition_grade": None if grading else _extract_condition_grade(product),
        "listing_type": "graded" if grading else "raw",
        "grading_company": grading["company"] if grading else None,
        "grade": grading["grade"] if grading else None,
        "stock_status": stock_status,
        "in_stock": stock_status == "in_stock" if stock_status != "unknown" else None,
        "url": _extract_url(product),
        "image_url": _extract_image_url(product),
        "exact_card_number_match": True,
    }

    logger.debug("Hareruya parsed listing: %s raw_stock=%s", listing, raw_stock)
    return listing


def get_hareruya_price(card_number):
    logger.info("Searching Hareruya for %s", card_number)
    logger.debug("Starting Hareruya search for card_number=%s", card_number)

    search_url = f"{BASE_URL}/search?q={quote(str(card_number).strip())}&type=product"
    try:
        page = Fetcher.get(
            search_url,
            timeout=25,
            headers={
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
                "Referer": BASE_URL,
            },
            stealthy_headers=True,
            retries=3,
            retry_delay=1,
        )
    except Exception:
        logger.exception("Hareruya Scrapling fetch failed for %s", search_url)
        return _empty_result()

    if page.status != 200:
        logger.warning(
            "Hareruya returned non-200 status: status=%s url=%s",
            page.status,
            search_url,
        )
        return _empty_result()

    products = []
    for selector in PRODUCT_SELECTORS:
        products = page.css(selector)
        logger.debug("Hareruya product selector %s matched %s products", selector, len(products))
        if products:
            break

    if not products:
        logger.info("Hareruya returned no products for card_number=%s", card_number)
        return _empty_result()

    listings = []
    seen_urls = set()

    for product in products:
        if not _matches_card_number(product, card_number):
            product_text = _product_text(product)
            logger.debug("Skipping non-matching Hareruya product: %s", product_text[:200] if product_text else None)
            continue

        listing = _parse_listing(product)
        dedupe_key = listing["url"] or (
            listing["name"],
            listing["price"],
            listing["condition_grade"],
            listing["listing_type"],
            listing["grade"],
        )

        if dedupe_key in seen_urls:
            logger.debug("Skipping duplicate Hareruya listing: %s", dedupe_key)
            continue

        seen_urls.add(dedupe_key)
        listings.append(listing)

    listings.sort(
        key=lambda listing: (
            not listing["exact_card_number_match"],
            listing["listing_type"] != "raw",
            listing["price"] is None,
            listing["price"] if listing["price"] is not None else 0,
        )
    )

    logger.info("Hareruya returned %s unique listings for %s", len(listings), card_number)
    return listings
