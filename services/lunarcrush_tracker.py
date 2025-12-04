"""
LunarCrush Social Intelligence Tracker
Legal, licensed API for crypto social sentiment and metrics
https://lunarcrush.com/developers/api/endpoints
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import aiohttp

from config.settings import lunarcrush_config
from services.database import Database, get_token_id

logger = logging.getLogger(__name__)

# Map fan token symbols to LunarCrush coin symbols/IDs
# LunarCrush uses different identifiers
FANTOKEN_TO_LUNARCRUSH = {
    "CHZ": "chz",  # Chiliz
    "BAR": "bar",  # FC Barcelona
    "PSG": "psg",  # Paris Saint-Germain
    "JUV": "juv",  # Juventus
    "ATM": "atm",  # Atletico Madrid
    "CITY": "city",  # Man City
    "ACM": "acm",  # AC Milan
    "INTER": "inter",  # Inter Milan
    "GAL": "gal",  # Galatasaray
    "NAP": "nap",  # Napoli
    "ASR": "asr",  # AS Roma
    "OG": "og",  # OG Esports
    "AFC": "afc",  # Arsenal
    "SPURS": "spurs",  # Tottenham
    "MENGO": "mengo",  # Flamengo
    "SANTOS": "santos",  # Santos
    "ARG": "arg",  # Argentina
    "POR": "por",  # Portugal
    # Add more as needed - check LunarCrush coins/list for available symbols
}


class LunarCrushTracker:
    """
    LunarCrush API integration for social sentiment tracking.
    Provides Galaxy Score, sentiment, social volume, and more.
    """

    def __init__(self):
        self.api_key = lunarcrush_config.api_key
        self.base_url = "https://lunarcrush.com/api4"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self.session = aiohttp.ClientSession(headers=headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def get_coin_data(self, symbol: str) -> Optional[Dict]:
        """
        Get social metrics for a specific coin/token.
        Returns Galaxy Score, sentiment, social volume, etc.
        """
        lc_symbol = FANTOKEN_TO_LUNARCRUSH.get(symbol, symbol.lower())

        url = f"{self.base_url}/public/coins/{lc_symbol}/v1"

        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data")
                elif resp.status == 404:
                    logger.warning(f"Coin {symbol} not found on LunarCrush")
                    return None
                else:
                    error = await resp.text()
                    logger.error(f"LunarCrush API error {resp.status}: {error[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching LunarCrush data for {symbol}: {e}")
            return None

    async def get_coin_time_series(
        self,
        symbol: str,
        interval: str = "1w",  # 1d, 1w, 1m, 3m, 6m, 1y, 2y
        bucket: str = "hour"  # hour or day
    ) -> List[Dict]:
        """
        Get time series social data for a coin.
        """
        lc_symbol = FANTOKEN_TO_LUNARCRUSH.get(symbol, symbol.lower())

        url = f"{self.base_url}/public/coins/{lc_symbol}/time-series/v2"
        params = {
            "interval": interval,
            "bucket": bucket,
        }

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                else:
                    return []
        except Exception as e:
            logger.error(f"Error fetching time series for {symbol}: {e}")
            return []

    async def get_topic_posts(self, topic: str, limit: int = 50) -> List[Dict]:
        """
        Get top social posts for a topic (coin name, hashtag, etc.)
        Returns posts from Twitter, Reddit, YouTube, TikTok, news.
        """
        url = f"{self.base_url}/public/topic/{topic}/posts/v1"
        params = {"limit": limit}

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                else:
                    return []
        except Exception as e:
            logger.error(f"Error fetching topic posts for {topic}: {e}")
            return []

    async def get_topic_news(self, topic: str, limit: int = 20) -> List[Dict]:
        """
        Get top news articles for a topic.
        """
        url = f"{self.base_url}/public/topic/{topic}/news/v1"
        params = {"limit": limit}

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                else:
                    return []
        except Exception as e:
            logger.error(f"Error fetching topic news for {topic}: {e}")
            return []

    async def get_coins_list(self) -> List[Dict]:
        """
        Get list of all coins tracked by LunarCrush.
        Useful for finding available fan tokens.
        """
        url = f"{self.base_url}/public/coins/list/v2"

        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                else:
                    return []
        except Exception as e:
            logger.error(f"Error fetching coins list: {e}")
            return []

    async def collect_fan_token_metrics(self, symbols: List[str]) -> List[Dict]:
        """
        Collect social metrics for multiple fan tokens.
        Returns normalized data ready for database storage.
        """
        results = []

        for symbol in symbols:
            try:
                coin_data = await self.get_coin_data(symbol)
                if not coin_data:
                    continue

                # Normalize to our schema
                normalized = {
                    "symbol": symbol,
                    "time": datetime.now(timezone.utc),
                    "source": "lunarcrush",

                    # Core metrics
                    "galaxy_score": coin_data.get("galaxy_score"),
                    "alt_rank": coin_data.get("alt_rank"),
                    "sentiment": coin_data.get("sentiment", 50) / 100,  # Normalize to 0-1

                    # Social volume
                    "social_volume": coin_data.get("social_volume", 0),
                    "social_volume_24h": coin_data.get("social_volume_24h", 0),
                    "social_dominance": coin_data.get("social_dominance", 0),

                    # Engagement
                    "social_contributors": coin_data.get("social_contributors", 0),
                    "social_interactions": coin_data.get("interactions_24h", 0),

                    # Sentiment breakdown
                    "bullish_sentiment": coin_data.get("sentiment_bullish", 0),
                    "bearish_sentiment": coin_data.get("sentiment_bearish", 0),

                    # Market data
                    "price": coin_data.get("price"),
                    "price_change_24h": coin_data.get("percent_change_24h"),
                    "market_cap": coin_data.get("market_cap"),
                    "volume_24h": coin_data.get("volume_24h"),

                    # Raw data for reference
                    "raw_data": coin_data,
                }

                results.append(normalized)
                logger.info(f"Collected LunarCrush metrics for {symbol}: Galaxy Score {coin_data.get('galaxy_score')}")

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error collecting metrics for {symbol}: {e}")

        return results

    async def save_metrics(self, metrics: List[Dict]):
        """Save collected metrics to database."""
        query = """
            INSERT INTO lunarcrush_metrics
            (time, token_id, galaxy_score, alt_rank, sentiment,
             social_volume, social_volume_24h, social_dominance,
             social_contributors, social_interactions,
             bullish_sentiment, bearish_sentiment,
             price, price_change_24h, market_cap, volume_24h, raw_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            ON CONFLICT DO NOTHING
        """

        import json
        for metric in metrics:
            try:
                token_id = await get_token_id(metric["symbol"])
                if not token_id:
                    continue

                await Database.execute(
                    query,
                    metric["time"],
                    token_id,
                    metric.get("galaxy_score"),
                    metric.get("alt_rank"),
                    metric.get("sentiment"),
                    metric.get("social_volume"),
                    metric.get("social_volume_24h"),
                    metric.get("social_dominance"),
                    metric.get("social_contributors"),
                    metric.get("social_interactions"),
                    metric.get("bullish_sentiment"),
                    metric.get("bearish_sentiment"),
                    metric.get("price"),
                    metric.get("price_change_24h"),
                    metric.get("market_cap"),
                    metric.get("volume_24h"),
                    json.dumps(metric.get("raw_data", {}), default=str),
                )
            except Exception as e:
                logger.error(f"Error saving LunarCrush metrics: {e}")


async def collect_lunarcrush_metrics() -> int:
    """
    One-time collection of LunarCrush metrics for all fan tokens.
    Called by the worker every 15 minutes.
    """
    from services.database import get_all_tokens

    tokens = await get_all_tokens()
    symbols = [t["symbol"] for t in tokens if t["symbol"] in FANTOKEN_TO_LUNARCRUSH]

    if not symbols:
        logger.warning("No fan tokens configured for LunarCrush tracking")
        return 0

    tracker = LunarCrushTracker()

    try:
        async with tracker:
            metrics = await tracker.collect_fan_token_metrics(symbols)
            if metrics:
                await tracker.save_metrics(metrics)
            return len(metrics)
    except Exception as e:
        logger.error(f"LunarCrush collection failed: {e}")
        return 0


async def get_lunarcrush_summary(symbol: str) -> Optional[Dict]:
    """
    Get current LunarCrush summary for a token.
    Used by the API for quick lookups.
    """
    tracker = LunarCrushTracker()

    try:
        async with tracker:
            return await tracker.get_coin_data(symbol)
    except Exception as e:
        logger.error(f"Error getting LunarCrush summary: {e}")
        return None
