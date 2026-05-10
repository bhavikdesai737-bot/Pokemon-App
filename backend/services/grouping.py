"""Helpers for grouping normalized marketplace listings."""

from collections import defaultdict


def _group_by(listings, key_name):
    grouped = defaultdict(list)

    for listing in listings or []:
        if not isinstance(listing, dict):
            continue

        key = listing.get(key_name) or "unknown"
        grouped[key].append(listing)

    return dict(grouped)


def group_by_card_name(listings):
    return _group_by(listings, "name")


def group_by_marketplace(listings):
    return _group_by(listings, "marketplace")


def group_by_condition(listings):
    return _group_by(listings, "condition_grade")


def group_listings_by_marketplace(listings):
    card_name = None
    image = None
    marketplaces = {
        "cardrush": [],
        "hareruya": [],
    }

    for listing in listings or []:
        if not isinstance(listing, dict):
            continue

        marketplace = listing.get("marketplace")
        if not marketplace:
            continue

        marketplace_key = str(marketplace).lower()
        marketplaces.setdefault(marketplace_key, [])

        card_name = card_name or listing.get("name")
        image = image or listing.get("image_url") or listing.get("image")

        marketplaces[marketplace_key].append(
            {
                "name": listing.get("name"),
                "condition_grade": listing.get("condition_grade"),
                "price": listing.get("price"),
                "currency": listing.get("currency"),
                "in_stock": listing.get("in_stock"),
                "stock_status": listing.get("stock_status"),
                "url": listing.get("url"),
                "image_url": listing.get("image_url"),
            }
        )

    for marketplace_listings in marketplaces.values():
        marketplace_listings.sort(
            key=lambda listing: (
                listing["price"] is None,
                listing["price"] if listing["price"] is not None else 0,
            )
        )

    return {
        "card_name": card_name,
        "image": image,
        "marketplaces": marketplaces,
    }
