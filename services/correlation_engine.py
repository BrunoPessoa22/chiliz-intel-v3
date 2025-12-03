"""
Correlation Engine - Cross-Pillar Analysis
Analyzes relationships between Social Activity, Price, Volume, Holders, Spread, and Liquidity.
CORE PoC FEATURE: Does social noise predict price movements?
"""
import asyncio
import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
import statistics

from services.database import Database, get_all_tokens

logger = logging.getLogger(__name__)

# Lag periods to test for social → price prediction (in hours)
SOCIAL_LAG_PERIODS = [0, 1, 3, 6, 12, 24]
# Lowered from 24 to 5 for early-stage data collection (Twitter Basic tier)
# Will show preliminary correlations while data accumulates
MIN_DATA_POINTS = 5


class CorrelationEngine:
    """Analyzes correlations across the Five Pillars"""

    async def get_time_series(
        self,
        token_id: int,
        metric: str,
        days: int = 30
    ) -> List[Tuple[datetime, float]]:
        """Get time series data for a specific metric"""

        queries = {
            "price": """
                SELECT time, vwap_price as value
                FROM token_metrics_aggregated
                WHERE token_id = $1 AND time > NOW() - INTERVAL '1 day' * $2
                ORDER BY time
            """,
            "volume": """
                SELECT time, total_volume_24h as value
                FROM token_metrics_aggregated
                WHERE token_id = $1 AND time > NOW() - INTERVAL '1 day' * $2
                ORDER BY time
            """,
            "holders": """
                SELECT time, total_holders as value
                FROM holder_snapshots
                WHERE token_id = $1 AND time > NOW() - INTERVAL '1 day' * $2
                ORDER BY time
            """,
            "spread": """
                SELECT time, avg_spread_bps as value
                FROM token_metrics_aggregated
                WHERE token_id = $1 AND time > NOW() - INTERVAL '1 day' * $2
                ORDER BY time
            """,
            "liquidity": """
                SELECT time, total_liquidity_1pct as value
                FROM token_metrics_aggregated
                WHERE token_id = $1 AND time > NOW() - INTERVAL '1 day' * $2
                ORDER BY time
            """,
        }

        query = queries.get(metric)
        if not query:
            return []

        rows = await Database.fetch(query, token_id, days)
        return [(row["time"], float(row["value"] or 0)) for row in rows]

    def calculate_correlation(
        self,
        series1: List[Tuple[datetime, float]],
        series2: List[Tuple[datetime, float]],
        lag: int = 0
    ) -> Optional[float]:
        """
        Calculate Pearson correlation between two time series.
        Optionally apply a lag (series2 shifted by lag periods).
        """
        if len(series1) < 10 or len(series2) < 10:
            return None

        # Align series by timestamp (daily aggregation)
        dict1 = {ts.date(): val for ts, val in series1}
        dict2 = {ts.date(): val for ts, val in series2}

        # Get common dates
        common_dates = sorted(set(dict1.keys()) & set(dict2.keys()))
        if len(common_dates) < 10:
            return None

        # Apply lag
        if lag > 0:
            common_dates = common_dates[lag:]

        values1 = [dict1[d] for d in common_dates if d in dict1]
        values2 = [dict2[d] for d in common_dates if d in dict2]

        if len(values1) != len(values2) or len(values1) < 5:
            return None

        # Calculate correlation
        try:
            n = len(values1)
            mean1 = statistics.mean(values1)
            mean2 = statistics.mean(values2)
            std1 = statistics.stdev(values1)
            std2 = statistics.stdev(values2)

            if std1 == 0 or std2 == 0:
                return 0

            covariance = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(values1, values2)) / n
            correlation = covariance / (std1 * std2)

            return round(correlation, 4)
        except Exception as e:
            logger.error(f"Correlation calculation error: {e}")
            return None

    def find_optimal_lag(
        self,
        series1: List[Tuple[datetime, float]],
        series2: List[Tuple[datetime, float]],
        max_lag: int = 7
    ) -> Tuple[Optional[float], int]:
        """
        Find the lag that produces the highest correlation.
        Returns (best_correlation, best_lag).
        """
        best_corr = None
        best_lag = 0

        for lag in range(-max_lag, max_lag + 1):
            if lag < 0:
                # Shift series1 forward
                s1 = series1[-lag:]
                s2 = series2[:lag] if lag != 0 else series2
            else:
                # Shift series2 forward
                s1 = series1
                s2 = series2

            corr = self.calculate_correlation(s1, s2, abs(lag))
            if corr is not None:
                if best_corr is None or abs(corr) > abs(best_corr):
                    best_corr = corr
                    best_lag = lag

        return best_corr, best_lag

    async def analyze_token_correlations(
        self,
        token_id: int,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Analyze all correlations for a single token"""

        # Get time series for all metrics
        price = await self.get_time_series(token_id, "price", lookback_days)
        volume = await self.get_time_series(token_id, "volume", lookback_days)
        holders = await self.get_time_series(token_id, "holders", lookback_days)
        spread = await self.get_time_series(token_id, "spread", lookback_days)
        liquidity = await self.get_time_series(token_id, "liquidity", lookback_days)

        # Price-Volume correlation (with lag detection)
        pv_corr, pv_lag = self.find_optimal_lag(price, volume)

        # Price-Holders correlation (holders often lead price)
        ph_corr, ph_lag = self.find_optimal_lag(price, holders)

        # Volume-Holders correlation
        vh_corr = self.calculate_correlation(volume, holders)

        # Spread-Price correlation (tighter spreads = more efficient)
        sp_corr = self.calculate_correlation(spread, price)

        # Liquidity-Volume correlation
        lv_corr = self.calculate_correlation(liquidity, volume)

        # Determine market regime based on recent price action
        market_regime = await self._determine_market_regime(token_id)

        return {
            "token_id": token_id,
            "analysis_date": datetime.now(timezone.utc).date(),
            "lookback_days": lookback_days,
            "price_volume_corr": pv_corr,
            "price_volume_lag": pv_lag,
            "price_holders_corr": ph_corr,
            "price_holders_lag": ph_lag,
            "volume_holders_corr": vh_corr,
            "spread_price_corr": sp_corr,
            "liquidity_volume_corr": lv_corr,
            "btc_correlation": None,  # Would need BTC price series
            "market_regime": market_regime,
        }

    async def _determine_market_regime(self, token_id: int) -> str:
        """Determine current market regime based on price action"""
        query = """
            SELECT price_change_7d FROM token_metrics_aggregated
            WHERE token_id = $1
            ORDER BY time DESC LIMIT 1
        """
        change = await Database.fetchval(query, token_id)

        if change is None:
            return "unknown"
        elif change > 10:
            return "bullish"
        elif change < -10:
            return "bearish"
        elif abs(change) < 3:
            return "ranging"
        else:
            return "neutral"

    async def analyze_all_tokens(self, lookback_days: int = 30) -> int:
        """Run correlation analysis for all tokens"""
        tokens = await get_all_tokens()
        count = 0

        for token in tokens:
            try:
                analysis = await self.analyze_token_correlations(
                    token["id"], lookback_days
                )
                await self._save_analysis(analysis)
                count += 1
            except Exception as e:
                logger.error(f"Correlation analysis failed for {token['symbol']}: {e}")

        logger.info(f"Completed correlation analysis for {count} tokens")
        return count

    async def _save_analysis(self, analysis: Dict[str, Any]):
        """Save correlation analysis to database"""
        query = """
            INSERT INTO correlation_analysis
            (token_id, analysis_date, lookback_days, price_volume_corr, price_volume_lag,
             price_holders_corr, price_holders_lag, volume_holders_corr, spread_price_corr,
             liquidity_volume_corr, btc_correlation, market_regime)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (token_id, analysis_date, lookback_days) DO UPDATE SET
                price_volume_corr = EXCLUDED.price_volume_corr,
                price_holders_corr = EXCLUDED.price_holders_corr,
                market_regime = EXCLUDED.market_regime
        """

        await Database.execute(
            query,
            analysis["token_id"],
            analysis["analysis_date"],
            analysis["lookback_days"],
            analysis["price_volume_corr"],
            analysis["price_volume_lag"],
            analysis["price_holders_corr"],
            analysis["price_holders_lag"],
            analysis["volume_holders_corr"],
            analysis["spread_price_corr"],
            analysis["liquidity_volume_corr"],
            analysis["btc_correlation"],
            analysis["market_regime"],
        )

    async def generate_insights(self, token_id: int) -> List[str]:
        """Generate human-readable insights from correlations"""
        query = """
            SELECT * FROM correlation_analysis
            WHERE token_id = $1
            ORDER BY analysis_date DESC LIMIT 1
        """
        row = await Database.fetchrow(query, token_id)
        if not row:
            return []

        insights = []

        # Social-Price relationship (PoC core insight)
        sp = row.get("social_price_corr")
        if sp and abs(sp) > 0.3:
            direction = "positively" if sp > 0 else "negatively"
            insights.append(f"Social activity {direction} correlates with price (r={sp:.2f}). Social signals may predict price movement.")

        # Price-Volume relationship
        pv = row["price_volume_corr"]
        if pv and pv > 0.7:
            insights.append("Strong positive price-volume correlation: volume increases typically accompany price rises.")
        elif pv and pv < -0.3:
            insights.append("Warning: Negative price-volume correlation detected - volume spikes may indicate selling pressure.")

        # Holder-Price relationship
        ph = row["price_holders_corr"]
        lag = row["price_holders_lag"]
        if ph and ph > 0.5 and lag and lag > 0:
            insights.append(f"Holder growth tends to lead price by {lag} days - new holder accumulation may signal upcoming price increases.")
        elif ph and ph < -0.3:
            insights.append("Warning: Declining holder count correlates with price drops - watch for distribution patterns.")

        # Liquidity-Volume
        lv = row["liquidity_volume_corr"]
        if lv and lv > 0.6:
            insights.append("Healthy liquidity-volume relationship: market makers are responsive to trading activity.")

        # Spread correlation
        spr = row["spread_price_corr"]
        if spr and spr < -0.5:
            insights.append("Spreads tighten as prices rise - market efficiency improves in bullish conditions.")

        return insights

    # =====================================================
    # SOCIAL → PRICE CORRELATION (PoC Core Feature)
    # =====================================================

    async def analyze_social_price_correlation(
        self,
        token_id: int,
        symbol: str,
        lookback_days: int = 30
    ) -> Optional[Dict]:
        """
        Analyze if social activity predicts price movements.
        This is the core PoC hypothesis: does social noise lead price?
        """
        # Fetch aligned hourly data
        data = await self._fetch_social_market_aligned(token_id, lookback_days)

        if len(data) < MIN_DATA_POINTS:
            logger.warning(f"{symbol}: Insufficient data ({len(data)} points, need {MIN_DATA_POINTS})")
            return None

        # Extract time series
        prices = [float(d["price"] or 0) for d in data]
        volumes = [float(d["volume"] or 0) for d in data]
        tweet_counts = [int(d["tweet_count"] or 0) for d in data]
        sentiments = [float(d["sentiment"] or 0.5) for d in data]
        engagements = [int(d["engagement"] or 0) for d in data]

        # Calculate price returns (percentage change)
        price_returns = self._calculate_returns(prices)
        volume_changes = self._calculate_returns(volumes)

        # Find best lag for social → price correlation
        tweet_price = self._find_best_lag(tweet_counts[:-1], price_returns, "tweets", "price_return")
        tweet_volume = self._find_best_lag(tweet_counts[:-1], volume_changes, "tweets", "volume_change")
        sentiment_price = self._find_best_lag(sentiments[:-1], price_returns, "sentiment", "price_return")
        engagement_price = self._find_best_lag(engagements[:-1], price_returns, "engagement", "price_return")

        result = {
            "token_id": token_id,
            "symbol": symbol,
            "data_points": len(data),
            "lookback_days": lookback_days,
            "tweet_price": tweet_price,
            "tweet_volume": tweet_volume,
            "sentiment_price": sentiment_price,
            "engagement_price": engagement_price,
            "is_predictive": tweet_price["is_predictive"] or sentiment_price["is_predictive"],
            "best_signal": self._get_best_signal(tweet_price, sentiment_price, engagement_price),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(f"{symbol}: Social→Price best lag={tweet_price['best_lag']}h, r={tweet_price['correlation']:.3f}")
        return result

    async def _fetch_social_market_aligned(self, token_id: int, lookback_days: int) -> List[Dict]:
        """Fetch aligned hourly social and market data"""
        query = """
            WITH market_hourly AS (
                SELECT
                    date_trunc('hour', time) as hour,
                    AVG(vwap_price) as price,
                    AVG(total_volume_24h) as volume
                FROM token_metrics_aggregated
                WHERE token_id = $1 AND time > NOW() - INTERVAL '%s days'
                GROUP BY date_trunc('hour', time)
            ),
            social_hourly AS (
                SELECT
                    date_trunc('hour', time) as hour,
                    MAX(tweet_count_24h) as tweet_count,
                    AVG(sentiment_score) as sentiment,
                    MAX(engagement_total) as engagement
                FROM social_metrics
                WHERE token_id = $1 AND time > NOW() - INTERVAL '%s days'
                GROUP BY date_trunc('hour', time)
            )
            SELECT
                m.hour as time,
                m.price,
                m.volume,
                COALESCE(s.tweet_count, 0) as tweet_count,
                COALESCE(s.sentiment, 0.5) as sentiment,
                COALESCE(s.engagement, 0) as engagement
            FROM market_hourly m
            LEFT JOIN social_hourly s ON m.hour = s.hour
            WHERE m.price IS NOT NULL AND m.price > 0
            ORDER BY m.hour ASC
        """ % (lookback_days, lookback_days)

        rows = await Database.fetch(query, token_id)
        return [dict(r) for r in rows]

    def _calculate_returns(self, prices: List[float]) -> List[float]:
        """Calculate percentage returns from price series"""
        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] != 0:
                ret = (prices[i] - prices[i - 1]) / prices[i - 1] * 100
            else:
                ret = 0
            returns.append(ret)
        return returns

    def _find_best_lag(
        self,
        x_series: List[float],
        y_series: List[float],
        x_name: str,
        y_name: str
    ) -> Dict:
        """Find the lag with highest correlation (x leads y)"""
        best_lag = 0
        best_corr = 0
        best_p = 1.0
        all_lags = {}

        for lag in SOCIAL_LAG_PERIODS:
            if lag >= len(x_series):
                continue

            # Align: x at time t, y at time t+lag
            if lag == 0:
                x = x_series
                y = y_series
            else:
                x = x_series[:-lag]
                y = y_series[lag:]

            if len(x) < MIN_DATA_POINTS:
                continue

            corr, p_value = self._pearson_with_pvalue(x, y)
            all_lags[lag] = {"r": round(corr, 4), "p": round(p_value, 4), "n": len(x)}

            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag
                best_p = p_value

        is_significant = best_p < 0.05
        is_predictive = is_significant and best_lag > 0 and abs(best_corr) >= 0.25

        return {
            "x": x_name,
            "y": y_name,
            "best_lag": best_lag,
            "correlation": round(best_corr, 4),
            "p_value": round(best_p, 4),
            "is_significant": is_significant,
            "is_predictive": is_predictive,
            "all_lags": all_lags,
            "interpretation": self._interpret(best_corr, best_lag, best_p, x_name, y_name)
        }

    def _pearson_with_pvalue(self, x: List[float], y: List[float]) -> Tuple[float, float]:
        """Calculate Pearson r and approximate p-value"""
        n = len(x)
        if n < 3:
            return 0.0, 1.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        den_x = sum((xi - mean_x) ** 2 for xi in x)
        den_y = sum((yi - mean_y) ** 2 for yi in y)
        den = math.sqrt(den_x * den_y)

        if den == 0:
            return 0.0, 1.0

        r = num / den

        # t-statistic for p-value
        if abs(r) >= 0.9999:
            return r, 0.0

        t = r * math.sqrt((n - 2) / (1 - r * r))
        # Approximate p-value (two-tailed)
        p = 2 * (1 - self._t_cdf(abs(t), n - 2))
        return r, max(0, min(1, p))

    def _t_cdf(self, t: float, df: int) -> float:
        """Approximate t-distribution CDF"""
        x = df / (df + t * t)
        # Beta function approximation
        return 1 - 0.5 * (x ** (df / 2))

    def _interpret(self, r: float, lag: int, p: float, x: str, y: str) -> str:
        """Generate human interpretation"""
        if p >= 0.05:
            return f"No significant relationship between {x} and {y}."

        strength = "strong" if abs(r) >= 0.5 else "moderate" if abs(r) >= 0.3 else "weak"
        direction = "positive" if r > 0 else "negative"

        if lag == 0:
            timing = "move together simultaneously"
        else:
            timing = f"{x} leads {y} by {lag} hour{'s' if lag > 1 else ''}"

        if abs(r) >= 0.25 and lag > 0:
            return f"PREDICTIVE: {strength} {direction} correlation - {timing}. Social signals may forecast price."
        return f"{strength.capitalize()} {direction} correlation - {timing}."

    def _get_best_signal(self, *signals) -> Dict:
        """Return the most predictive signal"""
        predictive = [s for s in signals if s.get("is_predictive")]
        if predictive:
            return max(predictive, key=lambda s: abs(s["correlation"]))
        return max(signals, key=lambda s: abs(s.get("correlation", 0)))

    async def get_social_correlation_summary(self) -> Dict:
        """Get summary of social correlations for all tokens (dashboard endpoint)"""
        tokens = await Database.fetch(
            "SELECT id, symbol, team FROM fan_tokens WHERE is_active = true"
        )

        results = []
        predictive_count = 0

        for token in tokens:  # All tokens
            try:
                analysis = await self.analyze_social_price_correlation(
                    token["id"], token["symbol"], lookback_days=14
                )
                if analysis:
                    results.append({
                        "symbol": token["symbol"],
                        "team": token["team"],
                        "tweet_price_r": analysis["tweet_price"]["correlation"],
                        "tweet_price_lag": analysis["tweet_price"]["best_lag"],
                        "is_predictive": analysis["is_predictive"],
                        "best_signal": analysis["best_signal"]["interpretation"],
                    })
                    if analysis["is_predictive"]:
                        predictive_count += 1
            except Exception as e:
                logger.error(f"Error analyzing {token['symbol']}: {e}")

        # Sort by correlation strength
        results.sort(key=lambda x: abs(x["tweet_price_r"]), reverse=True)

        return {
            "tokens": results,
            "summary": {
                "analyzed": len(results),
                "predictive": predictive_count,
                "pct_predictive": round(predictive_count / max(len(results), 1) * 100, 1),
            },
            "poc_answer": self._generate_poc_answer(results, predictive_count),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _generate_poc_answer(self, results: List[Dict], predictive_count: int) -> str:
        """Generate the PoC answer: does social predict price?"""
        if not results:
            return "Insufficient data to determine if social noise predicts price movements."

        if predictive_count >= 3:
            best = results[0]
            return (
                f"YES - Social activity shows predictive signal for {predictive_count} tokens. "
                f"Strongest: {best['symbol']} (r={best['tweet_price_r']:.2f}, leads by {best['tweet_price_lag']}h). "
                f"Recommend: Monitor social spikes for campaign timing."
            )
        elif predictive_count >= 1:
            return (
                f"PARTIAL - {predictive_count} token(s) show weak predictive signals. "
                f"Social activity correlates with price but lead time is inconsistent. "
                f"Recommend: Continue data collection for stronger conclusions."
            )
        else:
            return (
                "NO CLEAR SIGNAL - Current data does not show social activity predicting price. "
                "This could mean: (1) insufficient data, (2) fan tokens move on other factors, "
                "or (3) social signal is too noisy. Recommend: Extend collection period."
            )


async def run_engine():
    """Main correlation analysis loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["correlation"]
    logger.info(f"Starting correlation engine (interval: {interval}s)")

    while True:
        try:
            engine = CorrelationEngine()

            # Run analysis for different lookback periods
            for days in [7, 30, 90]:
                count = await engine.analyze_all_tokens(days)
                logger.info(f"Correlation analysis ({days}d) complete: {count} tokens")

        except Exception as e:
            logger.error(f"Correlation engine error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_engine())
