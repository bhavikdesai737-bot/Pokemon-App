"""Compare normalized marketplace price results."""

import logging


logger = logging.getLogger(__name__)


def get_lowest_price(marketplaces):
    priced_results = [
        {
            "marketplace": marketplace,
            **result,
        }
        for marketplace, result in (marketplaces or {}).items()
        if isinstance(result, dict) and isinstance(result.get("price"), int)
    ]

    if not priced_results:
        logger.info("No marketplace prices available for comparison")
        return None

    lowest = min(priced_results, key=lambda result: result["price"])
    logger.debug("Lowest marketplace price: %s", lowest)
    return lowest
