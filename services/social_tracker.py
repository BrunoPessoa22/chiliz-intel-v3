"""
Social Media Tracker using X Premium API ($200/mo)
Tracks mentions, sentiment, and engagement for fan tokens
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import x_api_config
from services.database import Database, get_token_id, get_all_tokens

logger = logging.getLogger(__name__)


class SocialTracker:
    """Tracks X/Twitter social metrics for fan tokens"""

    def __init__(self):
        self.bearer_token = x_api_config.bearer_token
        self.base_url = x_api_config.base_url
        self.search_queries = x_api_config.search_queries
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "Content-Type": "application/json",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search_recent_tweets(self, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search recent tweets using X API v2.
        Premium tier allows access to full archive and higher rate limits.
        """
        url = f"{self.base_url}/tweets/search/recent"

        # Calculate time range (last 24 hours)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=24)

        params = {
            "query": f"{query} -is:retweet lang:en",
            "max_results": min(max_results, 100),
            "start_time": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tweet.fields": "created_at,public_metrics,author_id,text",
            "expansions": "author_id",
            "user.fields": "public_metrics,verified",
        }

        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                elif resp.status == 429:
                    logger.warning("X API rate limit hit, waiting...")
                    await asyncio.sleep(60)
                    return []
                else:
                    logger.warning(f"X API error: {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Error searching tweets: {e}")
            return []

    def analyze_sentiment(self, text: str) -> str:
        """
        Simple rule-based sentiment analysis.
        Returns: 'positive', 'negative', or 'neutral'
        """
        text_lower = text.lower()

        positive_words = [
            "bullish", "moon", "pump", "buy", "hodl", "great", "amazing",
            "love", "best", "winning", "up", "gain", "profit", "rocket",
            "lambo", "diamond", "hands", "strong", "growth", "rally"
        ]
        negative_words = [
            "bearish", "dump", "sell", "crash", "down", "loss", "scam",
            "rug", "dead", "terrible", "worst", "falling", "drop", "panic",
            "fear", "weak", "bad", "fail", "rekt", "bag"
        ]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"

    def calculate_engagement(self, tweet: Dict[str, Any]) -> int:
        """Calculate total engagement for a tweet"""
        metrics = tweet.get("public_metrics", {})
        return (
            metrics.get("retweet_count", 0) +
            metrics.get("reply_count", 0) +
            metrics.get("like_count", 0) +
            metrics.get("quote_count", 0)
        )

    def is_influencer(self, user: Dict[str, Any]) -> bool:
        """Check if user is an influencer (>10k followers or verified)"""
        metrics = user.get("public_metrics", {})
        return (
            metrics.get("followers_count", 0) >= 10000 or
            user.get("verified", False)
        )

    async def collect_social_data(self, token: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Collect social metrics for a single token"""
        symbol = token["symbol"]
        query = self.search_queries.get(symbol)
        if not query:
            return None

        token_id = await get_token_id(symbol)
        if not token_id:
            return None

        tweets = await self.search_recent_tweets(query)
        now = datetime.now(timezone.utc)

        if not tweets:
            # Return zero metrics if no tweets found
            return {
                "time": now,
                "token_id": token_id,
                "tweet_count_24h": 0,
                "mention_count_24h": 0,
                "engagement_total": 0,
                "sentiment_score": 0.5,  # Neutral
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "influencer_mentions": 0,
            }

        # Analyze tweets
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        total_engagement = 0
        influencer_mentions = 0

        for tweet in tweets:
            # Sentiment analysis
            sentiment = self.analyze_sentiment(tweet.get("text", ""))
            if sentiment == "positive":
                positive_count += 1
            elif sentiment == "negative":
                negative_count += 1
            else:
                neutral_count += 1

            # Engagement
            total_engagement += self.calculate_engagement(tweet)

        # Calculate sentiment score (0-1, where 0.5 is neutral)
        total_tweets = len(tweets)
        if total_tweets > 0:
            sentiment_score = (positive_count - negative_count + total_tweets) / (2 * total_tweets)
        else:
            sentiment_score = 0.5

        return {
            "time": now,
            "token_id": token_id,
            "tweet_count_24h": total_tweets,
            "mention_count_24h": total_tweets,  # Each tweet is a mention
            "engagement_total": total_engagement,
            "sentiment_score": sentiment_score,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "influencer_mentions": influencer_mentions,
        }

    async def collect_all(self) -> int:
        """Collect social data for all tokens"""
        tokens = await get_all_tokens()
        all_data = []

        for token in tokens:
            data = await self.collect_social_data(token)
            if data:
                all_data.append(data)
            # Rate limiting: stay well under 450 requests/15min
            await asyncio.sleep(5)

        if all_data:
            await self._insert_social_data(all_data)

        logger.info(f"Collected {len(all_data)} social records")
        return len(all_data)

    async def _insert_social_data(self, data: List[Dict[str, Any]]):
        """Batch insert social data"""
        query = """
            INSERT INTO social_metrics
            (time, token_id, tweet_count_24h, mention_count_24h, engagement_total,
             sentiment_score, positive_count, negative_count, neutral_count,
             influencer_mentions)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (time, token_id) DO UPDATE SET
                tweet_count_24h = EXCLUDED.tweet_count_24h,
                engagement_total = EXCLUDED.engagement_total,
                sentiment_score = EXCLUDED.sentiment_score
        """

        args = [
            (
                d["time"], d["token_id"], d["tweet_count_24h"], d["mention_count_24h"],
                d["engagement_total"], d["sentiment_score"], d["positive_count"],
                d["negative_count"], d["neutral_count"], d["influencer_mentions"]
            )
            for d in data
        ]

        await Database.executemany(query, args)


async def run_tracker():
    """Main tracking loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["social"]
    logger.info(f"Starting social tracker (interval: {interval}s)")

    while True:
        try:
            async with SocialTracker() as tracker:
                count = await tracker.collect_all()
                logger.info(f"Social tracking complete: {count} records")
        except Exception as e:
            logger.error(f"Social tracking error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_tracker())
