"""
Reddit Community Signal Tracker
Free API for monitoring fan token discussions on Reddit
https://www.reddit.com/dev/api/
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

import aiohttp

from config.settings import reddit_config, FAN_TOKENS
from services.database import Database, get_token_id

logger = logging.getLogger(__name__)

# Map symbols to team names and search terms for Reddit
SYMBOL_TO_REDDIT_TERMS = {
    "CHZ": ["chiliz", "chz", "socios"],
    "BAR": ["barcelona", "barca", "bar token"],
    "PSG": ["paris saint germain", "psg"],
    "JUV": ["juventus", "juve"],
    "ACM": ["ac milan", "milan"],
    "INTER": ["inter milan", "inter"],
    "ASR": ["as roma", "roma"],
    "NAP": ["napoli", "nap token"],
    "CITY": ["manchester city", "man city", "mcfc"],
    "AFC": ["arsenal", "gunners", "afc token"],
    "SPURS": ["tottenham", "spurs", "thfc"],
    "GAL": ["galatasaray", "gala"],
    "MENGO": ["flamengo", "mengo"],
    "ARG": ["argentina", "afa"],
    "POR": ["portugal", "fpf"],
    "UFC": ["ufc"],
    "OG": ["og esports", "og dota"],
}


class RedditTracker:
    """
    Reddit API integration for community signal tracking.
    Uses OAuth2 for authentication (free tier: 60 requests/minute).
    """

    def __init__(self):
        self.client_id = reddit_config.client_id
        self.client_secret = reddit_config.client_secret
        self.user_agent = reddit_config.user_agent
        self.subreddits = reddit_config.subreddits
        self.base_url = "https://oauth.reddit.com"
        self.auth_url = "https://www.reddit.com/api/v1/access_token"
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        await self._authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _authenticate(self):
        """Get OAuth2 access token for Reddit API."""
        if not self.client_id or not self.client_secret:
            logger.warning("Reddit credentials not configured")
            return

        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials"}
        headers = {"User-Agent": self.user_agent}

        try:
            async with self.session.post(
                self.auth_url,
                auth=auth,
                data=data,
                headers=headers
            ) as resp:
                if resp.status == 200:
                    token_data = await resp.json()
                    self.access_token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expiry = datetime.now(timezone.utc).timestamp() + expires_in - 60
                    logger.info("Reddit OAuth2 token obtained successfully")
                else:
                    error = await resp.text()
                    logger.error(f"Reddit auth failed: {resp.status} - {error[:200]}")
        except Exception as e:
            logger.error(f"Reddit authentication error: {e}")

    async def _ensure_authenticated(self):
        """Refresh token if expired."""
        if not self.access_token:
            await self._authenticate()
        elif self.token_expiry and datetime.now(timezone.utc).timestamp() > self.token_expiry:
            await self._authenticate()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with current auth token."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": self.user_agent,
        }

    async def search_subreddit(
        self,
        subreddit: str,
        query: str,
        limit: int = 25,
        time_filter: str = "day"  # hour, day, week, month, year, all
    ) -> List[Dict]:
        """
        Search a specific subreddit for posts matching query.
        """
        await self._ensure_authenticated()
        if not self.access_token:
            return []

        url = f"{self.base_url}/r/{subreddit}/search"
        params = {
            "q": query,
            "restrict_sr": "true",  # Only search this subreddit
            "sort": "relevance",
            "t": time_filter,
            "limit": limit,
        }

        try:
            async with self.session.get(url, headers=self._get_headers(), params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    posts = data.get("data", {}).get("children", [])
                    return [p["data"] for p in posts]
                elif resp.status == 429:
                    logger.warning("Reddit rate limit hit, backing off...")
                    await asyncio.sleep(60)
                    return []
                else:
                    return []
        except Exception as e:
            logger.error(f"Error searching r/{subreddit}: {e}")
            return []

    async def get_subreddit_new(
        self,
        subreddit: str,
        limit: int = 25
    ) -> List[Dict]:
        """
        Get newest posts from a subreddit.
        """
        await self._ensure_authenticated()
        if not self.access_token:
            return []

        url = f"{self.base_url}/r/{subreddit}/new"
        params = {"limit": limit}

        try:
            async with self.session.get(url, headers=self._get_headers(), params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    posts = data.get("data", {}).get("children", [])
                    return [p["data"] for p in posts]
                else:
                    return []
        except Exception as e:
            logger.error(f"Error fetching r/{subreddit}/new: {e}")
            return []

    async def get_hot_posts(
        self,
        subreddit: str,
        limit: int = 25
    ) -> List[Dict]:
        """
        Get hot/trending posts from a subreddit.
        """
        await self._ensure_authenticated()
        if not self.access_token:
            return []

        url = f"{self.base_url}/r/{subreddit}/hot"
        params = {"limit": limit}

        try:
            async with self.session.get(url, headers=self._get_headers(), params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    posts = data.get("data", {}).get("children", [])
                    return [p["data"] for p in posts]
                else:
                    return []
        except Exception as e:
            logger.error(f"Error fetching r/{subreddit}/hot: {e}")
            return []

    def _analyze_post_sentiment(self, title: str, content: str) -> tuple:
        """
        Simple keyword-based sentiment analysis for Reddit posts.
        Returns (sentiment_label, sentiment_score).
        """
        text = f"{title} {content}".lower()

        positive_words = [
            "bullish", "moon", "buy", "pump", "amazing", "great", "love",
            "exciting", "potential", "win", "winning", "victory", "champion",
            "partnership", "adoption", "growth", "surge", "rally",
        ]
        negative_words = [
            "bearish", "dump", "sell", "crash", "scam", "rugpull", "rug",
            "loss", "losing", "bad", "terrible", "avoid", "warning",
            "concern", "worried", "drop", "plunge", "decline",
        ]

        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)

        if positive_count > negative_count:
            score = min(0.5 + (positive_count - negative_count) * 0.1, 0.95)
            return "positive", score
        elif negative_count > positive_count:
            score = max(0.5 - (negative_count - positive_count) * 0.1, 0.05)
            return "negative", score
        else:
            return "neutral", 0.5

    def _categorize_post(self, title: str, content: str, subreddit: str) -> List[str]:
        """
        Categorize post based on content and subreddit.
        """
        text = f"{title} {content}".lower()
        categories = []

        # Crypto category
        crypto_keywords = ["crypto", "token", "coin", "blockchain", "web3", "defi", "nft"]
        if any(kw in text for kw in crypto_keywords) or subreddit in ["CryptoCurrency", "CryptoMoonShots"]:
            categories.append("crypto")

        # Sports category
        sports_keywords = ["match", "game", "score", "player", "transfer", "season", "league", "cup"]
        sports_subreddits = ["Barca", "psg", "Juve", "ACMilan", "Gunners", "MCFC", "formula1", "MMA", "ufc"]
        if any(kw in text for kw in sports_keywords) or subreddit in sports_subreddits:
            categories.append("sports")

        # Fan token category
        fantoken_keywords = ["fan token", "chiliz", "socios", "fantoken"]
        if any(kw in text for kw in fantoken_keywords):
            categories.append("fantoken")

        if not categories:
            categories.append("general")

        return categories

    def _match_token(self, title: str, content: str) -> Optional[str]:
        """
        Match post to a specific token based on mentions.
        """
        text = f"{title} {content}".lower()

        for symbol, terms in SYMBOL_TO_REDDIT_TERMS.items():
            for term in terms:
                if term.lower() in text:
                    return symbol

        # Also check for direct symbol mentions
        for token in FAN_TOKENS:
            symbol = token["symbol"]
            if f"${symbol.lower()}" in text or f" {symbol.lower()} " in text:
                return symbol

        return None

    async def collect_fan_token_signals(self) -> List[Dict]:
        """
        Collect Reddit posts mentioning fan tokens from all monitored subreddits.
        Returns normalized signals ready for database.
        """
        signals = []
        seen_post_ids = set()

        # Search crypto subreddits for fan token mentions
        crypto_subreddits = ["chiliz", "socios", "CryptoCurrency", "altcoin"]

        for subreddit in crypto_subreddits:
            try:
                # Search for fan token related posts
                posts = await self.search_subreddit(
                    subreddit,
                    "fan token OR chiliz OR socios",
                    limit=25,
                    time_filter="day"
                )

                for post in posts:
                    post_id = post.get("id")
                    if post_id in seen_post_ids:
                        continue
                    seen_post_ids.add(post_id)

                    signal = self._process_post(post, subreddit)
                    if signal:
                        signals.append(signal)

                await asyncio.sleep(1)  # Rate limiting

            except Exception as e:
                logger.error(f"Error collecting from r/{subreddit}: {e}")

        # Get new posts from team-specific subreddits
        team_subreddits = ["Barca", "psg", "Juve", "ACMilan", "Gunners", "MCFC", "Galatasaray", "flamengo"]

        for subreddit in team_subreddits:
            try:
                posts = await self.get_new_posts(subreddit, limit=10)

                for post in posts:
                    post_id = post.get("id")
                    if post_id in seen_post_ids:
                        continue

                    # Only include if mentions crypto/token
                    text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
                    if any(kw in text for kw in ["token", "crypto", "chiliz", "socios", "fan token"]):
                        seen_post_ids.add(post_id)
                        signal = self._process_post(post, subreddit)
                        if signal:
                            signals.append(signal)

                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error collecting from r/{subreddit}: {e}")

        logger.info(f"Collected {len(signals)} Reddit signals")
        return signals

    async def get_new_posts(self, subreddit: str, limit: int = 25) -> List[Dict]:
        """Alias for get_subreddit_new."""
        return await self.get_subreddit_new(subreddit, limit)

    def _process_post(self, post: Dict, subreddit: str) -> Optional[Dict]:
        """
        Process a Reddit post into a normalized signal.
        """
        title = post.get("title", "")
        content = post.get("selftext", "")
        created_utc = post.get("created_utc", 0)

        # Basic validation
        if not title:
            return None

        # Match to token
        token_symbol = self._match_token(title, content)

        # Analyze sentiment
        sentiment, sentiment_score = self._analyze_post_sentiment(title, content)

        # Categorize
        categories = self._categorize_post(title, content, subreddit)

        # Determine priority
        is_high_priority = (
            "crypto" in categories and "sports" in categories
        ) or post.get("score", 0) > 100

        return {
            "time": datetime.fromtimestamp(created_utc, tz=timezone.utc),
            "token_symbol": token_symbol,
            "post_id": post.get("id"),
            "subreddit": subreddit,
            "title": title[:500],  # Truncate
            "content": content[:2000] if content else None,
            "url": f"https://reddit.com{post.get('permalink', '')}",
            "author": post.get("author"),
            "signal_type": "post",
            "score": post.get("score", 0),
            "upvote_ratio": post.get("upvote_ratio", 0.5),
            "num_comments": post.get("num_comments", 0),
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "categories": categories,
            "is_high_priority": is_high_priority,
            "is_trending": post.get("score", 0) > 50,
        }

    async def save_signals(self, signals: List[Dict]):
        """Save Reddit signals to database."""
        query = """
            INSERT INTO reddit_signals
            (time, token_id, post_id, subreddit, title, content, url, author,
             signal_type, score, upvote_ratio, num_comments,
             sentiment, sentiment_score, categories, is_high_priority, is_trending)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
            ON CONFLICT (post_id) DO UPDATE SET
                score = EXCLUDED.score,
                num_comments = EXCLUDED.num_comments,
                is_trending = EXCLUDED.is_trending
        """

        saved = 0
        for signal in signals:
            try:
                token_id = None
                if signal.get("token_symbol"):
                    token_id = await get_token_id(signal["token_symbol"])

                await Database.execute(
                    query,
                    signal["time"],
                    token_id,
                    signal["post_id"],
                    signal["subreddit"],
                    signal["title"],
                    signal.get("content"),
                    signal["url"],
                    signal["author"],
                    signal["signal_type"],
                    signal["score"],
                    signal["upvote_ratio"],
                    signal["num_comments"],
                    signal["sentiment"],
                    signal["sentiment_score"],
                    signal["categories"],
                    signal["is_high_priority"],
                    signal["is_trending"],
                )
                saved += 1
            except Exception as e:
                logger.error(f"Error saving Reddit signal: {e}")

        logger.info(f"Saved {saved}/{len(signals)} Reddit signals")


async def collect_reddit_signals() -> int:
    """
    One-time collection of Reddit signals.
    Called by the worker every 15-30 minutes.
    """
    if not reddit_config.client_id:
        logger.warning("Reddit API not configured, skipping collection")
        return 0

    try:
        async with RedditTracker() as tracker:
            signals = await tracker.collect_fan_token_signals()
            if signals:
                await tracker.save_signals(signals)
            return len(signals)
    except Exception as e:
        logger.error(f"Reddit collection failed: {e}")
        return 0


async def get_reddit_summary(symbol: str, hours: int = 24) -> Dict:
    """
    Get Reddit activity summary for a specific token.
    """
    query = """
        SELECT
            COUNT(*) as post_count,
            AVG(sentiment_score) as avg_sentiment,
            SUM(score) as total_score,
            SUM(num_comments) as total_comments,
            SUM(CASE WHEN is_high_priority THEN 1 ELSE 0 END) as high_priority_count
        FROM reddit_signals rs
        JOIN fan_tokens ft ON rs.token_id = ft.id
        WHERE ft.symbol = $1
        AND rs.time > NOW() - make_interval(hours => $2)
    """

    try:
        row = await Database.fetchrow(query, symbol.upper(), hours)
        return {
            "symbol": symbol.upper(),
            "period_hours": hours,
            "post_count": row["post_count"] or 0 if row else 0,
            "avg_sentiment": float(row["avg_sentiment"]) if row and row["avg_sentiment"] else 0.5,
            "total_score": row["total_score"] or 0 if row else 0,
            "total_comments": row["total_comments"] or 0 if row else 0,
            "high_priority_count": row["high_priority_count"] or 0 if row else 0,
        }
    except Exception as e:
        logger.error(f"Error getting Reddit summary: {e}")
        return {
            "symbol": symbol.upper(),
            "period_hours": hours,
            "post_count": 0,
            "avg_sentiment": 0.5,
        }
