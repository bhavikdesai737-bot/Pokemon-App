"""Normalize scraper outputs into one API contract."""

import logging
import re


logger = logging.getLogger(__name__)


def normalize_card_number(card_number):
    return str(card_number).strip().replace("/", "-").upper()


def _unwrap_price(value):
    if isinstance(value, dict):
        return value.get("amount") or value.get("price") or value.get("price_yen") or value.get("price_usd")
    return value


def normalize_jpy_price(value):
    value = _unwrap_price(value)

    if value is None:
        return None
    if isinstance(value, int):
        return value

    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        logger.info("Unable to normalize JPY price: %r", value)
        return None

    return int(digits)


def normalize_usd_price(value):
    value = _unwrap_price(value)

    if value is None:
        return None
    if isinstance(value, int):
        return value

    match = re.search(r"(\d+(?:[,\d]*)(?:\.\d{1,2})?)", str(value))
    if not match:
        logger.info("Unable to normalize USD price: %r", value)
        return None

    number = match.group(1).replace(",", "")
    dollars, _, cents = number.partition(".")
    cents = (cents + "00")[:2]

    try:
        return int(dollars) * 100 + int(cents)
    except ValueError:
        logger.info("Unable to normalize USD price: %r", value)
        return None


def normalize_price(value, currency="JPY"):
    if str(currency).upper() == "USD":
        return normalize_usd_price(value)
    return normalize_jpy_price(value)


def normalize_in_stock(value):
    if value is None or isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in {"true", "yes", "in_stock", "in stock", "available", "○"}:
        return True
    if text in {"false", "no", "out_of_stock", "out of stock", "sold out", "soldout", "×", "x"}:
        return False

    return None


def normalize_condition_grade(value):
    if value is None:
        return None

    text = str(value).strip().upper()
    compact = re.sub(r"\s+", "", text)
    compact = compact.replace("－", "-").replace("−", "-").replace("ー", "-")

    if "状態難" in compact or "HEAVILYPLAYED" in compact or "DAMAGED" in compact:
        return "C"

    match = re.search(r"状態(A-|A|B-|B|C)", compact)
    if match:
        return match.group(1)

    english_map = {
        "NEARMINT": "A",
        "NM": "A",
        "EXCELLENT": "A-",
        "EX": "A-",
        "LIGHTPLAYED": "B",
        "LP": "B",
        "PLAYED": "B-",
        "MODERATEPLAYED": "B-",
        "MP": "B-",
        "POOR": "C",
        "HEAVYPLAYED": "C",
        "HP": "C",
    }

    if compact in {"A", "A-", "B", "B-", "C"}:
        return compact
    if compact in english_map:
        return english_map[compact]

    logger.info("Unable to normalize condition grade: %r", value)
    return None


def normalize_store_result(source, result):
    if isinstance(result, list):
        normalized_listings = [
            normalize_store_result(source, listing)
            for listing in result
            if isinstance(listing, dict)
        ]
        logger.debug("Normalized %s listings: %s", source, normalized_listings)
        return normalized_listings

    result = result or {}
    currency = result.get("currency") or "JPY"
    price_value = result["price_yen"] if "price_yen" in result else result.get("price")
    stock_value = result["in_stock"] if "in_stock" in result else result.get("stock_status")

    normalized = {
        "name": result.get("name") or result.get("card_name"),
        "price": normalize_price(price_value, currency),
        "currency": currency,
        "in_stock": normalize_in_stock(stock_value),
        "url": result.get("url") or result.get("product_url"),
        "image_url": result.get("image_url") or result.get("image") or result.get("imageUrl"),
    }

    if "condition_grade" in result:
        normalized["condition_grade"] = normalize_condition_grade(result.get("condition_grade"))
    if "stock_status" in result:
        normalized["stock_status"] = result.get("stock_status")
    if "listing_type" in result:
        normalized["listing_type"] = result.get("listing_type")
    if "grading_company" in result:
        normalized["grading_company"] = result.get("grading_company")
    if "grade" in result:
        normalized["grade"] = result.get("grade")
    if "certification_number" in result:
        normalized["certification_number"] = result.get("certification_number")
    if "graded_population" in result:
        normalized["graded_population"] = result.get("graded_population")
    if "population_higher" in result:
        normalized["population_higher"] = result.get("population_higher")
    if "exact_card_number_match" in result:
        normalized["exact_card_number_match"] = result.get("exact_card_number_match")

    logger.debug("Normalized %s result: %s", source, normalized)
    return normalized
