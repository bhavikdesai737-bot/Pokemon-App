"""eBay UK price scraper using the official Browse API."""

import logging
import os
from statistics import mean
from typing import Any

import requests
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

load_dotenv()

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope"
DEFAULT_MARKETPLACE_ID = "EBAY_GB"
BAD_TITLE_TERMS = (
    "proxy",
    "custom",
    "digital",
    "jumbo",
    "sleeve",
    "case",
    "mystery",
    "bundle",
    "lot",
    "empty",
    "pack",
)
QUERY_TEMPLATES = {
    "raw": "{card_number} Pokemon card",
    "psa": "{card_number} Pokemon PSA",
    "ace": "{card_number} Pokemon ACE",
}


class EbayConfigError(RuntimeError):
    """Raised when required eBay credentials are missing."""


class EbayOAuthError(RuntimeError):
    """Raised when eBay OAuth token retrieval fails."""


class EbayBrowseAPIError(RuntimeError):
    """Raised when the eBay Browse API search fails."""


def _response_error_detail(response):
    try:
        body = response.text[:1000]
    except Exception:
        body = "<unable to read response body>"

    return {
        "status_code": response.status_code,
        "url": response.url,
        "body": body,
    }


def _error_detail(exc, stage):
    detail = {
        "stage": stage,
        "type": type(exc).__name__,
        "message": str(exc),
    }
    cause = getattr(exc, "__cause__", None)
    response = getattr(exc, "response", None) or getattr(cause, "response", None)
    if response is not None:
        detail["response"] = _response_error_detail(response)
    return detail


def _empty_section(error=None, error_detail=None):
    section = {
        "count": 0,
        "min_price": None,
        "max_price": None,
        "average_price": None,
        "listings": [],
    }
    if error:
        section["error"] = error
    if error_detail:
        section["error_detail"] = error_detail
    return section


def _empty_result(error=None, error_detail=None):
    result = {
        "raw": _empty_section(),
        "psa": _empty_section(),
        "ace": _empty_section(),
    }
    if error:
        result["error"] = error
    if error_detail:
        result["error_detail"] = error_detail
    return result


def _get_config():
    return {
        "client_id": os.getenv("EBAY_CLIENT_ID"),
        "client_secret": os.getenv("EBAY_CLIENT_SECRET"),
        "marketplace_id": os.getenv("EBAY_MARKETPLACE_ID") or DEFAULT_MARKETPLACE_ID,
        "env": (os.getenv("EBAY_ENV") or "PRODUCTION").upper(),
    }


def _get_access_token():
    config = _get_config()
    client_id = config["client_id"]
    client_secret = config["client_secret"]

    if not client_id or not client_secret:
        missing = [
            name
            for name, value in (
                ("EBAY_CLIENT_ID", client_id),
                ("EBAY_CLIENT_SECRET", client_secret),
            )
            if not value
        ]
        raise EbayConfigError(f"Missing required eBay credentials: {', '.join(missing)}")
    if config["env"] != "PRODUCTION":
        logger.warning("Only eBay production endpoints are configured; EBAY_ENV=%s", config["env"])

    logger.info("Requesting eBay OAuth token")
    try:
        response = requests.post(
            TOKEN_URL,
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "scope": EBAY_SCOPE,
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise EbayOAuthError("eBay OAuth token request failed") from exc
    except requests.RequestException as exc:
        raise EbayOAuthError(f"eBay OAuth request error: {exc}") from exc

    token = response.json().get("access_token")
    if not token:
        raise EbayOAuthError("eBay OAuth response did not include an access token")

    return token


def _bad_title(title):
    normalized_title = str(title or "").lower()
    return any(term in normalized_title for term in BAD_TITLE_TERMS)


def _parse_price(price_data: dict[str, Any] | None):
    if not price_data:
        return None, None

    value = price_data.get("value")
    currency = price_data.get("currency")
    try:
        return float(value), currency
    except (TypeError, ValueError):
        logger.debug("Unable to parse eBay price: %s", price_data)
        return None, currency


def _normalize_listing(item):
    price, currency = _parse_price(item.get("price"))
    image = item.get("image") or {}
    seller = item.get("seller") or {}

    return {
        "title": item.get("title"),
        "price": price,
        "currency": currency,
        "condition": item.get("condition"),
        "item_url": item.get("itemWebUrl"),
        "image_url": image.get("imageUrl"),
        "seller_username": seller.get("username"),
        "buying_options": item.get("buyingOptions") or [],
    }


def _summarize_listings(listings):
    prices = [listing["price"] for listing in listings if isinstance(listing.get("price"), (int, float))]

    return {
        "count": len(listings),
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "average_price": round(mean(prices), 2) if prices else None,
        "listings": listings,
    }


def _search_ebay(query, token, marketplace_id, limit=20):
    logger.info("Searching eBay UK Browse API for query=%r", query)
    try:
        response = requests.get(
            BROWSE_SEARCH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
                "Accept": "application/json",
            },
            params={
                "q": query,
                "limit": limit,
            },
            timeout=25,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise EbayBrowseAPIError(f"eBay Browse API request failed for query={query!r}") from exc
    except requests.RequestException as exc:
        raise EbayBrowseAPIError(f"eBay Browse API request error for query={query!r}: {exc}") from exc

    items = response.json().get("itemSummaries") or []
    listings = []
    for item in items:
        title = item.get("title")
        if _bad_title(title):
            logger.debug("Skipping filtered eBay title: %s", title)
            continue

        listing = _normalize_listing(item)
        if listing["price"] is None:
            logger.debug("Skipping eBay listing without price: %s", title)
            continue

        listings.append(listing)

    logger.info("eBay query=%r returned %s usable listings", query, len(listings))
    return _summarize_listings(listings)


def get_ebay_uk_prices(card_number: str):
    """Return eBay UK listed prices grouped into raw, PSA, and ACE sections."""
    try:
        normalized_card_number = str(card_number or "").strip().replace("/", "-").upper()
        if not normalized_card_number:
            logger.warning("No card number provided for eBay search")
            return _empty_result("No card number provided for eBay search")

        config = _get_config()
        marketplace_id = config["marketplace_id"] or DEFAULT_MARKETPLACE_ID
        token = _get_access_token()

        results = {}
        for section, template in QUERY_TEMPLATES.items():
            query = template.format(card_number=normalized_card_number)
            try:
                results[section] = _search_ebay(query, token, marketplace_id)
            except Exception as exc:
                logger.exception("eBay search failed for section=%s card_number=%s", section, normalized_card_number)
                results[section] = _empty_section(
                    f"{type(exc).__name__}: {exc}",
                    _error_detail(exc, "browse_api"),
                )

        return {
            "raw": results.get("raw", _empty_section()),
            "psa": results.get("psa", _empty_section()),
            "ace": results.get("ace", _empty_section()),
        }
    except Exception as exc:
        logger.exception("eBay UK price lookup failed for card_number=%s", card_number)
        stage = "credentials" if isinstance(exc, EbayConfigError) else "oauth"
        return _empty_result(f"{type(exc).__name__}: {exc}", _error_detail(exc, stage))
