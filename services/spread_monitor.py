"""
PILLAR 4: Spread Data Monitor
Tracks bid-ask spreads across exchanges via CoinGecko Pro
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import coingecko_config
from services.database import Database, get_token_id, get_exchange_id, get_all_tokens

logger = logging.getLogger(__name__)


class SpreadMonitor:
    """Monitors bid-ask spreads across exchanges"""

    def __init__(self):
        self.api_key = coingecko_config.api_key
        self.base_url = coingecko_config.base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "x-cg-pro-api-key": self.api_key,
                "Accept": "application/json",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_coin_tickers(self, coingecko_id: str) -> List[Dict[str, Any]]:
        """Fetch tickers with depth data"""
        url = f"{self.base_url}/coins/{coingecko_id}/tickers"
        params = {
            "depth": "true",
            "order": "volume_desc",
        }

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("tickers", [])
                return []
        except Exception as e:
            logger.error(f"Error fetching tickers for {coingecko_id}: {e}")
            return []

    async def collect_spread_data(self, token: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect spread data for a token across exchanges"""
        coingecko_id = token.get("coingecko_id")
        if not coingecko_id:
            return []

        token_id = await get_token_id(token["symbol"])
        if not token_id:
            return []

        tickers = await self.fetch_coin_tickers(coingecko_id)
        now = datetime.now(timezone.utc)

        results = []
        for ticker in tickers:
            exchange_id_str = ticker.get("market", {}).get("identifier", "")
            exchange_id = await get_exchange_id(exchange_id_str)

            if not exchange_id:
                continue

            # Extract bid/ask data
            cost_to_move = ticker.get("cost_to_move_up_usd") or ticker.get("cost_to_move_down_usd")
            bid_ask_spread_pct = ticker.get("bid_ask_spread_percentage", 0)

            # Calculate best bid/ask from last price and spread
            last_price = float(ticker.get("last", 0))
            if last_price > 0 and bid_ask_spread_pct:
                spread_decimal = float(bid_ask_spread_pct) / 100
                half_spread = spread_decimal / 2
                best_bid = last_price * (1 - half_spread)
                best_ask = last_price * (1 + half_spread)
                spread_absolute = best_ask - best_bid
                spread_bps = float(bid_ask_spread_pct) * 100  # Convert % to bps
                mid_price = (best_bid + best_ask) / 2
            else:
                best_bid = last_price
                best_ask = last_price
                spread_absolute = 0
                spread_bps = 0
                mid_price = last_price

            results.append({
                "time": now,
                "token_id": token_id,
                "exchange_id": exchange_id,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread_absolute": spread_absolute,
                "spread_percentage": bid_ask_spread_pct or 0,
                "spread_bps": spread_bps,
                "mid_price": mid_price,
            })

        return results

    async def collect_all(self) -> int:
        """Collect spread data for all tokens"""
        tokens = await get_all_tokens()
        all_data = []

        for token in tokens:
            data = await self.collect_spread_data(token)
            all_data.extend(data)
            await asyncio.sleep(2)  # Rate limiting

        if all_data:
            await self._insert_spread_data(all_data)

        logger.info(f"Collected {len(all_data)} spread records")
        return len(all_data)

    async def _insert_spread_data(self, data: List[Dict[str, Any]]):
        """Batch insert spread data"""
        query = """
            INSERT INTO spread_ticks
            (time, token_id, exchange_id, best_bid, best_ask,
             spread_absolute, spread_percentage, spread_bps, mid_price)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (time, token_id, exchange_id) DO UPDATE SET
                best_bid = EXCLUDED.best_bid,
                best_ask = EXCLUDED.best_ask,
                spread_absolute = EXCLUDED.spread_absolute,
                spread_percentage = EXCLUDED.spread_percentage,
                spread_bps = EXCLUDED.spread_bps,
                mid_price = EXCLUDED.mid_price
        """

        args = [
            (
                d["time"], d["token_id"], d["exchange_id"], d["best_bid"],
                d["best_ask"], d["spread_absolute"], d["spread_percentage"],
                d["spread_bps"], d["mid_price"]
            )
            for d in data
        ]

        await Database.executemany(query, args)


async def run_monitor():
    """Main monitoring loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["spread"]
    logger.info(f"Starting spread monitor (interval: {interval}s)")

    while True:
        try:
            async with SpreadMonitor() as monitor:
                count = await monitor.collect_all()
                logger.info(f"Spread collection complete: {count} records")
        except Exception as e:
            logger.error(f"Spread monitoring error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_monitor())
