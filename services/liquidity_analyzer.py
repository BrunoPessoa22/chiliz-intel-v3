"""
PILLAR 5: Liquidity/Order Book Depth Analyzer
Analyzes market depth and calculates slippage estimates
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import coingecko_config
from services.database import Database, get_token_id, get_exchange_id, get_all_tokens

logger = logging.getLogger(__name__)


class LiquidityAnalyzer:
    """Analyzes order book depth and liquidity"""

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
        """Fetch tickers with depth data (cost to move price)"""
        url = f"{self.base_url}/coins/{coingecko_id}/tickers"
        params = {
            "depth": "true",
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

    def calculate_slippage(self, depth_usd: float, trade_size: float) -> float:
        """
        Estimate slippage for a given trade size based on available depth.
        Simple linear model: slippage increases as trade size approaches depth.
        """
        if depth_usd <= 0:
            return 100.0  # 100% slippage if no liquidity

        # Slippage estimation: trade_size / depth * scaling_factor
        # Scaling factor to convert to percentage
        slippage_pct = (trade_size / depth_usd) * 50
        return min(slippage_pct, 100.0)  # Cap at 100%

    async def collect_liquidity_data(self, token: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Collect liquidity data for a token across exchanges"""
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

            # CoinGecko provides cost_to_move_up_usd and cost_to_move_down_usd
            # This represents liquidity available at ±2% from current price
            cost_to_move_up = float(ticker.get("cost_to_move_up_usd") or 0)
            cost_to_move_down = float(ticker.get("cost_to_move_down_usd") or 0)

            # Use cost_to_move as proxy for depth at 2%
            bid_depth_2pct = cost_to_move_down
            ask_depth_2pct = cost_to_move_up

            # Estimate depths at other levels (rough approximations)
            # Assuming linear depth distribution
            bid_depth_1pct = bid_depth_2pct * 0.5
            ask_depth_1pct = ask_depth_2pct * 0.5
            bid_depth_5pct = bid_depth_2pct * 2.5
            ask_depth_5pct = ask_depth_2pct * 2.5

            total_bid_depth = bid_depth_5pct
            total_ask_depth = ask_depth_5pct

            # Calculate slippage for standard trade sizes
            slippage_buy_1k = self.calculate_slippage(ask_depth_1pct, 1000)
            slippage_buy_10k = self.calculate_slippage(ask_depth_2pct, 10000)
            slippage_buy_50k = self.calculate_slippage(ask_depth_5pct, 50000)
            slippage_sell_1k = self.calculate_slippage(bid_depth_1pct, 1000)
            slippage_sell_10k = self.calculate_slippage(bid_depth_2pct, 10000)
            slippage_sell_50k = self.calculate_slippage(bid_depth_5pct, 50000)

            # Order book imbalance: (bid - ask) / (bid + ask)
            total_depth = total_bid_depth + total_ask_depth
            if total_depth > 0:
                book_imbalance = (total_bid_depth - total_ask_depth) / total_depth
            else:
                book_imbalance = 0

            results.append({
                "time": now,
                "token_id": token_id,
                "exchange_id": exchange_id,
                "bid_depth_1pct": bid_depth_1pct,
                "ask_depth_1pct": ask_depth_1pct,
                "bid_depth_2pct": bid_depth_2pct,
                "ask_depth_2pct": ask_depth_2pct,
                "bid_depth_5pct": bid_depth_5pct,
                "ask_depth_5pct": ask_depth_5pct,
                "total_bid_depth": total_bid_depth,
                "total_ask_depth": total_ask_depth,
                "slippage_buy_1k": slippage_buy_1k,
                "slippage_buy_10k": slippage_buy_10k,
                "slippage_buy_50k": slippage_buy_50k,
                "slippage_sell_1k": slippage_sell_1k,
                "slippage_sell_10k": slippage_sell_10k,
                "slippage_sell_50k": slippage_sell_50k,
                "book_imbalance": book_imbalance,
            })

        return results

    async def collect_all(self) -> int:
        """Collect liquidity data for all tokens"""
        tokens = await get_all_tokens()
        all_data = []

        for token in tokens:
            data = await self.collect_liquidity_data(token)
            all_data.extend(data)
            await asyncio.sleep(2)

        if all_data:
            await self._insert_liquidity_data(all_data)

        logger.info(f"Collected {len(all_data)} liquidity records")
        return len(all_data)

    async def _insert_liquidity_data(self, data: List[Dict[str, Any]]):
        """Batch insert liquidity data"""
        query = """
            INSERT INTO liquidity_snapshots
            (time, token_id, exchange_id, bid_depth_1pct, ask_depth_1pct,
             bid_depth_2pct, ask_depth_2pct, bid_depth_5pct, ask_depth_5pct,
             total_bid_depth, total_ask_depth, slippage_buy_1k, slippage_buy_10k,
             slippage_buy_50k, slippage_sell_1k, slippage_sell_10k, slippage_sell_50k,
             book_imbalance)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            ON CONFLICT (time, token_id, exchange_id) DO UPDATE SET
                bid_depth_1pct = EXCLUDED.bid_depth_1pct,
                ask_depth_1pct = EXCLUDED.ask_depth_1pct,
                total_bid_depth = EXCLUDED.total_bid_depth,
                total_ask_depth = EXCLUDED.total_ask_depth,
                book_imbalance = EXCLUDED.book_imbalance
        """

        args = [
            (
                d["time"], d["token_id"], d["exchange_id"], d["bid_depth_1pct"],
                d["ask_depth_1pct"], d["bid_depth_2pct"], d["ask_depth_2pct"],
                d["bid_depth_5pct"], d["ask_depth_5pct"], d["total_bid_depth"],
                d["total_ask_depth"], d["slippage_buy_1k"], d["slippage_buy_10k"],
                d["slippage_buy_50k"], d["slippage_sell_1k"], d["slippage_sell_10k"],
                d["slippage_sell_50k"], d["book_imbalance"]
            )
            for d in data
        ]

        await Database.executemany(query, args)


async def run_analyzer():
    """Main analysis loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["liquidity"]
    logger.info(f"Starting liquidity analyzer (interval: {interval}s)")

    while True:
        try:
            async with LiquidityAnalyzer() as analyzer:
                count = await analyzer.collect_all()
                logger.info(f"Liquidity analysis complete: {count} records")
        except Exception as e:
            logger.error(f"Liquidity analysis error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_analyzer())
