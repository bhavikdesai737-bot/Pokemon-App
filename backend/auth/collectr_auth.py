"""Collectr Playwright login and storage-state helpers."""

import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


logger = logging.getLogger(__name__)

COLLECTR_URL = "https://app.getcollectr.com"
AUTH_DIR = Path(__file__).resolve().parent
COLLECTR_STATE_PATH = AUTH_DIR / "collectr_state.json"
LOGIN_INSTRUCTIONS = (
    "Collectr login required: run `venv\\Scripts\\python.exe save_collectr_login.py` "
    "from the backend folder, log in manually, then press Enter to save the session."
)


class CollectrAuthError(RuntimeError):
    """Raised when Collectr needs a fresh logged-in Playwright session."""


def get_collectr_storage_state_path():
    """Return the Collectr storage-state path when it contains saved session data."""
    if not COLLECTR_STATE_PATH.exists():
        logger.warning("Collectr storage state file is missing: %s", COLLECTR_STATE_PATH)
        return None

    if COLLECTR_STATE_PATH.stat().st_size <= 0:
        logger.warning("Collectr storage state file is empty: %s", COLLECTR_STATE_PATH)
        return None

    try:
        state = json.loads(COLLECTR_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Collectr storage state file is invalid JSON: %s", COLLECTR_STATE_PATH)
        return None

    has_cookies = bool(state.get("cookies"))
    has_origins = bool(state.get("origins"))
    if not has_cookies and not has_origins:
        logger.warning("Collectr storage state has no saved login data: %s", COLLECTR_STATE_PATH)
        return None

    logger.info("Collectr storage state validated: %s", COLLECTR_STATE_PATH)
    return str(COLLECTR_STATE_PATH)


def require_collectr_storage_state_path():
    """Return a saved Collectr storage-state path or raise a clear login error."""
    storage_state = get_collectr_storage_state_path()
    if storage_state:
        return storage_state

    raise CollectrAuthError(LOGIN_INSTRUCTIONS)


async def save_collectr_auth_state():
    """Open Collectr visibly, wait for manual login, then save storage state."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    logger.info("Opening Collectr for manual login: %s", COLLECTR_URL)
    logger.info("After logging in, return to this terminal and press Enter to save the session.")
    AUTH_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(COLLECTR_URL, wait_until="domcontentloaded", timeout=60_000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15_000)
            except PlaywrightTimeoutError:
                logger.info("Collectr page did not reach networkidle; continuing with manual login.")

            await asyncio.to_thread(input, "Press Enter after you finish logging in to Collectr...")
            await context.storage_state(path=str(COLLECTR_STATE_PATH))
            logger.info("Saved Collectr auth state to %s", COLLECTR_STATE_PATH)

            if get_collectr_storage_state_path() is None:
                logger.warning("Saved Collectr state is still empty. Make sure you logged in before pressing Enter.")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(save_collectr_auth_state())
