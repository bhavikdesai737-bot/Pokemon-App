"""Open Collectr for manual login and save Playwright storage state."""

import asyncio

from auth.collectr_auth import save_collectr_auth_state


if __name__ == "__main__":
    asyncio.run(save_collectr_auth_state())
