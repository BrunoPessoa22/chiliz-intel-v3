"""
Historical Data Collector
Collects and stores hourly market + social data for correlation analysis.
This is the foundation for the PoC - without historical data, no correlation is possible.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import urllib.parse

import aiohttp

from services.database import Database
from config.settings import x_api_config, coingecko_config

logger = logging.getLogger(__name__)

# Top tokens to track (focus on high-volume for meaningful correlation)
PRIORITY_TOKENS = [
    "CHZ", "BAR", "PSG", "JUV", "ATM", "ACM", "ASR", "CITY",
    "INTER", "NAP", "GAL", "OG", "MENGO", "SPURS", "AFC"
]

# X/Twitter search queries per token
TOKEN_SEARCH_QUERIES = {
    "CHZ": "($CHZ OR chiliz OR #Chiliz) -is:retweet",
    "BAR": "($BAR OR Barcelona fan token OR #BarcaToken) -is:retweet",
    "PSG": "($PSG OR PSG fan token OR #PSGToken) -is:retweet",
    "JUV": "($JUV OR Juventus fan token OR #JuventusToken) -is:retweet",
    "ATM": "($ATM OR Atletico fan token OR #AtletiToken) -is:retweet",
    "ACM": "($ACM OR AC Milan fan token OR #ACMilanToken) -is:retweet",
    "ASR": "($ASR OR AS Roma fan token OR #RomaToken) -is:retweet",
    "CITY": "($CITY OR Man City fan token) -is:retweet",
    "INTER": "($INTER OR Inter Milan fan token) -is:retweet",
    "NAP": "($NAP OR Napoli fan token) -is:retweet",
    "GAL": "($GAL OR Galatasaray fan token) -is:retweet",
    "OG": "($OG OR OG esports fan token) -is:retweet",
    "MENGO": "($MENGO OR Flamengo fan token) -is:retweet",
    "SPURS": "($SPURS OR Tottenham fan token) -is:retweet",
    "AFC": "($AFC OR Arsenal fan token) -is:retweet",
}

# Sentiment keywords
BULLISH_WORDS = [
    'bullish', 'moon', 'pump', 'buy', 'winning', 'won', 'victory', 'champion',
    'amazing', 'great', 'signing', 'deal', 'partnership', 'fire', '🚀',
    'massive', 'huge', 'breaking', 'official', 'love', 'best', 'up'
]
BEARISH_WORDS = [
    'bearish', 'dump', 'sell', 'losing', 'lost', 'defeat', 'eliminated',
    'terrible', 'awful', 'injury', 'sacked', 'crisis', 'scandal', 'worst',
    'disappointed', 'sad', 'failed', 'miss', 'bad', 'down', 'crash'
]


class HistoricalCollector:
    """Collects hourly snapshots of market and social data"""

    def __init__(self):
        # Use CoinGecko Pro API for extended historical data (up to 2 years)
        self.coingecko_api_key = coingecko_config.api_key
        if self.coingecko_api_key:
            self.coingecko_base = "https://pro-api.coingecko.com/api/v3"
        else:
            self.coingecko_base = "https://api.coingecko.com/api/v3"
        self.x_base = "https://api.twitter.com/2"
        self.x_bearer = x_api_config.bearer_token

    def _get_coingecko_headers(self) -> Dict[str, str]:
        """Get headers for CoinGecko API requests"""
        headers = {"Accept": "application/json"}
        if self.coingecko_api_key:
            headers["x-cg-pro-api-key"] = self.coingecko_api_key
        return headers

    async def collect_hourly_snapshot(self):
        """Main collection routine - run every hour"""
        logger.info("Starting hourly data collection...")

        async with aiohttp.ClientSession() as session:
            # 1. Collect market data from CoinGecko
            market_data = await self._collect_market_data(session)

            # 2. Collect social data from X/Twitter
            social_data = await self._collect_social_data(session)

            # 3. Store in database
            await self._store_market_data(market_data)
            await self._store_social_data(social_data)

            # 4. Store BTC/ETH for correlation reference
            await self._store_market_references(session)

        logger.info(f"Hourly collection complete. Market: {len(market_data)} tokens, Social: {len(social_data)} tokens")

    async def _collect_market_data(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Fetch market data from CoinGecko"""
        # Get token IDs from database
        tokens = await Database.fetch(
            "SELECT id, symbol, coingecko_id FROM fan_tokens WHERE is_active = true AND symbol = ANY($1)",
            PRIORITY_TOKENS
        )

        if not tokens:
            logger.warning("No tokens found in database")
            return []

        # Build CoinGecko IDs list
        cg_ids = [t["coingecko_id"] for t in tokens if t["coingecko_id"]]

        url = f"{self.coingecko_base}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ",".join(cg_ids),
            "order": "market_cap_desc",
            "per_page": 100,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d"
        }

        try:
            headers = self._get_coingecko_headers()
            async with session.get(url, params=params, headers=headers, timeout=30) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"CoinGecko API error: {resp.status} - {error_text}")
                    return []

                data = await resp.json()

                # Map back to our token IDs
                token_map = {t["coingecko_id"]: t for t in tokens}
                results = []

                for coin in data:
                    cg_id = coin.get("id")
                    if cg_id not in token_map:
                        continue

                    token = token_map[cg_id]
                    results.append({
                        "token_id": token["id"],
                        "symbol": token["symbol"],
                        "price": float(coin.get("current_price") or 0),
                        "volume_24h": float(coin.get("total_volume") or 0),
                        "market_cap": float(coin.get("market_cap") or 0),
                        "price_change_1h": float(coin.get("price_change_percentage_1h_in_currency") or 0),
                        "price_change_24h": float(coin.get("price_change_percentage_24h") or 0),
                        "price_change_7d": float(coin.get("price_change_percentage_7d") or 0),
                    })

                return results

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return []

    async def _collect_social_data(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Fetch social data from X/Twitter"""
        if not self.x_bearer:
            logger.warning("X API bearer token not configured")
            return []

        # Get token IDs from database
        tokens = await Database.fetch(
            "SELECT id, symbol FROM fan_tokens WHERE is_active = true AND symbol = ANY($1)",
            PRIORITY_TOKENS
        )

        results = []

        for token in tokens:
            symbol = token["symbol"]
            query = TOKEN_SEARCH_QUERIES.get(symbol)

            if not query:
                continue

            try:
                social_metrics = await self._fetch_token_tweets(session, symbol, query)
                if social_metrics:
                    social_metrics["token_id"] = token["id"]
                    social_metrics["symbol"] = symbol
                    results.append(social_metrics)

                # Rate limit: small delay between requests
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching social data for {symbol}: {e}")
                continue

        return results

    async def _fetch_token_tweets(self, session: aiohttp.ClientSession, symbol: str, query: str) -> Optional[Dict]:
        """Fetch recent tweets for a token and calculate metrics"""
        url = f"{self.x_base}/tweets/search/recent"

        # URL encode the query
        params = {
            "query": query,
            "max_results": 100,  # Max allowed per request
            "tweet.fields": "created_at,public_metrics,author_id",
            "expansions": "author_id",
            "user.fields": "public_metrics"
        }

        headers = {
            "Authorization": f"Bearer {self.x_bearer}"
        }

        try:
            async with session.get(url, params=params, headers=headers, timeout=30) as resp:
                if resp.status == 429:
                    logger.warning(f"X API rate limit hit for {symbol}")
                    return None

                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"X API error for {symbol}: {resp.status} - {error_text}")
                    return None

                data = await resp.json()
                tweets = data.get("data", [])

                if not tweets:
                    return {
                        "tweet_count": 0,
                        "engagement_total": 0,
                        "sentiment_score": 0.5,
                        "positive_count": 0,
                        "negative_count": 0,
                        "neutral_count": 0,
                        "influencer_mentions": 0,
                    }

                # Build user map for follower counts
                users = {}
                if "includes" in data and "users" in data["includes"]:
                    for user in data["includes"]["users"]:
                        users[user["id"]] = user.get("public_metrics", {}).get("followers_count", 0)

                # Calculate metrics
                tweet_count = len(tweets)
                total_engagement = 0
                positive = 0
                negative = 0
                neutral = 0
                influencer_mentions = 0

                for tweet in tweets:
                    text = tweet.get("text", "").lower()
                    metrics = tweet.get("public_metrics", {})

                    # Engagement
                    likes = metrics.get("like_count", 0)
                    retweets = metrics.get("retweet_count", 0)
                    replies = metrics.get("reply_count", 0)
                    total_engagement += likes + retweets * 2 + replies

                    # Sentiment (simple keyword-based)
                    bull_score = sum(1 for word in BULLISH_WORDS if word in text)
                    bear_score = sum(1 for word in BEARISH_WORDS if word in text)

                    if bull_score > bear_score:
                        positive += 1
                    elif bear_score > bull_score:
                        negative += 1
                    else:
                        neutral += 1

                    # Influencer check (>10k followers)
                    author_id = tweet.get("author_id")
                    if author_id and users.get(author_id, 0) > 10000:
                        influencer_mentions += 1

                # Calculate sentiment score (0-1, 0.5 is neutral)
                total_sentiment = positive + negative + neutral
                if total_sentiment > 0:
                    sentiment_score = 0.5 + (positive - negative) / (total_sentiment * 2)
                    sentiment_score = max(0, min(1, sentiment_score))
                else:
                    sentiment_score = 0.5

                return {
                    "tweet_count": tweet_count,
                    "engagement_total": total_engagement,
                    "sentiment_score": round(sentiment_score, 4),
                    "positive_count": positive,
                    "negative_count": negative,
                    "neutral_count": neutral,
                    "influencer_mentions": influencer_mentions,
                }

        except Exception as e:
            logger.error(f"Error fetching tweets for {symbol}: {e}")
            return None

    async def _store_market_data(self, data: List[Dict]):
        """Store market data in database"""
        if not data:
            return

        now = datetime.now(timezone.utc)

        # Use token_metrics_aggregated table
        query = """
            INSERT INTO token_metrics_aggregated
            (time, token_id, vwap_price, total_volume_24h, price_change_1h,
             price_change_24h, price_change_7d, market_cap)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (time, token_id) DO UPDATE SET
                vwap_price = EXCLUDED.vwap_price,
                total_volume_24h = EXCLUDED.total_volume_24h,
                price_change_1h = EXCLUDED.price_change_1h,
                price_change_24h = EXCLUDED.price_change_24h,
                price_change_7d = EXCLUDED.price_change_7d,
                market_cap = EXCLUDED.market_cap
        """

        for item in data:
            try:
                await Database.execute(
                    query,
                    now,
                    item["token_id"],
                    item["price"],
                    item["volume_24h"],
                    item["price_change_1h"],
                    item["price_change_24h"],
                    item["price_change_7d"],
                    item["market_cap"]
                )
            except Exception as e:
                logger.error(f"Error storing market data for token {item.get('symbol')}: {e}")

        logger.info(f"Stored market data for {len(data)} tokens")

    async def _store_social_data(self, data: List[Dict]):
        """Store social data in database"""
        if not data:
            return

        now = datetime.now(timezone.utc)

        query = """
            INSERT INTO social_metrics
            (time, token_id, tweet_count_24h, engagement_total, sentiment_score,
             positive_count, negative_count, neutral_count, influencer_mentions)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (time, token_id) DO UPDATE SET
                tweet_count_24h = EXCLUDED.tweet_count_24h,
                engagement_total = EXCLUDED.engagement_total,
                sentiment_score = EXCLUDED.sentiment_score,
                positive_count = EXCLUDED.positive_count,
                negative_count = EXCLUDED.negative_count,
                neutral_count = EXCLUDED.neutral_count,
                influencer_mentions = EXCLUDED.influencer_mentions
        """

        for item in data:
            try:
                await Database.execute(
                    query,
                    now,
                    item["token_id"],
                    item["tweet_count"],
                    item["engagement_total"],
                    item["sentiment_score"],
                    item["positive_count"],
                    item["negative_count"],
                    item["neutral_count"],
                    item["influencer_mentions"]
                )
            except Exception as e:
                logger.error(f"Error storing social data for token {item.get('symbol')}: {e}")

        logger.info(f"Stored social data for {len(data)} tokens")

    async def _store_market_references(self, session: aiohttp.ClientSession):
        """Store BTC and ETH prices for correlation reference"""
        url = f"{self.coingecko_base}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": "bitcoin,ethereum",
            "order": "market_cap_desc",
            "per_page": 2,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h"
        }

        try:
            async with session.get(url, params=params, timeout=30) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()
                now = datetime.now(timezone.utc)

                query = """
                    INSERT INTO market_prices (time, symbol, price, price_change_24h, volume_24h, market_cap)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (time, symbol) DO UPDATE SET
                        price = EXCLUDED.price,
                        price_change_24h = EXCLUDED.price_change_24h,
                        volume_24h = EXCLUDED.volume_24h,
                        market_cap = EXCLUDED.market_cap
                """

                for coin in data:
                    symbol = "BTC" if coin["id"] == "bitcoin" else "ETH"
                    await Database.execute(
                        query,
                        now,
                        symbol,
                        float(coin.get("current_price") or 0),
                        float(coin.get("price_change_percentage_24h") or 0),
                        float(coin.get("total_volume") or 0),
                        float(coin.get("market_cap") or 0)
                    )

                logger.info("Stored BTC/ETH reference prices")

        except Exception as e:
            logger.error(f"Error storing market references: {e}")

    async def backfill_historical_data(self, days: int = 30):
        """
        Backfill historical data using CoinGecko's historical endpoints.
        CoinGecko Pro API supports:
        - Up to 365 days with hourly data per request
        - For 2 years (730 days), we make 2 requests per token

        X/Twitter API doesn't support historical search on basic tiers,
        so we'll only backfill market data.
        """
        logger.info(f"Starting {days}-day backfill of market data using {'Pro' if self.coingecko_api_key else 'Free'} API...")

        tokens = await Database.fetch(
            "SELECT id, symbol, coingecko_id FROM fan_tokens WHERE is_active = true AND symbol = ANY($1)",
            PRIORITY_TOKENS
        )

        async with aiohttp.ClientSession() as session:
            for token in tokens:
                if not token["coingecko_id"]:
                    continue

                # For requests > 365 days, split into chunks
                if days > 365:
                    # First chunk: older data (e.g., days 365-730)
                    await self._backfill_token_range(session, token, days, 365)
                    await asyncio.sleep(0.5)  # Pro API has higher rate limits
                    # Second chunk: recent data (days 0-365)
                    await self._backfill_token(session, token, 365)
                else:
                    await self._backfill_token(session, token, days)

                await asyncio.sleep(0.3 if self.coingecko_api_key else 1.5)  # Pro has higher limits

        # Also backfill BTC/ETH
        await self._backfill_market_references(days)

        logger.info("Backfill complete")

    async def _backfill_token(self, session: aiohttp.ClientSession, token: Dict, days: int):
        """Backfill historical data for a single token (up to 365 days)"""
        url = f"{self.coingecko_base}/coins/{token['coingecko_id']}/market_chart"
        params = {
            "vs_currency": "usd",
            "days": min(days, 365),  # CoinGecko max is 365 for hourly
            "interval": "hourly"
        }

        try:
            headers = self._get_coingecko_headers()
            async with session.get(url, params=params, headers=headers, timeout=60) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.warning(f"Could not backfill {token['symbol']}: {resp.status} - {error_text[:100]}")
                    return

                data = await resp.json()
                prices = data.get("prices", [])
                volumes = data.get("total_volumes", [])
                market_caps = data.get("market_caps", [])

                # Build hourly data points
                query = """
                    INSERT INTO token_metrics_aggregated
                    (time, token_id, vwap_price, total_volume_24h, market_cap)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (time, token_id) DO NOTHING
                """

                count = 0
                for i, (timestamp, price) in enumerate(prices):
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                    volume = volumes[i][1] if i < len(volumes) else 0
                    mcap = market_caps[i][1] if i < len(market_caps) else 0

                    try:
                        await Database.execute(query, dt, token["id"], price, volume, mcap)
                        count += 1
                    except Exception as e:
                        pass  # Ignore duplicate key errors

                logger.info(f"Backfilled {count} data points for {token['symbol']} (last {days} days)")

        except Exception as e:
            logger.error(f"Error backfilling {token['symbol']}: {e}")

    async def _backfill_token_range(self, session: aiohttp.ClientSession, token: Dict, from_days: int, to_days: int):
        """
        Backfill historical data for a specific date range.
        Uses CoinGecko Pro's range endpoint for older data.
        from_days: how many days ago to start (e.g., 730 for 2 years ago)
        to_days: how many days ago to end (e.g., 365 for 1 year ago)
        """
        now = datetime.now(timezone.utc)
        from_timestamp = int((now - timedelta(days=from_days)).timestamp())
        to_timestamp = int((now - timedelta(days=to_days)).timestamp())

        url = f"{self.coingecko_base}/coins/{token['coingecko_id']}/market_chart/range"
        params = {
            "vs_currency": "usd",
            "from": from_timestamp,
            "to": to_timestamp
        }

        try:
            headers = self._get_coingecko_headers()
            async with session.get(url, params=params, headers=headers, timeout=60) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.warning(f"Could not backfill range for {token['symbol']}: {resp.status} - {error_text[:100]}")
                    return

                data = await resp.json()
                prices = data.get("prices", [])
                volumes = data.get("total_volumes", [])
                market_caps = data.get("market_caps", [])

                query = """
                    INSERT INTO token_metrics_aggregated
                    (time, token_id, vwap_price, total_volume_24h, market_cap)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (time, token_id) DO NOTHING
                """

                count = 0
                for i, (timestamp, price) in enumerate(prices):
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                    volume = volumes[i][1] if i < len(volumes) else 0
                    mcap = market_caps[i][1] if i < len(market_caps) else 0

                    try:
                        await Database.execute(query, dt, token["id"], price, volume, mcap)
                        count += 1
                    except Exception as e:
                        pass

                logger.info(f"Backfilled {count} data points for {token['symbol']} (days {from_days} to {to_days})")

        except Exception as e:
            logger.error(f"Error backfilling range for {token['symbol']}: {e}")

    async def _backfill_market_references(self, days: int):
        """Backfill BTC/ETH historical data (supports up to 2 years with Pro API)"""
        async with aiohttp.ClientSession() as session:
            for coin_id, symbol in [("bitcoin", "BTC"), ("ethereum", "ETH")]:
                # For > 365 days, use range endpoint for older data first
                if days > 365:
                    await self._backfill_reference_range(session, coin_id, symbol, days, 365)
                    await asyncio.sleep(0.3 if self.coingecko_api_key else 1.5)

                url = f"{self.coingecko_base}/coins/{coin_id}/market_chart"
                params = {
                    "vs_currency": "usd",
                    "days": min(days, 365),
                    "interval": "hourly"
                }

                try:
                    headers = self._get_coingecko_headers()
                    async with session.get(url, params=params, headers=headers, timeout=60) as resp:
                        if resp.status != 200:
                            continue

                        data = await resp.json()
                        prices = data.get("prices", [])
                        volumes = data.get("total_volumes", [])
                        market_caps = data.get("market_caps", [])

                        query = """
                            INSERT INTO market_prices (time, symbol, price, volume_24h, market_cap)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (time, symbol) DO NOTHING
                        """

                        count = 0
                        for i, (timestamp, price) in enumerate(prices):
                            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                            volume = volumes[i][1] if i < len(volumes) else 0
                            mcap = market_caps[i][1] if i < len(market_caps) else 0

                            try:
                                await Database.execute(query, dt, symbol, price, volume, mcap)
                                count += 1
                            except:
                                pass

                        logger.info(f"Backfilled {count} data points for {symbol}")

                except Exception as e:
                    logger.error(f"Error backfilling {symbol}: {e}")

                await asyncio.sleep(0.3 if self.coingecko_api_key else 1.5)

    async def _backfill_reference_range(self, session: aiohttp.ClientSession, coin_id: str, symbol: str, from_days: int, to_days: int):
        """Backfill BTC/ETH for a specific date range"""
        now = datetime.now(timezone.utc)
        from_timestamp = int((now - timedelta(days=from_days)).timestamp())
        to_timestamp = int((now - timedelta(days=to_days)).timestamp())

        url = f"{self.coingecko_base}/coins/{coin_id}/market_chart/range"
        params = {
            "vs_currency": "usd",
            "from": from_timestamp,
            "to": to_timestamp
        }

        try:
            headers = self._get_coingecko_headers()
            async with session.get(url, params=params, headers=headers, timeout=60) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()
                prices = data.get("prices", [])
                volumes = data.get("total_volumes", [])
                market_caps = data.get("market_caps", [])

                query = """
                    INSERT INTO market_prices (time, symbol, price, volume_24h, market_cap)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (time, symbol) DO NOTHING
                """

                count = 0
                for i, (timestamp, price) in enumerate(prices):
                    dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
                    volume = volumes[i][1] if i < len(volumes) else 0
                    mcap = market_caps[i][1] if i < len(market_caps) else 0

                    try:
                        await Database.execute(query, dt, symbol, price, volume, mcap)
                        count += 1
                    except:
                        pass

                logger.info(f"Backfilled {count} data points for {symbol} (days {from_days} to {to_days})")

        except Exception as e:
            logger.error(f"Error backfilling range for {symbol}: {e}")


# Singleton instance
_collector: Optional[HistoricalCollector] = None


async def get_collector() -> HistoricalCollector:
    """Get or create singleton collector"""
    global _collector
    if _collector is None:
        _collector = HistoricalCollector()
    return _collector


async def run_hourly_collection():
    """Entry point for hourly collection job"""
    collector = await get_collector()
    await collector.collect_hourly_snapshot()


async def run_backfill(days: int = 30):
    """Entry point for backfill job"""
    collector = await get_collector()
    await collector.backfill_historical_data(days)
