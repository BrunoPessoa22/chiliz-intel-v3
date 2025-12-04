"""
Social Signal Tracker - Real-time social signal tracking from X/Twitter
Stores individual signals for UI display and aggregates metrics
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import quote

import aiohttp

from config.settings import x_api_config
from services.database import Database, get_token_id, get_all_tokens

logger = logging.getLogger(__name__)

# Categories for signals
CATEGORIES = {
    'crypto': ['$CHZ', '$BAR', '$PSG', 'fan token', 'crypto', 'blockchain', 'web3'],
    'sports': ['match', 'game', 'goal', 'win', 'champion', 'league', 'fixture'],
    'fantoken': ['fan token', 'socios', 'chiliz', 'fanx'],
}


class SocialSignalTracker:
    """Tracks X/Twitter signals for fan tokens in real-time"""

    def __init__(self):
        self.bearer_token = x_api_config.bearer_token
        self.base_url = x_api_config.base_url
        self.search_queries = x_api_config.search_queries
        self.session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self.recent_signals: List[Dict] = []
        self.max_recent = 200

    async def __aenter__(self):
        # URL decode the bearer token if it's encoded
        token = self.bearer_token
        if token and '%' in token:
            from urllib.parse import unquote
            token = unquote(token)

        logger.info(f"Creating Twitter session, token length: {len(token) if token else 0}")

        self.session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {token}",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search_recent_tweets(
        self,
        query: str,
        max_results: int = 50,
        since_minutes: int = 60
    ) -> List[Dict]:
        """Search recent tweets using X API v2"""
        url = f"{self.base_url}/tweets/search/recent"

        # Basic tier doesn't support time range well, just get recent tweets
        params = {
            "query": f"{query} -is:retweet lang:en",
            "max_results": min(max_results, 10),  # Limit to 10 for Basic tier
            "tweet.fields": "created_at,public_metrics,author_id,text,entities",
            "expansions": "author_id",
            "user.fields": "public_metrics,verified,username,name",
        }

        try:
            logger.info(f"Searching Twitter: query={query}, url={url}")
            async with self.session.get(url, params=params) as resp:
                logger.info(f"Twitter API response status: {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    tweets = data.get("data", [])
                    logger.info(f"Twitter API returned {len(tweets)} tweets")
                    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

                    # Attach user data to tweets
                    for tweet in tweets:
                        author_id = tweet.get("author_id")
                        if author_id and author_id in users:
                            tweet["author"] = users[author_id]

                    return tweets

                elif resp.status == 429:
                    logger.warning("X API rate limit hit")
                    return []
                else:
                    error_text = await resp.text()
                    logger.warning(f"X API error {resp.status}: {error_text[:500]}")
                    return []

        except Exception as e:
            logger.error(f"Error searching tweets: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def analyze_sentiment(self, text: str) -> tuple[str, float]:
        """
        Analyze sentiment of text.
        Returns: (sentiment_label, sentiment_score)
        """
        text_lower = text.lower()

        positive_words = [
            "bullish", "moon", "pump", "buy", "hodl", "great", "amazing",
            "love", "best", "winning", "up", "gain", "profit", "rocket",
            "diamond", "hands", "strong", "growth", "rally", "surge",
            "breakout", "ath", "all time high", "huge", "massive"
        ]
        negative_words = [
            "bearish", "dump", "sell", "crash", "down", "loss", "scam",
            "rug", "dead", "terrible", "worst", "falling", "drop", "panic",
            "fear", "weak", "bad", "fail", "rekt", "bag", "dump", "plunge"
        ]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        total = positive_count + negative_count
        if total == 0:
            return "neutral", 0.5

        score = (positive_count + 0.5 * total) / (2 * total)

        if positive_count > negative_count:
            return "positive", min(1.0, 0.5 + (score - 0.5) * 2)
        elif negative_count > positive_count:
            return "negative", max(0.0, 0.5 - (0.5 - score) * 2)
        return "neutral", 0.5

    def categorize_signal(self, text: str) -> List[str]:
        """Categorize a signal based on content"""
        text_lower = text.lower()
        categories = []

        for category, keywords in CATEGORIES.items():
            if any(kw.lower() in text_lower for kw in keywords):
                categories.append(category)

        return categories if categories else ['general']

    def is_high_priority(self, tweet: Dict, categories: List[str]) -> bool:
        """Determine if a signal is high priority"""
        # High priority if it's crypto + sports intersection
        if 'crypto' in categories and 'sports' in categories:
            return True

        # High priority if from influencer
        author = tweet.get("author", {})
        metrics = author.get("public_metrics", {})
        if metrics.get("followers_count", 0) >= 50000:
            return True

        # High priority if verified
        if author.get("verified", False):
            return True

        # High priority if high engagement
        tweet_metrics = tweet.get("public_metrics", {})
        engagement = (
            tweet_metrics.get("retweet_count", 0) +
            tweet_metrics.get("like_count", 0) +
            tweet_metrics.get("reply_count", 0)
        )
        if engagement >= 100:
            return True

        return False

    async def process_tweet(self, tweet: Dict, token_symbol: str) -> Dict:
        """Process a tweet into a signal"""
        author = tweet.get("author", {})
        metrics = tweet.get("public_metrics", {})
        author_metrics = author.get("public_metrics", {})

        text = tweet.get("text", "")
        sentiment, sentiment_score = self.analyze_sentiment(text)
        categories = self.categorize_signal(text)

        engagement = (
            metrics.get("retweet_count", 0) +
            metrics.get("like_count", 0) +
            metrics.get("reply_count", 0) +
            metrics.get("quote_count", 0)
        )

        is_influencer = author_metrics.get("followers_count", 0) >= 10000 or author.get("verified", False)

        signal = {
            'time': datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00')),
            'token_symbol': token_symbol,
            'signal_type': 'tweet',
            'source': f"@{author.get('username', 'unknown')}",
            'source_url': f"https://twitter.com/{author.get('username', 'i')}/status/{tweet['id']}",
            'title': f"{author.get('name', 'Unknown')} on {token_symbol}",
            'content': text,
            'sentiment': sentiment,
            'sentiment_score': sentiment_score,
            'engagement': engagement,
            'followers': author_metrics.get("followers_count", 0),
            'is_influencer': is_influencer,
            'is_high_priority': self.is_high_priority(tweet, categories),
            'categories': categories,
            'raw_data': tweet,
        }

        return signal

    async def collect_signals(self, token_symbol: str) -> List[Dict]:
        """Collect signals for a token"""
        query = self.search_queries.get(token_symbol)
        if not query:
            return []

        tweets = await self.search_recent_tweets(query, max_results=50, since_minutes=60)
        signals = []

        for tweet in tweets:
            signal = await self.process_tweet(tweet, token_symbol)
            signals.append(signal)

        return signals

    async def collect_all_signals(self) -> int:
        """Collect signals for all tokens with rotation"""
        tokens = await get_all_tokens()
        all_signals = []

        # Priority tokens - tier 1 (always query)
        tier1_tokens = ['CHZ', 'BAR', 'PSG']

        # Tier 2 tokens - rotate through these
        tier2_tokens = [
            'JUV', 'ATM', 'CITY', 'ACM', 'INTER', 'GAL', 'MENGO', 'OG',  # Major clubs
            'FLU', 'SANTOS', 'SCCP', 'SPFC', 'GALO', 'VERDAO', 'VASCO',  # Brazilian
            'LAZIO', 'NAP', 'ASR', 'AFC', 'SPURS',  # European
            'TRA', 'FB', 'BJK', 'BENFICA', 'PORTO',  # Other major
            'ARG', 'ALPINE', 'UFC',  # Other categories
        ]

        # Filter to tokens that have search queries
        tokens_with_queries = [t for t in tokens if t["symbol"] in self.search_queries]

        # Always include tier 1
        tier1_to_query = [t for t in tokens_with_queries if t["symbol"] in tier1_tokens]

        # Rotate through tier 2 based on current hour (different tokens each collection)
        from datetime import datetime
        hour = datetime.now().hour
        tier2_available = [t for t in tokens_with_queries if t["symbol"] in tier2_tokens]

        # Pick 2 tokens from tier 2 based on rotation
        rotation_index = (hour % 12) * 2  # Changes every hour, cycles through ~24 tokens
        tier2_to_query = tier2_available[rotation_index:rotation_index + 2]

        # If we didn't get enough, wrap around
        if len(tier2_to_query) < 2 and tier2_available:
            remaining = 2 - len(tier2_to_query)
            tier2_to_query.extend(tier2_available[:remaining])

        # Combine: 3 tier1 + 2 tier2 = 5 tokens per collection (within rate limits)
        tokens_to_query = tier1_to_query + tier2_to_query

        logger.info(f"Collecting social signals for {len(tokens_to_query)} tokens: {[t['symbol'] for t in tokens_to_query]}")

        for token in tokens_to_query:
            symbol = token["symbol"]

            try:
                signals = await self.collect_signals(symbol)
                all_signals.extend(signals)
                logger.info(f"Collected {len(signals)} signals for {symbol}")
            except Exception as e:
                logger.warning(f"Error collecting {symbol}: {e}")
                import traceback
                logger.warning(traceback.format_exc())

            # Rate limiting - 5 seconds between requests
            await asyncio.sleep(5)

        # Sort by time and priority
        all_signals.sort(key=lambda x: (not x['is_high_priority'], x['time']), reverse=True)

        # Update in-memory cache
        self.recent_signals = all_signals[:self.max_recent]

        # Save to database
        if all_signals:
            await self._save_signals(all_signals)

        logger.info(f"Collected {len(all_signals)} social signals")
        return len(all_signals)

    async def _save_signals(self, signals: List[Dict]):
        """Save signals to database"""
        query = """
            INSERT INTO social_signals
            (time, token_id, signal_type, source, source_url, title, content,
             sentiment, sentiment_score, engagement, followers, is_influencer,
             is_high_priority, categories, raw_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT DO NOTHING
        """

        for signal in signals:
            try:
                token_id = await get_token_id(signal['token_symbol'])

                await Database.execute(
                    query,
                    signal['time'],
                    token_id,
                    signal['signal_type'],
                    signal['source'],
                    signal['source_url'],
                    signal['title'][:300] if signal['title'] else None,
                    signal['content'],
                    signal['sentiment'],
                    signal['sentiment_score'],
                    signal['engagement'],
                    signal['followers'],
                    signal['is_influencer'],
                    signal['is_high_priority'],
                    signal['categories'],
                    json.dumps(signal['raw_data'], default=str),
                )
            except Exception as e:
                logger.error(f"Error saving signal: {e}")

    async def start_tracking(self, interval_seconds: int = 300):
        """Start continuous signal tracking"""
        logger.info(f"Starting social signal tracking (interval: {interval_seconds}s)")
        self._running = True

        while self._running:
            try:
                async with self as tracker:
                    count = await tracker.collect_all_signals()
                    logger.info(f"Social tracking complete: {count} signals")
            except Exception as e:
                logger.error(f"Social tracking error: {e}")

            await asyncio.sleep(interval_seconds)

    async def stop_tracking(self):
        """Stop tracking"""
        self._running = False


# Singleton instance
_signal_tracker: Optional[SocialSignalTracker] = None


async def get_signal_tracker() -> SocialSignalTracker:
    """Get or create signal tracker instance"""
    global _signal_tracker
    if _signal_tracker is None:
        _signal_tracker = SocialSignalTracker()
    return _signal_tracker


async def start_social_tracking():
    """Start social signal tracking"""
    tracker = await get_signal_tracker()
    await tracker.start_tracking()


async def stop_social_tracking():
    """Stop social signal tracking"""
    global _signal_tracker
    if _signal_tracker:
        await _signal_tracker.stop_tracking()
        _signal_tracker = None


async def collect_signals_once() -> int:
    """
    One-time collection of social signals.
    Used by API endpoint for manual trigger.
    """
    logger.info("Starting one-time social signal collection")
    tracker = SocialSignalTracker()
    try:
        async with tracker as t:
            count = await t.collect_all_signals()
            logger.info(f"Social collection completed: {count} signals")
            return count
    except Exception as e:
        logger.error(f"Social collection failed: {e}")
        return 0


# API helper functions
async def get_recent_signals(
    limit: int = 50,
    token_symbol: Optional[str] = None,
    signal_type: Optional[str] = None,
    high_priority_only: bool = False,
    categories: Optional[List[str]] = None
) -> List[Dict]:
    """Get recent social signals from database"""

    conditions = ["1=1"]
    params = []
    param_idx = 1

    if token_symbol:
        conditions.append(f"""
            token_id = (SELECT id FROM fan_tokens WHERE symbol = ${param_idx})
        """)
        params.append(token_symbol)
        param_idx += 1

    if signal_type:
        conditions.append(f"signal_type = ${param_idx}")
        params.append(signal_type)
        param_idx += 1

    if high_priority_only:
        conditions.append("is_high_priority = TRUE")

    if categories:
        conditions.append(f"categories && ${param_idx}::text[]")
        params.append(categories)
        param_idx += 1

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            ss.time, ft.symbol as token_symbol, ss.signal_type, ss.source,
            ss.source_url, ss.title, ss.content, ss.sentiment, ss.sentiment_score,
            ss.engagement, ss.followers, ss.is_influencer, ss.is_high_priority,
            ss.categories
        FROM social_signals ss
        LEFT JOIN fan_tokens ft ON ss.token_id = ft.id
        WHERE {where_clause}
        ORDER BY ss.is_high_priority DESC, ss.time DESC
        LIMIT {limit}
    """

    rows = await Database.fetch(query, *params)

    return [
        {
            'time': row['time'].isoformat(),
            'token': row['token_symbol'],
            'type': row['signal_type'],
            'source': row['source'],
            'url': row['source_url'],
            'title': row['title'],
            'content': row['content'],
            'sentiment': row['sentiment'],
            'sentiment_score': float(row['sentiment_score']) if row['sentiment_score'] else 0.5,
            'engagement': row['engagement'],
            'followers': row['followers'],
            'is_influencer': row['is_influencer'],
            'is_high_priority': row['is_high_priority'],
            'categories': row['categories'] or [],
        }
        for row in rows
    ]


async def get_signal_stats(hours: int = 24) -> Dict:
    """Get signal statistics for the last N hours"""

    query = """
        SELECT
            ft.symbol,
            COUNT(*) as signal_count,
            SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive_count,
            SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count,
            SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
            AVG(sentiment_score) as avg_sentiment,
            SUM(engagement) as total_engagement,
            SUM(CASE WHEN is_influencer THEN 1 ELSE 0 END) as influencer_count,
            SUM(CASE WHEN is_high_priority THEN 1 ELSE 0 END) as high_priority_count
        FROM social_signals ss
        JOIN fan_tokens ft ON ss.token_id = ft.id
        WHERE ss.time > NOW() - INTERVAL '%s hours'
        GROUP BY ft.symbol
        ORDER BY signal_count DESC
    """ % hours

    rows = await Database.fetch(query)

    return {
        'period_hours': hours,
        'tokens': [
            {
                'symbol': row['symbol'],
                'signal_count': row['signal_count'],
                'positive_count': row['positive_count'],
                'negative_count': row['negative_count'],
                'neutral_count': row['neutral_count'],
                'avg_sentiment': float(row['avg_sentiment']) if row['avg_sentiment'] else 0.5,
                'total_engagement': row['total_engagement'],
                'influencer_mentions': row['influencer_count'],
                'high_priority_signals': row['high_priority_count'],
                'sentiment_label': 'positive' if (row['avg_sentiment'] or 0.5) > 0.55 else 'negative' if (row['avg_sentiment'] or 0.5) < 0.45 else 'neutral',
            }
            for row in rows
        ]
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_social_tracking())
