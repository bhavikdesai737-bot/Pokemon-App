import logging
import re
from urllib.parse import quote, urljoin

from scrapling import Fetcher


logger = logging.getLogger(__name__)

BASE_URL = "https://www.cardrush-pokemon.jp"

PRODUCT_SELECTORS = (
    ".item_data",
    "[data-product-id]",
    ".product_data",
)
NAME_SELECTORS = (
    ".goods_name",
    ".item_name .goods_name",
    ".item_name",
)
PRICE_SELECTORS = (
    ".selling_price .figure",
    ".price .figure",
    ".selling_price",
    ".price",
)
STOCK_SELECTORS = (
    ".stock",
    ".item_info .stock",
    ".soldout",
)
PRODUCT_URL_SELECTORS = (
    "a.item_data_link[href]",
    "a[href*='/product/']",
)
CONDITION_PATTERN = re.compile(r"状態\s*(A-|A|B-|B|C)")
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
            logger.debug("Cardrush selector matched: %s", selector)
            return elements[0]
    logger.debug("Cardrush selectors had no match: %s", selectors)
    return None


def _extract_name(product):
    element = _select_first(product, NAME_SELECTORS)
    if element:
        return _clean_card_name(_element_text(element))

    image = _select_first(product, ("img[alt]",))
    if image:
        logger.debug("Cardrush name fallback matched img alt")
        return _clean_card_name(_attr(image, "alt"))

    return None


def _clean_card_name(value):
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"^〔状態\s*(?:A-|A|B-|B|C)〕", "", text)
    text = re.sub(r"^〔[^〕]*(?:PSA|ACE)\s*\d+[^〕]*〕", "", text, flags=re.IGNORECASE)
    return _clean_text(text)


def _extract_price(product):
    element = _select_first(product, PRICE_SELECTORS)
    price_text = _element_text(element)

    if not price_text:
        return {
            "amount": None,
            "currency": "JPY",
            "display": None,
        }

    digits = re.sub(r"[^\d]", "", price_text)
    amount = int(digits) if digits else None

    return {
        "amount": amount,
        "currency": "JPY",
        "display": price_text,
    }


def _empty_result():
    return []


def _extract_product_url(product):
    element = _select_first(product, PRODUCT_URL_SELECTORS)
    href = _attr(element, "href")
    return urljoin(BASE_URL, href) if href else None


def _extract_image_url(product):
    image = _select_first(product, ("img",))
    if not image:
        logger.info("Missing Cardrush image for listing: %s", _element_text(product))
        return None

    src = _attr(image, "data-x2") or _attr(image, "src")
    return urljoin(BASE_URL, src) if src else None


def _extract_stock_status(product):
    element = _select_first(product, STOCK_SELECTORS)
    raw_stock = _element_text(element)
    class_value = _attr(element, "class") or ""
    classes = set(str(class_value).split())
    stock_text = (raw_stock or "").lower()

    if "soldout" in classes or stock_text in {"×", "x"}:
        status = "out_of_stock"
    elif any(text in stock_text for text in ("売切", "品切", "sold out", "out of stock")):
        status = "out_of_stock"
    elif any(text in stock_text for text in ("○", "在庫", "カート", "add to cart", "in stock")):
        status = "in_stock"
    else:
        status = "unknown"

    return status, raw_stock


def _extract_condition_grade(product):
    text_sources = [
        _element_text(element)
        for element in product.css(".goods_name, .model_number_value")
    ]

    image = _select_first(product, ("img[alt]",))
    if image:
        text_sources.append(_clean_text(_attr(image, "alt")))

    for text in filter(None, text_sources):
        match = CONDITION_PATTERN.search(text)
        if match:
            return match.group(1)

    # Cardrush omits the condition marker on its default near-mint listing.
    name_element = _select_first(product, (".goods_name",))
    name = _element_text(name_element) or ""
    if name and not name.startswith("〔"):
        return "A"

    logger.info("Missing Cardrush condition grade for listing: %s", _element_text(product))
    return None


def _extract_grading(product):
    text = _product_text(product)
    match = GRADED_PATTERN.search(text)
    if not match and "鑑定済" not in text:
        return None

    return {
        "company": match.group(1).upper() if match else "UNKNOWN",
        "grade": int(match.group(2)) if match else None,
    }


def _listing_type(product):
    return "graded" if _extract_grading(product) else "raw"


def _matches_card_number(product, card_number):
    target = _normalize_for_match(card_number)
    return target in _normalize_for_match(_product_text(product))


def _parse_listing(product):
    stock_status, raw_stock = _extract_stock_status(product)
    price = _extract_price(product)
    grading = _extract_grading(product)

    listing = {
        "name": _extract_name(product),
        "price": price["amount"],
        "currency": "JPY",
        "condition_grade": None if grading else _extract_condition_grade(product),
        "listing_type": "graded" if grading else "raw",
        "grading_company": grading["company"] if grading else None,
        "grade": grading["grade"] if grading else None,
        "stock_status": stock_status,
        "in_stock": stock_status == "in_stock" if stock_status != "unknown" else None,
        "url": _extract_product_url(product),
        "image_url": _extract_image_url(product),
        "exact_card_number_match": True,
    }

    logger.debug("Cardrush parsed listing: %s raw_stock=%s", listing, raw_stock)
    return listing


def get_cardrush_price(card_number):
    logging.info(f"Searching Cardrush for {card_number}")
    logger.debug("Starting Cardrush search for card_number=%s", card_number)

    search_url = (
        f"https://www.cardrush-pokemon.jp/product-list?keyword={quote(str(card_number).strip())}"
    )

    try:
        page = Fetcher.get(
            search_url,
            timeout=25,
            headers={"Accept-Language": "ja,en-US;q=0.9,en;q=0.8"},
            stealthy_headers=True,
        )
    except Exception:
        logger.exception("Cardrush Scrapling fetch failed for %s", search_url)
        return _empty_result()

    if page.status != 200:
        logger.warning(
            "Cardrush returned non-200 status: status=%s url=%s",
            page.status,
            search_url,
        )
        return _empty_result()

    products = []
    for selector in PRODUCT_SELECTORS:
        products = page.css(selector)
        logger.debug("Cardrush product selector %s matched %s products", selector, len(products))
        if products:
            break

    if not products:
        logger.info("Cardrush returned no products for card_number=%s", card_number)
        return _empty_result()

    listings = []
    seen_urls = set()

    for product in products:
        if not _matches_card_number(product, card_number):
            logger.info("Skipping non-exact Cardrush listing: %s", _product_text(product)[:200])
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
            logger.debug("Skipping duplicate Cardrush listing: %s", dedupe_key)
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

    logger.info("Cardrush returned %s unique listings for %s", len(listings), card_number)
    return listings
