"""SQLite database connection and persistence helpers."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from databases import Database
from sqlalchemy import MetaData, create_engine, insert, select, update


logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'pokemon_prices.db'}"
CACHE_TTL_SECONDS = 60 * 60

database = Database(DATABASE_URL)
metadata = MetaData()
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def create_db_and_tables():
    """Create database tables registered in database.models."""
    from database import models  # noqa: F401

    metadata.create_all(engine)
    _ensure_listing_columns()


def _ensure_listing_columns():
    """Add newly introduced SQLite columns for existing local databases."""
    required_columns = {
        "certification_number": "VARCHAR",
        "graded_population": "INTEGER",
        "population_higher": "INTEGER",
    }

    with engine.begin() as conn:
        existing_columns = {
            row["name"]
            for row in conn.exec_driver_sql("PRAGMA table_info(listings)").mappings()
        }

        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                logger.info("Adding missing listings column: %s", column_name)
                conn.exec_driver_sql(f"ALTER TABLE listings ADD COLUMN {column_name} {column_type}")


def _iter_marketplace_listings(results_by_marketplace):
    for marketplace, listings in (results_by_marketplace or {}).items():
        if isinstance(listings, dict):
            listings = [listings]

        for listing in listings or []:
            if isinstance(listing, dict):
                yield marketplace, listing


def _utc_now():
    return datetime.now(timezone.utc)


def _coerce_datetime(value):
    if value is None:
        return value

    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Unable to parse cache timestamp: %r", value)
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_cached_search_result(card_number, ttl_seconds=CACHE_TTL_SECONDS):
    """Return a cached search response if it is still fresh."""
    create_db_and_tables()

    from database.models import search_cache

    with engine.connect() as conn:
        row = conn.execute(
            select(
                search_cache.c.response_json,
                search_cache.c.cached_at,
                search_cache.c.expires_at,
            ).where(search_cache.c.card_number == card_number)
        ).mappings().first()

    if not row:
        logger.info("Search cache miss for card_number=%s", card_number)
        return None

    expires_at = _coerce_datetime(row["expires_at"])
    cached_at = _coerce_datetime(row["cached_at"])
    if not expires_at or expires_at <= _utc_now():
        logger.info(
            "Search cache expired for card_number=%s cached_at=%s expires_at=%s",
            card_number,
            cached_at,
            expires_at,
        )
        return None

    try:
        cached_result = json.loads(row["response_json"])
    except json.JSONDecodeError:
        logger.warning("Search cache payload is invalid for card_number=%s", card_number)
        return None

    logger.info("Search cache hit for card_number=%s cached_at=%s", card_number, cached_at)
    return cached_result


def save_search_cache(card_number, response, ttl_seconds=CACHE_TTL_SECONDS):
    """Store a search response for short-lived reuse."""
    create_db_and_tables()

    from database.models import search_cache

    cached_at = _utc_now()
    expires_at = cached_at + timedelta(seconds=ttl_seconds)
    response_json = json.dumps(response, ensure_ascii=False)
    values = {
        "card_number": card_number,
        "response_json": response_json,
        "cached_at": cached_at,
        "expires_at": expires_at,
    }

    with engine.begin() as conn:
        existing_id = conn.execute(
            select(search_cache.c.id).where(search_cache.c.card_number == card_number)
        ).scalar_one_or_none()

        if existing_id is None:
            conn.execute(insert(search_cache).values(**values))
        else:
            conn.execute(
                update(search_cache)
                .where(search_cache.c.id == existing_id)
                .values(**values)
            )

    logger.info(
        "Saved search cache for card_number=%s cached_at=%s expires_at=%s",
        card_number,
        cached_at,
        expires_at,
    )
    return response


def _first_present_listing(results_by_marketplace):
    for _, listing in _iter_marketplace_listings(results_by_marketplace):
        if listing.get("name") or listing.get("image_url"):
            return listing
    return {}


def _get_or_create_card(conn, card_number, results_by_marketplace):
    from database.models import cards

    existing_card_id = conn.execute(
        select(cards.c.id).where(cards.c.card_number == card_number)
    ).scalar_one_or_none()

    first_listing = _first_present_listing(results_by_marketplace)
    card_values = {
        "card_name": first_listing.get("name"),
        "image_url": first_listing.get("image_url"),
    }

    if existing_card_id is not None:
        update_values = {key: value for key, value in card_values.items() if value}
        if update_values:
            conn.execute(update(cards).where(cards.c.id == existing_card_id).values(**update_values))
        return existing_card_id

    result = conn.execute(
        insert(cards).values(
            card_number=card_number,
            **card_values,
        )
    )
    return result.inserted_primary_key[0]


def save_listing(conn, card_id, card_number, marketplace, listing):
    """Save one normalized marketplace listing."""
    from database.models import listings

    values = {
        "card_id": card_id,
        "card_number": card_number,
        "card_name": listing.get("name"),
        "marketplace": marketplace,
        "condition": listing.get("condition_grade"),
        "price": listing.get("price"),
        "currency": listing.get("currency") or "JPY",
        "listing_type": listing.get("listing_type") or "raw",
        "grading_company": listing.get("grading_company"),
        "grade": listing.get("grade"),
        "certification_number": listing.get("certification_number"),
        "graded_population": listing.get("graded_population"),
        "population_higher": listing.get("population_higher"),
        "in_stock": listing.get("in_stock"),
        "stock_status": listing.get("stock_status"),
        "url": listing.get("url"),
        "image_url": listing.get("image_url"),
        "exact_card_number_match": listing.get("exact_card_number_match", True),
    }

    if _latest_listing_matches(conn, values):
        logger.debug(
            "Skipping duplicate listing: card_number=%s marketplace=%s url=%s",
            card_number,
            marketplace,
            listing.get("url"),
        )
        return False

    conn.execute(insert(listings).values(**values))
    return True


def _latest_listing_matches(conn, values):
    from database.models import listings

    query = (
        select(
            listings.c.price,
            listings.c.currency,
            listings.c.in_stock,
            listings.c.stock_status,
            listings.c.image_url,
        )
        .where(listings.c.card_number == values["card_number"])
        .where(listings.c.marketplace == values["marketplace"])
        .where(listings.c.url == values["url"])
        .where(listings.c.condition == values["condition"])
        .where(listings.c.listing_type == values["listing_type"])
        .where(listings.c.grading_company == values["grading_company"])
        .where(listings.c.grade == values["grade"])
        .where(listings.c.certification_number == values["certification_number"])
        .order_by(listings.c.timestamp.desc())
        .limit(1)
    )
    latest = conn.execute(query).mappings().first()

    if not latest:
        return False

    return all(
        latest[key] == values[key]
        for key in ("price", "currency", "in_stock", "stock_status", "image_url")
    )


def save_listings(card_number, results_by_marketplace):
    """Save all normalized listings for a card search."""
    create_db_and_tables()

    with engine.begin() as conn:
        card_id = _get_or_create_card(conn, card_number, results_by_marketplace)
        saved_count = 0

        for marketplace, listing in _iter_marketplace_listings(results_by_marketplace):
            if save_listing(conn, card_id, card_number, marketplace, listing):
                saved_count += 1

    logger.info("Saved %s listings for card_number=%s", saved_count, card_number)
    return saved_count


def save_search_results(card_number, results_by_marketplace):
    """Persist search results without breaking the API if storage fails."""
    try:
        return save_listings(card_number, results_by_marketplace)
    except Exception:
        logger.exception("Failed to save listings for card_number=%s", card_number)
        return 0


def get_price_history(card_number, limit=250):
    """Return timestamped marketplace listing prices for a card."""
    create_db_and_tables()

    from database.models import listings

    query = (
        select(
            listings.c.card_number,
            listings.c.card_name,
            listings.c.marketplace,
            listings.c.condition,
            listings.c.price,
            listings.c.currency,
            listings.c.image_url,
            listings.c.listing_type,
            listings.c.grading_company,
            listings.c.grade,
            listings.c.certification_number,
            listings.c.graded_population,
            listings.c.population_higher,
            listings.c.timestamp,
        )
        .where(listings.c.card_number == card_number)
        .where(listings.c.price.is_not(None))
        .order_by(listings.c.timestamp.asc())
        .limit(limit)
    )

    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [
        {
            **dict(row),
            "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
        }
        for row in rows
    ]


def get_tracked_card_numbers():
    """Return card numbers that should be refreshed by scheduled scrapes."""
    create_db_and_tables()

    from database.models import cards

    with engine.connect() as conn:
        rows = conn.execute(select(cards.c.card_number).order_by(cards.c.card_number)).scalars().all()

    return list(rows)
