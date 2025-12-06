"""
PILLAR 1 & 2: Price and Volume Data Collector
Uses CoinGecko Pro API for multi-exchange data
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import coingecko_config, FAN_TOKENS, EXCHANGES
from services.database import Database, get_token_id, get_exchange_id, get_all_tokens

logger = logging.getLogger(__name__)


class PriceVolumeCollector:
    """Collects price and volume data from multiple exchanges via CoinGecko Pro"""

    def __init__(self):
        self.api_key = coingecko_config.api_key
        self.base_url = coingecko_config.base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "Accept": "application/json",
            }
        )
        return self

    def _add_api_key(self, params: dict) -> dict:
        """Add API key to request params"""
        if self.api_key:
            params["x_cg_pro_api_key"] = self.api_key
        return params

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_coin_tickers(self, coingecko_id: str) -> List[Dict[str, Any]]:
        """Fetch all exchange tickers for a coin"""
        url = f"{self.base_url}/coins/{coingecko_id}/tickers"
        params = self._add_api_key({
            "include_exchange_logo": "false",
            "depth": "true",  # Include order book depth
        })

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("tickers", [])
                else:
                    logger.warning(f"CoinGecko API error for {coingecko_id}: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching tickers for {coingecko_id}: {e}")
            return []

    async def fetch_coin_market_data(self, coingecko_id: str) -> Optional[Dict[str, Any]]:
        """Fetch market data including market cap"""
        url = f"{self.base_url}/coins/{coingecko_id}"
        params = self._add_api_key({
            "localization": "false",
            "tickers": "false",
            "community_data": "false",
            "developer_data": "false",
        })

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching market data for {coingecko_id}: {e}")
            return None

    async def collect_token_data(self, token: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect price/volume data for a single token across exchanges"""
        coingecko_id = token.get("coingecko_id")
        if not coingecko_id:
            return []

        token_id = await get_token_id(token["symbol"])
        if not token_id:
            logger.warning(f"Token ID not found for {token['symbol']}")
            return []

        tickers = await self.fetch_coin_tickers(coingecko_id)
        now = datetime.now(timezone.utc)

        results = []
        for ticker in tickers:
            exchange_id_str = ticker.get("market", {}).get("identifier", "")
            exchange_id = await get_exchange_id(exchange_id_str)

            if not exchange_id:
                continue  # Skip exchanges we don't track

            # Extract price and volume data
            # Use converted_last for USD price (handles non-USD quote currencies like TRY, KRW)
            price = float(ticker.get("converted_last", {}).get("usd", 0))
            volume_usd = float(ticker.get("converted_volume", {}).get("usd", 0))
            volume_base = float(ticker.get("volume", 0))

            # Skip if no valid USD price
            if price <= 0:
                continue

            # Extract bid-ask for spread calculation
            bid = float(ticker.get("bid_ask_spread_percentage", 0))

            results.append({
                "time": now,
                "token_id": token_id,
                "exchange_id": exchange_id,
                "price": price,
                "price_change_1h": None,  # Will calculate from historical
                "price_change_24h": None,
                "volume_24h": volume_usd,
                "volume_base_24h": volume_base,
                "trade_count_24h": None,  # CoinGecko doesn't provide this
                "high_price": None,
                "low_price": None,
            })

        return results

    async def collect_all(self) -> int:
        """Collect price/volume data for all tokens"""
        tokens = await get_all_tokens()
        all_data = []

        for token in tokens:
            data = await self.collect_token_data(token)
            all_data.extend(data)
            # Rate limiting: ~30 requests per minute to be safe
            await asyncio.sleep(2)

        # Batch insert
        if all_data:
            await self._insert_price_volume_data(all_data)

        logger.info(f"Collected {len(all_data)} price/volume records")
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
                volume_24h = EXCLUDED.volume_24h,
                volume_base_24h = EXCLUDED.volume_base_24h
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
    logger.info(f"Starting price/volume collector (interval: {interval}s)")

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
