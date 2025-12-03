"""
Health Scoring System
Calculates comprehensive health scores (0-100) for fan tokens
Based on Five Pillars: Price, Volume, Holders, Spread, Liquidity
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config.settings import HEALTH_SCORE_CONFIG
from services.database import Database, get_all_tokens

logger = logging.getLogger(__name__)


class HealthScorer:
    """Calculates health scores for fan tokens"""

    def __init__(self):
        self.weights = HEALTH_SCORE_CONFIG["weights"]
        self.thresholds = HEALTH_SCORE_CONFIG["thresholds"]
        self.grades = HEALTH_SCORE_CONFIG["grades"]

    def calculate_grade(self, score: int) -> str:
        """Convert numeric score to letter grade"""
        for grade, (low, high) in self.grades.items():
            if low <= score <= high:
                return grade
        return "F"

    async def get_latest_metrics(self, token_id: int) -> Dict[str, Any]:
        """Get latest metrics for a token from all pillars"""

        # Get latest price/volume from aggregated
        agg_query = """
            SELECT vwap_price, price_change_24h, total_volume_24h, avg_spread_bps,
                   total_liquidity_1pct, active_exchanges
            FROM token_metrics_aggregated
            WHERE token_id = $1
            ORDER BY time DESC LIMIT 1
        """
        agg_row = await Database.fetchrow(agg_query, token_id)

        # Get latest holder data
        holder_query = """
            SELECT total_holders, holder_change_24h, gini_coefficient
            FROM holder_snapshots
            WHERE token_id = $1
            ORDER BY time DESC LIMIT 1
        """
        holder_row = await Database.fetchrow(holder_query, token_id)

        # Get 7-day price volatility
        volatility_query = """
            SELECT STDDEV(price_change_24h) as volatility
            FROM token_metrics_aggregated
            WHERE token_id = $1 AND time > NOW() - INTERVAL '7 days'
        """
        volatility = await Database.fetchval(volatility_query, token_id)

        return {
            "price": float(agg_row["vwap_price"] or 0) if agg_row else 0,
            "price_change_24h": float(agg_row["price_change_24h"] or 0) if agg_row else 0,
            "volume_24h": float(agg_row["total_volume_24h"] or 0) if agg_row else 0,
            "spread_bps": float(agg_row["avg_spread_bps"] or 0) if agg_row else 0,
            "liquidity_1pct": float(agg_row["total_liquidity_1pct"] or 0) if agg_row else 0,
            "active_exchanges": int(agg_row["active_exchanges"] or 0) if agg_row else 0,
            "total_holders": int(holder_row["total_holders"] or 0) if holder_row else 0,
            "holder_change_24h": int(holder_row["holder_change_24h"] or 0) if holder_row else 0,
            "gini_coefficient": float(holder_row["gini_coefficient"] or 0) if holder_row else 0,
            "volatility_7d": float(volatility or 0),
        }

    def score_volume(self, volume_24h: float) -> int:
        """Score volume component (0-100)"""
        if volume_24h >= self.thresholds["volume_24h_excellent"]:
            return 100
        elif volume_24h >= self.thresholds["volume_24h_good"]:
            # Linear interpolation between good and excellent
            return int(75 + 25 * (volume_24h - self.thresholds["volume_24h_good"]) /
                      (self.thresholds["volume_24h_excellent"] - self.thresholds["volume_24h_good"]))
        elif volume_24h >= self.thresholds["volume_24h_fair"]:
            return int(50 + 25 * (volume_24h - self.thresholds["volume_24h_fair"]) /
                      (self.thresholds["volume_24h_good"] - self.thresholds["volume_24h_fair"]))
        elif volume_24h > 0:
            return int(50 * volume_24h / self.thresholds["volume_24h_fair"])
        return 0

    def score_liquidity(self, liquidity_1pct: float) -> int:
        """Score liquidity component (0-100)"""
        if liquidity_1pct >= self.thresholds["liquidity_1pct_excellent"]:
            return 100
        elif liquidity_1pct >= self.thresholds["liquidity_1pct_good"]:
            return int(75 + 25 * (liquidity_1pct - self.thresholds["liquidity_1pct_good"]) /
                      (self.thresholds["liquidity_1pct_excellent"] - self.thresholds["liquidity_1pct_good"]))
        elif liquidity_1pct >= self.thresholds["liquidity_1pct_fair"]:
            return int(50 + 25 * (liquidity_1pct - self.thresholds["liquidity_1pct_fair"]) /
                      (self.thresholds["liquidity_1pct_good"] - self.thresholds["liquidity_1pct_fair"]))
        elif liquidity_1pct > 0:
            return int(50 * liquidity_1pct / self.thresholds["liquidity_1pct_fair"])
        return 0

    def score_spread(self, spread_bps: float) -> int:
        """Score spread component (0-100, lower spread = higher score)"""
        if spread_bps <= self.thresholds["spread_excellent_bps"]:
            return 100
        elif spread_bps <= self.thresholds["spread_good_bps"]:
            return int(100 - 25 * (spread_bps - self.thresholds["spread_excellent_bps"]) /
                      (self.thresholds["spread_good_bps"] - self.thresholds["spread_excellent_bps"]))
        elif spread_bps <= self.thresholds["spread_fair_bps"]:
            return int(75 - 25 * (spread_bps - self.thresholds["spread_good_bps"]) /
                      (self.thresholds["spread_fair_bps"] - self.thresholds["spread_good_bps"]))
        elif spread_bps < 500:  # Very wide spread
            return int(50 - 50 * (spread_bps - self.thresholds["spread_fair_bps"]) /
                      (500 - self.thresholds["spread_fair_bps"]))
        return 0

    def score_holders(self, holder_change_24h: int, gini: float) -> int:
        """Score holder component (0-100)"""
        # Holder growth score (0-50)
        if holder_change_24h >= self.thresholds["holder_growth_excellent"]:
            growth_score = 50
        elif holder_change_24h >= self.thresholds["holder_growth_good"]:
            growth_score = int(35 + 15 * (holder_change_24h - self.thresholds["holder_growth_good"]) /
                              (self.thresholds["holder_growth_excellent"] - self.thresholds["holder_growth_good"]))
        elif holder_change_24h >= self.thresholds["holder_growth_fair"]:
            growth_score = int(20 + 15 * (holder_change_24h - self.thresholds["holder_growth_fair"]) /
                              (self.thresholds["holder_growth_good"] - self.thresholds["holder_growth_fair"]))
        elif holder_change_24h >= -50:
            growth_score = max(0, int(20 + holder_change_24h / 2.5))
        else:
            growth_score = 0

        # Distribution score based on Gini (0-50)
        # Lower Gini = more distributed = better (0.3-0.5 is healthy)
        if gini <= 0.5:
            distribution_score = 50
        elif gini <= 0.7:
            distribution_score = int(50 - 25 * (gini - 0.5) / 0.2)
        elif gini <= 0.9:
            distribution_score = int(25 - 25 * (gini - 0.7) / 0.2)
        else:
            distribution_score = 0

        return growth_score + distribution_score

    def score_price_stability(self, price_change_24h: float, volatility_7d: float) -> int:
        """Score price stability (0-100)"""
        # Moderate positive change is ideal, extreme moves are penalized
        # Ideal: 0-5% gain
        if 0 <= price_change_24h <= 5:
            change_score = 50
        elif -5 <= price_change_24h < 0 or 5 < price_change_24h <= 10:
            change_score = 40
        elif -10 <= price_change_24h < -5 or 10 < price_change_24h <= 20:
            change_score = 25
        else:
            change_score = 10

        # Low volatility is preferred for institutional consideration
        if volatility_7d <= 5:
            volatility_score = 50
        elif volatility_7d <= 10:
            volatility_score = 35
        elif volatility_7d <= 20:
            volatility_score = 20
        else:
            volatility_score = 5

        return change_score + volatility_score

    async def calculate_health_score(self, token_id: int) -> Tuple[int, str, Dict[str, int]]:
        """
        Calculate overall health score for a token.
        Returns (score, grade, component_scores)
        """
        metrics = await self.get_latest_metrics(token_id)

        # Calculate component scores
        volume_score = self.score_volume(metrics["volume_24h"])
        liquidity_score = self.score_liquidity(metrics["liquidity_1pct"])
        spread_score = self.score_spread(metrics["spread_bps"])
        holder_score = self.score_holders(
            metrics["holder_change_24h"],
            metrics["gini_coefficient"]
        )
        stability_score = self.score_price_stability(
            metrics["price_change_24h"],
            metrics["volatility_7d"]
        )

        component_scores = {
            "volume": volume_score,
            "liquidity": liquidity_score,
            "spread": spread_score,
            "holders": holder_score,
            "price_stability": stability_score,
        }

        # Weighted average
        total_score = int(
            volume_score * self.weights["volume"] +
            liquidity_score * self.weights["liquidity"] +
            spread_score * self.weights["spread"] +
            holder_score * self.weights["holders"] +
            stability_score * self.weights["price_stability"]
        )

        grade = self.calculate_grade(total_score)

        return total_score, grade, component_scores

    async def score_all_tokens(self) -> int:
        """Calculate and store health scores for all tokens"""
        tokens = await get_all_tokens()
        count = 0

        for token in tokens:
            try:
                score, grade, components = await self.calculate_health_score(token["id"])

                # Update aggregated metrics with health score
                await self._update_health_score(token["id"], score, grade)
                count += 1

                logger.debug(f"{token['symbol']}: Score={score} Grade={grade}")

            except Exception as e:
                logger.error(f"Health scoring failed for {token['symbol']}: {e}")

        logger.info(f"Health scores updated for {count} tokens")
        return count

    async def _update_health_score(self, token_id: int, score: int, grade: str):
        """Update health score in aggregated metrics"""
        query = """
            UPDATE token_metrics_aggregated
            SET health_score = $2, health_grade = $3
            WHERE token_id = $1 AND time = (
                SELECT MAX(time) FROM token_metrics_aggregated WHERE token_id = $1
            )
        """
        await Database.execute(query, token_id, score, grade)


async def run_scorer():
    """Main scoring loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["health_score"]
    logger.info(f"Starting health scorer (interval: {interval}s)")

    while True:
        try:
            scorer = HealthScorer()
            count = await scorer.score_all_tokens()
            logger.info(f"Health scoring complete: {count} tokens")
        except Exception as e:
            logger.error(f"Health scoring error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scorer())
