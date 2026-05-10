"""Shared scraping orchestration for live and scheduled price refreshes."""

import asyncio
import logging

from database.database import save_search_results
from scrapers.cardladder import get_cardladder_prices
from scrapers.collectr import get_collectr_prices
from scrapers.cardrush import get_cardrush_price
from scrapers.hareruya import get_hareruya_price
from services.normalize import normalize_card_number, normalize_store_result


logger = logging.getLogger(__name__)


async def _safe_graded_scrape(source, scrape_func, card_number):
    try:
        return await scrape_func(card_number)
    except Exception:
        logger.exception("%s graded scrape failed for %s", source, card_number)
        return []


async def scrape_card_prices(card_number):
    """Scrape all configured marketplaces and return normalized results."""
    normalized_card_number = normalize_card_number(card_number)

    cardrush, hareruya = await asyncio.gather(
        asyncio.to_thread(get_cardrush_price, normalized_card_number),
        asyncio.to_thread(get_hareruya_price, normalized_card_number),
    )
    cardladder, collectr = await asyncio.gather(
        _safe_graded_scrape("CardLadder", get_cardladder_prices, card_number),
        _safe_graded_scrape("Collectr", get_collectr_prices, card_number),
    )

    japan_results = {
        "cardrush": normalize_store_result("cardrush", cardrush),
        "hareruya": normalize_store_result("hareruya", hareruya),
    }
    graded_results = {
        "cardladder": normalize_store_result("cardladder", cardladder),
        "collectr": normalize_store_result("collectr", collectr),
    }

    return normalized_card_number, {
        "japan": japan_results,
        "graded": graded_results,
    }


async def scrape_and_save_card(card_number):
    """Scrape one tracked card and persist any new price snapshots."""
    normalized_card_number, grouped_results = await scrape_card_prices(card_number)
    saveable_results = {
        **grouped_results["japan"],
        **grouped_results["graded"],
    }
    saved_count = await asyncio.to_thread(save_search_results, normalized_card_number, saveable_results)
    logger.info(
        "Scraped %s and saved %s new listing snapshots",
        normalized_card_number,
        saved_count,
    )

    return {
        "card_number": normalized_card_number,
        "japan": grouped_results["japan"],
        "graded": grouped_results["graded"],
        "saved_count": saved_count,
    }


def scrape_and_save_card_sync(card_number):
    """Synchronous wrapper for scripts or legacy callers."""
    return asyncio.run(scrape_and_save_card(card_number))
