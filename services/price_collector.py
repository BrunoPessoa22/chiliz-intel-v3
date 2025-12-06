"""
PILLAR 1 & 2: Price and Volume Data Collector
Uses CoinGecko Pro API BATCH endpoint to minimize API calls
Only tracks TOP 20 tokens to save credits
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import coingecko_config, TOP_20_COINGECKO_IDS
from services.database import Database, get_token_id, get_exchange_id

logger = logging.getLogger(__name__)


class PriceVolumeCollector:
    """Collects price and volume data using CoinGecko BATCH endpoint"""

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

    async def fetch_batch_market_data(self) -> List[Dict[str, Any]]:
        """
        Fetch market data for ALL top 20 tokens in ONE API call.
        Uses /coins/markets endpoint which returns price, volume, market cap, 24h change.
        """
        url = f"{self.base_url}/coins/markets"

        # Join all coingecko IDs into comma-separated string
        ids = ",".join(TOP_20_COINGECKO_IDS)

        params = {
            "vs_currency": "usd",
            "ids": ids,
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d",
        }

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"Batch fetch successful: {len(data)} tokens")
                    return data
                else:
                    error_text = await resp.text()
                    logger.warning(f"CoinGecko batch API error: {resp.status} - {error_text[:200]}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching batch market data: {e}")
            return []

    async def collect_all(self) -> int:
        """Collect price/volume data for top 20 tokens in ONE API call"""

        # Single batch API call for all tokens
        market_data = await self.fetch_batch_market_data()

        if not market_data:
            logger.warning("No market data returned from batch API")
            return 0

        now = datetime.now(timezone.utc)
        all_data = []

        # Map coingecko_id to symbol for our tokens
        id_to_symbol = {
            "chiliz": "CHZ",
            "fc-barcelona-fan-token": "BAR",
            "paris-saint-germain-fan-token": "PSG",
            "juventus-fan-token": "JUV",
            "manchester-city-fan-token": "CITY",
            "ac-milan-fan-token": "ACM",
            "inter-milan-fan-token": "INTER",
            "atletico-madrid": "ATM",
            "arsenal-fan-token": "AFC",
            "as-roma-fan-token": "ASR",
            "napoli-fan-token": "NAP",
            "galatasaray-fan-token": "GAL",
            "flamengo-fan-token": "MENGO",
            "tottenham-hotspur-fc-fan-token": "SPURS",
            "argentine-football-association-fan-token": "ARG",
            "sl-benfica-fan-token": "BENFICA",
            "s-c-corinthians-fan-token": "SCCP",
            "og-fan-token": "OG",
            "ufc-fan-token": "UFC",
            "santos-fc-fan-token": "SANTOS",
        }

        for coin in market_data:
            coingecko_id = coin.get("id")
            symbol = id_to_symbol.get(coingecko_id)

            if not symbol:
                continue

            token_id = await get_token_id(symbol)
            if not token_id:
                logger.warning(f"Token ID not found for {symbol}")
                continue

            # Get "aggregate" exchange ID (for overall market data)
            exchange_id = await get_exchange_id("aggregate")
            if not exchange_id:
                # Try binance as fallback
                exchange_id = await get_exchange_id("binance")

            if not exchange_id:
                continue

            price = float(coin.get("current_price") or 0)
            volume_24h = float(coin.get("total_volume") or 0)
            price_change_1h = float(coin.get("price_change_percentage_1h_in_currency") or 0)
            price_change_24h = float(coin.get("price_change_percentage_24h") or 0)
            high_24h = float(coin.get("high_24h") or 0)
            low_24h = float(coin.get("low_24h") or 0)
            market_cap = float(coin.get("market_cap") or 0)

            if price <= 0:
                continue

            all_data.append({
                "time": now,
                "token_id": token_id,
                "exchange_id": exchange_id,
                "price": price,
                "price_change_1h": price_change_1h,
                "price_change_24h": price_change_24h,
                "volume_24h": volume_24h,
                "volume_base_24h": volume_24h / price if price > 0 else 0,
                "trade_count_24h": None,
                "high_price": high_24h,
                "low_price": low_24h,
            })

            logger.debug(f"Collected {symbol}: ${price:.4f}, vol: ${volume_24h:,.0f}")

        # Batch insert
        if all_data:
            await self._insert_price_volume_data(all_data)

        logger.info(f"Collected {len(all_data)} price/volume records (1 API call)")
        return len(all_data)

    async def _insert_price_volume_data(self, data: List[Dict[str, Any]]):
        """Batch insert price/volume data"""
        query = """
            INSERT INTO price_volume_ticks
            (time, token_id, exchange_id, price, price_change_1h, price_change_24h,
             volume_24h, volume_base_24h, trade_count_24h, high_price, low_price)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (time, token_id, exchange_id) DO UPDATE SET
                price = EXCLUDED.price,
                price_change_1h = EXCLUDED.price_change_1h,
                price_change_24h = EXCLUDED.price_change_24h,
                volume_24h = EXCLUDED.volume_24h,
                volume_base_24h = EXCLUDED.volume_base_24h,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price
        """

        args = [
            (
                d["time"], d["token_id"], d["exchange_id"], d["price"],
                d["price_change_1h"], d["price_change_24h"], d["volume_24h"],
                d["volume_base_24h"], d["trade_count_24h"], d["high_price"], d["low_price"]
            )
            for d in data
        ]

        await Database.executemany(query, args)


async def run_collector():
    """Main collection loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["price_volume"]
    logger.info(f"Starting price/volume collector (interval: {interval}s, TOP 20 tokens, BATCH mode)")

    while True:
        try:
            async with PriceVolumeCollector() as collector:
                count = await collector.collect_all()
                logger.info(f"Price/volume collection complete: {count} records")
        except Exception as e:
            logger.error(f"Price/volume collection error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_collector())
