import asyncio
import logging
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.database import (
    create_db_and_tables,
    get_cached_search_result,
    get_price_history,
    save_search_cache,
)
from auth.collectr_auth import CollectrAuthError
from scrapers.collectr import CollectrScrapeError, get_collectr_prices
from services.scheduler import run_scheduled_scrape, start_scheduler, stop_scheduler
from services.scraping import scrape_and_save_card
from services.normalize import normalize_card_number

logging.basicConfig(level=logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    create_db_and_tables()
    start_scheduler()


@app.on_event("shutdown")
def shutdown():
    stop_scheduler()


@app.get("/")
def root():
    return {"message": "Pokemon price app running"}


@app.get("/health")
def healthcheck():
    return {
        "status": "ok",
        "service": "pokemon-price-backend",
        "port": 8002,
    }


async def build_search_response(card_number: str):
    normalized_card_number = normalize_card_number(card_number)
    cached_result = await asyncio.to_thread(get_cached_search_result, normalized_card_number)
    if cached_result:
        return cached_result

    result = await scrape_and_save_card(normalized_card_number)

    response = {
        "card_number": result["card_number"],
        "japan": result["japan"],
        "graded": result["graded"],
    }
    await asyncio.to_thread(save_search_cache, normalized_card_number, response)
    return response


@app.get("/search")
async def search_card_query(card_number: str):
    try:
        return await build_search_response(card_number)
    except Exception as exc:
        logger.exception("Search failed for card_number=%s", card_number)
        return JSONResponse(
            status_code=500,
            content={"error": type(exc).__name__, "detail": str(exc)},
        )


@app.get("/search/{card_number}")
async def search_card(card_number: str):
    try:
        return await build_search_response(card_number)
    except Exception as exc:
        logger.exception("Search failed for card_number=%s", card_number)
        return JSONResponse(
            status_code=500,
            content={"error": type(exc).__name__, "detail": str(exc)},
        )


@app.get("/debug/collectr/{card_number}")
async def debug_collectr(card_number: str):
    normalized_card_number = normalize_card_number(card_number)
    logger.info("Starting Collectr debug scrape for card_number=%s", normalized_card_number)

    try:
        result = await get_collectr_prices(normalized_card_number)
        logger.info(
            "Finished Collectr debug scrape for card_number=%s result_count=%s",
            normalized_card_number,
            len(result) if isinstance(result, list) else "unknown",
        )
        return result
    except CollectrAuthError as exc:
        logger.warning("Collectr debug authentication error for card_number=%s: %s", normalized_card_number, exc)
        return JSONResponse(
            status_code=401,
            content={
                "error": "Collectr authentication required",
                "type": type(exc).__name__,
                "detail": str(exc),
                "card_number": normalized_card_number,
                "current_url": getattr(exc, "current_url", None),
            },
        )
    except CollectrScrapeError as exc:
        logger.exception("Collectr debug scrape error for card_number=%s", normalized_card_number)
        return JSONResponse(
            status_code=502,
            content={
                "error": "Collectr scrape failed",
                "type": type(exc).__name__,
                "detail": str(exc),
                "card_number": normalized_card_number,
                "current_url": getattr(exc, "current_url", None),
            },
        )
    except Exception as exc:
        logger.exception("Collectr debug scrape failed for card_number=%s", normalized_card_number)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Collectr scrape failed",
                "type": type(exc).__name__,
                "detail": str(exc),
                "card_number": normalized_card_number,
                "current_url": getattr(exc, "current_url", None),
            },
        )


@app.get("/history/{card_number}")
def price_history(card_number: str):
    normalized_card_number = normalize_card_number(card_number)
    return {
        "card_number": normalized_card_number,
        "history": get_price_history(normalized_card_number),
    }


@app.post("/jobs/scrape")
async def run_scrape_job():
    return await run_scheduled_scrape()
