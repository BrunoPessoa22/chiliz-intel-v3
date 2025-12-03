"""
Aggregator Service
Combines data from all exchanges into unified token metrics
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.database import Database, get_all_tokens

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Aggregates metrics across all exchanges into unified view"""

    async def aggregate_token_metrics(self, token_id: int) -> Optional[Dict[str, Any]]:
        """Aggregate all metrics for a single token"""
        now = datetime.now(timezone.utc)

        # Get latest price/volume data aggregated across exchanges
        pv_query = """
            SELECT
                SUM(price * volume_24h) / NULLIF(SUM(volume_24h), 0) as vwap_price,
                SUM(volume_24h) as total_volume_24h,
                SUM(trade_count_24h) as total_trade_count_24h,
                COUNT(DISTINCT exchange_id) as active_exchanges
            FROM price_volume_ticks
            WHERE token_id = $1
              AND time > NOW() - INTERVAL '5 minutes'
        """
        pv_row = await Database.fetchrow(pv_query, token_id)

        if not pv_row or not pv_row["vwap_price"]:
            return None

        # Get price changes
        price_change_query = """
            WITH current AS (
                SELECT AVG(price) as price
                FROM price_volume_ticks
                WHERE token_id = $1 AND time > NOW() - INTERVAL '5 minutes'
            ),
            hour_ago AS (
                SELECT AVG(price) as price
                FROM price_volume_ticks
                WHERE token_id = $1 AND time BETWEEN NOW() - INTERVAL '65 minutes' AND NOW() - INTERVAL '55 minutes'
            ),
            day_ago AS (
                SELECT AVG(price) as price
                FROM price_volume_ticks
                WHERE token_id = $1 AND time BETWEEN NOW() - INTERVAL '25 hours' AND NOW() - INTERVAL '23 hours'
            ),
            week_ago AS (
                SELECT AVG(price) as price
                FROM price_volume_ticks
                WHERE token_id = $1 AND time BETWEEN NOW() - INTERVAL '7 days 1 hour' AND NOW() - INTERVAL '7 days'
            )
            SELECT
                ((c.price - h.price) / NULLIF(h.price, 0)) * 100 as change_1h,
                ((c.price - d.price) / NULLIF(d.price, 0)) * 100 as change_24h,
                ((c.price - w.price) / NULLIF(w.price, 0)) * 100 as change_7d
            FROM current c, hour_ago h, day_ago d, week_ago w
        """
        change_row = await Database.fetchrow(price_change_query, token_id)

        # Get holder data
        holder_query = """
            SELECT total_holders, holder_change_24h
            FROM holder_snapshots
            WHERE token_id = $1
            ORDER BY time DESC LIMIT 1
        """
        holder_row = await Database.fetchrow(holder_query, token_id)

        # Get aggregated spread (volume-weighted average)
        spread_query = """
            SELECT
                SUM(spread_bps * COALESCE(pv.volume_24h, 1)) / NULLIF(SUM(COALESCE(pv.volume_24h, 1)), 0) as avg_spread_bps
            FROM spread_ticks st
            LEFT JOIN price_volume_ticks pv ON st.token_id = pv.token_id
                AND st.exchange_id = pv.exchange_id
                AND st.time = pv.time
            WHERE st.token_id = $1 AND st.time > NOW() - INTERVAL '5 minutes'
        """
        spread_row = await Database.fetchrow(spread_query, token_id)

        # Get aggregated liquidity
        liquidity_query = """
            SELECT SUM(bid_depth_1pct + ask_depth_1pct) as total_liquidity_1pct
            FROM liquidity_snapshots
            WHERE token_id = $1 AND time > NOW() - INTERVAL '10 minutes'
        """
        liquidity_row = await Database.fetchrow(liquidity_query, token_id)

        # Get market cap from fan_tokens table
        market_cap_query = """
            SELECT circulating_supply FROM fan_tokens WHERE id = $1
        """
        supply = await Database.fetchval(market_cap_query, token_id)
        market_cap = float(pv_row["vwap_price"] or 0) * float(supply or 0)

        return {
            "time": now,
            "token_id": token_id,
            "vwap_price": float(pv_row["vwap_price"] or 0),
            "price_change_1h": float(change_row["change_1h"] or 0) if change_row else None,
            "price_change_24h": float(change_row["change_24h"] or 0) if change_row else None,
            "price_change_7d": float(change_row["change_7d"] or 0) if change_row else None,
            "total_volume_24h": float(pv_row["total_volume_24h"] or 0),
            "total_trade_count_24h": int(pv_row["total_trade_count_24h"] or 0),
            "market_cap": market_cap,
            "total_holders": int(holder_row["total_holders"] or 0) if holder_row else None,
            "holder_change_24h": int(holder_row["holder_change_24h"] or 0) if holder_row else None,
            "total_liquidity_1pct": float(liquidity_row["total_liquidity_1pct"] or 0) if liquidity_row else 0,
            "avg_spread_bps": float(spread_row["avg_spread_bps"] or 0) if spread_row else None,
            "health_score": None,  # Calculated separately
            "health_grade": None,
            "active_exchanges": int(pv_row["active_exchanges"] or 0),
        }

    async def aggregate_all(self) -> int:
        """Aggregate metrics for all tokens"""
        tokens = await get_all_tokens()
        all_data = []

        for token in tokens:
            data = await self.aggregate_token_metrics(token["id"])
            if data:
                all_data.append(data)

        if all_data:
            await self._insert_aggregated_data(all_data)

        logger.info(f"Aggregated metrics for {len(all_data)} tokens")
        return len(all_data)

    async def _insert_aggregated_data(self, data: List[Dict[str, Any]]):
        """Batch insert aggregated data"""
        query = """
            INSERT INTO token_metrics_aggregated
            (time, token_id, vwap_price, price_change_1h, price_change_24h, price_change_7d,
             total_volume_24h, total_trade_count_24h, market_cap, total_holders,
             holder_change_24h, total_liquidity_1pct, avg_spread_bps, health_score,
             health_grade, active_exchanges)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            ON CONFLICT (time, token_id) DO UPDATE SET
                vwap_price = EXCLUDED.vwap_price,
                total_volume_24h = EXCLUDED.total_volume_24h,
                avg_spread_bps = EXCLUDED.avg_spread_bps,
                total_liquidity_1pct = EXCLUDED.total_liquidity_1pct
        """

        args = [
            (
                d["time"], d["token_id"], d["vwap_price"], d["price_change_1h"],
                d["price_change_24h"], d["price_change_7d"], d["total_volume_24h"],
                d["total_trade_count_24h"], d["market_cap"], d["total_holders"],
                d["holder_change_24h"], d["total_liquidity_1pct"], d["avg_spread_bps"],
                d["health_score"], d["health_grade"], d["active_exchanges"]
            )
            for d in data
        ]

        await Database.executemany(query, args)


async def run_aggregator():
    """Main aggregation loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["aggregation"]
    logger.info(f"Starting metrics aggregator (interval: {interval}s)")

    while True:
        try:
            aggregator = MetricsAggregator()
            count = await aggregator.aggregate_all()
            logger.info(f"Aggregation complete: {count} tokens")
        except Exception as e:
            logger.error(f"Aggregation error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_aggregator())
