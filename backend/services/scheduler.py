"""Simple background scheduler for tracked card price refreshes."""

import asyncio
import logging

from database.database import get_tracked_card_numbers
from services.scraping import scrape_and_save_card


logger = logging.getLogger(__name__)

SCRAPE_INTERVAL_SECONDS = 6 * 60 * 60

_scheduler_task = None
_scrape_lock = asyncio.Lock()


async def run_scheduled_scrape():
    """Refresh every tracked card once, skipping overlapping runs."""
    if _scrape_lock.locked():
        logger.info("Scheduled scrape already running; skipping overlap")
        return {"tracked_cards": 0, "saved_listings": 0, "skipped": True}

    async with _scrape_lock:
        tracked_cards = get_tracked_card_numbers()
        saved_listings = 0

        if not tracked_cards:
            logger.info("Scheduled scrape skipped because no cards are tracked yet")
            return {"tracked_cards": 0, "saved_listings": 0, "skipped": False}

        logger.info("Starting scheduled scrape for %s tracked cards", len(tracked_cards))

        for card_number in tracked_cards:
            try:
                result = await scrape_and_save_card(card_number)
                saved_listings += result["saved_count"]
            except Exception:
                logger.exception("Scheduled scrape failed for card_number=%s", card_number)

        logger.info(
            "Finished scheduled scrape: tracked_cards=%s saved_listings=%s",
            len(tracked_cards),
            saved_listings,
        )
        return {
            "tracked_cards": len(tracked_cards),
            "saved_listings": saved_listings,
            "skipped": False,
        }


async def _scheduler_loop():
    while True:
        await asyncio.sleep(SCRAPE_INTERVAL_SECONDS)
        await run_scheduled_scrape()


def start_scheduler():
    """Start the 6-hour scraping scheduler once per app process."""
    global _scheduler_task

    if _scheduler_task and not _scheduler_task.done():
        return _scheduler_task

    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Scheduled scraping started; interval=%s seconds", SCRAPE_INTERVAL_SECONDS)
    return _scheduler_task


def stop_scheduler():
    """Stop the background scheduler task."""
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
