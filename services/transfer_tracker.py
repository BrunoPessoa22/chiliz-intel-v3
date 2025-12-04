"""
Transfer Room - Track transfer news, rumors, and their impact on fan tokens
Correlates player transfers with social media spikes and price movements
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import aiohttp
from urllib.parse import unquote

from services.database import Database
from config.settings import x_api_config

logger = logging.getLogger(__name__)

# High-profile players that could move to fan token teams
TRACKED_PLAYERS = [
    # Global superstars
    "Neymar", "Mbappe", "Haaland", "Vinicius", "Bellingham",
    "Salah", "De Bruyne", "Kane", "Lewandowski", "Messi",
    # Rising stars
    "Yamal", "Endrick", "Mainoo", "Guler", "Garnacho",
    # Transfer-active players
    "Osimhen", "Kvaratskhelia", "Zirkzee", "Gyokeres",
]

# Team name to token symbol mapping
TEAM_TOKEN_MAP = {
    # La Liga
    "barcelona": "BAR", "barca": "BAR", "fcb": "BAR", "blaugrana": "BAR",
    "atletico": "ATM", "atletico madrid": "ATM", "atleti": "ATM",
    "valencia": "VCF",
    "sevilla": "SEVILLA",

    # Serie A
    "juventus": "JUV", "juve": "JUV",
    "ac milan": "ACM", "milan": "ACM", "rossoneri": "ACM",
    "roma": "ASR", "as roma": "ASR",
    "inter": "INTER", "inter milan": "INTER", "nerazzurri": "INTER",
    "napoli": "NAP", "ssc napoli": "NAP",

    # Premier League
    "manchester city": "CITY", "man city": "CITY", "city": "CITY",
    "arsenal": "AFC", "gunners": "AFC",
    "tottenham": "SPURS", "spurs": "SPURS",

    # Ligue 1
    "psg": "PSG", "paris": "PSG", "paris saint-germain": "PSG",
    "monaco": "ASM", "as monaco": "ASM",

    # Turkish
    "galatasaray": "GAL", "gala": "GAL",
    "fenerbahce": "FB", "fener": "FB",
    "besiktas": "BJK",

    # Brazilian
    "flamengo": "MENGO", "mengao": "MENGO",
    "fluminense": "FLU",
    "corinthians": "SCCP",
    "palmeiras": "VERDAO",
    "sao paulo": "SPFC",
}

# Credible transfer sources (Twitter handles)
TIER_1_SOURCES = [
    "fabrizioromano", "david_ornstein", "dimarzio", "mattemoretto",
    "geradoromeu", "paboromag", "thegurdianfb"
]
TIER_2_SOURCES = [
    "skysportsnews", "espnfc", "deadlinedaylive", "footballespana",
    "goal", "marca", "mundodeportivo"
]


@dataclass
class TransferEvent:
    """Represents a transfer-related event"""
    player_name: Optional[str]
    from_team: Optional[str]
    to_team: Optional[str]
    event_type: str  # 'rumor', 'interest', 'bid', 'agreement', 'official'
    headline: str
    source_type: str
    source_author: str
    tweet_id: str
    engagement: int
    sentiment_score: float
    credibility_score: float
    event_time: datetime
    related_tokens: List[str]


class TransferTracker:
    """Tracks transfer news and correlates with token activity"""

    def __init__(self):
        self.bearer_token = x_api_config.bearer_token
        if '%' in self.bearer_token:
            self.bearer_token = unquote(self.bearer_token)

    async def collect_transfer_signals(self) -> int:
        """Collect transfer-related tweets and save as events"""
        if not self.bearer_token:
            logger.warning("No Twitter bearer token configured")
            return 0

        collected = 0
        queries = x_api_config.transfer_queries

        async with aiohttp.ClientSession() as session:
            for query_name, query in queries.items():
                try:
                    events = await self._search_transfers(session, query, query_name)
                    for event in events:
                        saved = await self._save_transfer_event(event)
                        if saved:
                            collected += 1
                except Exception as e:
                    logger.error(f"Error collecting transfers for {query_name}: {e}")

        # Generate alerts for significant activity
        await self._generate_transfer_alerts()

        return collected

    async def _search_transfers(
        self,
        session: aiohttp.ClientSession,
        query: str,
        query_name: str
    ) -> List[TransferEvent]:
        """Search Twitter for transfer news"""
        events = []

        url = f"{x_api_config.base_url}/tweets/search/recent"
        headers = {"Authorization": f"Bearer {self.bearer_token}"}
        params = {
            "query": f"{query} -is:retweet lang:en",
            "max_results": 20,
            "tweet.fields": "created_at,public_metrics,author_id,text",
            "expansions": "author_id",
            "user.fields": "public_metrics,username,name,verified",
        }

        try:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    return events

                data = await resp.json()
                tweets = data.get("data", [])
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

                for tweet in tweets:
                    author = users.get(tweet.get("author_id"), {})
                    event = self._parse_tweet_to_event(tweet, author)
                    if event and event.related_tokens:
                        events.append(event)

        except Exception as e:
            logger.error(f"Twitter API error: {e}")

        return events

    def _parse_tweet_to_event(
        self,
        tweet: Dict,
        author: Dict
    ) -> Optional[TransferEvent]:
        """Parse a tweet into a TransferEvent"""
        text = tweet.get("text", "").lower()
        metrics = tweet.get("public_metrics", {})
        username = author.get("username", "").lower()

        # Determine credibility based on source
        if username in TIER_1_SOURCES:
            credibility = 0.9
            source_type = "tier1_journalist"
        elif username in TIER_2_SOURCES:
            credibility = 0.7
            source_type = "tier2_source"
        elif author.get("verified"):
            credibility = 0.5
            source_type = "verified_account"
        else:
            # Check follower count
            followers = author.get("public_metrics", {}).get("followers_count", 0)
            if followers > 100000:
                credibility = 0.4
                source_type = "large_account"
            elif followers > 10000:
                credibility = 0.3
                source_type = "medium_account"
            else:
                credibility = 0.2
                source_type = "general"

        # Extract player name if mentioned
        player_name = None
        for player in TRACKED_PLAYERS:
            if player.lower() in text:
                player_name = player
                break

        # Detect event type
        event_type = self._detect_event_type(text)

        # Find related tokens
        related_tokens = self._find_related_tokens(text)

        # Calculate engagement
        engagement = (
            metrics.get("like_count", 0) +
            metrics.get("retweet_count", 0) * 2 +
            metrics.get("reply_count", 0)
        )

        # Simple sentiment (can be enhanced with NLP)
        sentiment = self._calculate_sentiment(text)

        # Extract team names
        from_team, to_team = self._extract_teams(text)

        return TransferEvent(
            player_name=player_name,
            from_team=from_team,
            to_team=to_team,
            event_type=event_type,
            headline=tweet.get("text", "")[:500],
            source_type=source_type,
            source_author=author.get("username", "unknown"),
            tweet_id=tweet.get("id", ""),
            engagement=engagement,
            sentiment_score=sentiment,
            credibility_score=credibility,
            event_time=datetime.fromisoformat(
                tweet.get("created_at", "").replace("Z", "+00:00")
            ),
            related_tokens=related_tokens,
        )

    def _detect_event_type(self, text: str) -> str:
        """Detect the type of transfer event"""
        text = text.lower()

        if "here we go" in text or "official" in text or "announced" in text or "signed" in text:
            return "official"
        elif "agreement" in text or "agreed" in text or "done deal" in text:
            return "agreement"
        elif "bid" in text or "offer" in text or "€" in text or "$" in text:
            return "bid"
        elif "interest" in text or "monitoring" in text or "tracking" in text:
            return "interest"
        else:
            return "rumor"

    def _find_related_tokens(self, text: str) -> List[str]:
        """Find fan tokens mentioned or related to the tweet"""
        tokens = []
        text = text.lower()

        for team_name, token in TEAM_TOKEN_MAP.items():
            if team_name in text and token not in tokens:
                tokens.append(token)

        return tokens

    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score (0-1)"""
        text = text.lower()

        positive_words = [
            "excited", "amazing", "great", "fantastic", "wonderful", "perfect",
            "welcome", "love", "dream", "finally", "incredible", "brilliant"
        ]
        negative_words = [
            "sad", "disappointed", "leaving", "departure", "losing", "miss",
            "worst", "terrible", "disaster", "fear", "worried", "concern"
        ]

        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)

        if positive_count + negative_count == 0:
            return 0.5  # Neutral

        return 0.5 + (positive_count - negative_count) * 0.1

    def _extract_teams(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract from/to team from transfer text"""
        text = text.lower()

        # Patterns like "X to Y", "X joins Y", "X leaves Y"
        from_team = None
        to_team = None

        for team_name in TEAM_TOKEN_MAP.keys():
            if team_name in text:
                # Check context
                if "from " + team_name in text or "leaves " + team_name in text:
                    from_team = team_name.title()
                elif "to " + team_name in text or "joins " + team_name in text:
                    to_team = team_name.title()
                elif not to_team:  # Default to "to" if ambiguous
                    to_team = team_name.title()

        return from_team, to_team

    async def _save_transfer_event(self, event: TransferEvent) -> bool:
        """Save transfer event to database"""
        # Check for duplicates
        existing = await Database.fetchval(
            "SELECT id FROM transfer_events WHERE tweet_id = $1",
            event.tweet_id
        )
        if existing:
            return False

        # Get token_id for the primary related token
        token_id = None
        if event.related_tokens:
            token = await Database.fetchrow(
                "SELECT id FROM fan_tokens WHERE symbol = $1",
                event.related_tokens[0]
            )
            if token:
                token_id = token["id"]

        query = """
            INSERT INTO transfer_events (
                token_id, event_type, player_name, from_team, to_team,
                source_type, source_author, tweet_id, headline,
                engagement, sentiment_score, credibility_score, event_time
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        """

        try:
            await Database.execute(
                query,
                token_id,
                event.event_type,
                event.player_name,
                event.from_team,
                event.to_team,
                event.source_type,
                event.source_author,
                event.tweet_id,
                event.headline,
                event.engagement,
                event.sentiment_score,
                event.credibility_score,
                event.event_time,
            )
            return True
        except Exception as e:
            logger.error(f"Error saving transfer event: {e}")
            return False

    async def _generate_transfer_alerts(self):
        """Generate alerts for significant transfer activity"""
        # Find tokens with unusual transfer activity
        query = """
            SELECT
                ft.id as token_id,
                ft.symbol,
                ft.team,
                COUNT(*) as event_count,
                SUM(te.engagement) as total_engagement,
                AVG(te.sentiment_score) as avg_sentiment,
                MAX(te.credibility_score) as max_credibility,
                STRING_AGG(DISTINCT te.player_name, ', ') as players
            FROM transfer_events te
            JOIN fan_tokens ft ON te.token_id = ft.id
            WHERE te.event_time > NOW() - INTERVAL '24 hours'
            GROUP BY ft.id, ft.symbol, ft.team
            HAVING COUNT(*) >= 3 OR MAX(te.credibility_score) >= 0.8
            ORDER BY total_engagement DESC
        """

        rows = await Database.fetch(query)

        for row in rows:
            # Determine alert severity
            if row["max_credibility"] >= 0.9 or row["event_count"] >= 10:
                severity = "critical"
            elif row["max_credibility"] >= 0.7 or row["event_count"] >= 5:
                severity = "high"
            elif row["event_count"] >= 3:
                severity = "medium"
            else:
                severity = "low"

            # Check if similar alert already exists
            existing = await Database.fetchval("""
                SELECT id FROM transfer_alerts
                WHERE token_id = $1 AND is_active = true
                AND created_at > NOW() - INTERVAL '6 hours'
            """, row["token_id"])

            if existing:
                # Update existing alert
                await Database.execute("""
                    UPDATE transfer_alerts
                    SET event_count = $1, total_engagement = $2,
                        avg_sentiment = $3, severity = $4, updated_at = NOW()
                    WHERE id = $5
                """, row["event_count"], row["total_engagement"],
                    row["avg_sentiment"], severity, existing)
            else:
                # Create new alert
                players = row["players"] or "Unknown players"
                headline = f"Transfer activity spike for {row['symbol']}"
                description = f"{row['event_count']} transfer mentions in 24h. Players: {players}"

                await Database.execute("""
                    INSERT INTO transfer_alerts (
                        token_id, alert_type, severity, headline, description,
                        event_count, total_engagement, avg_sentiment, expires_at
                    ) VALUES ($1, 'rumor_spike', $2, $3, $4, $5, $6, $7, NOW() + INTERVAL '48 hours')
                """, row["token_id"], severity, headline, description,
                    row["event_count"], row["total_engagement"], row["avg_sentiment"])

    async def get_transfer_summary(self) -> Dict[str, Any]:
        """Get summary of transfer activity for dashboard"""
        # Recent events
        events_query = """
            SELECT
                te.id, te.event_type, te.player_name, te.from_team, te.to_team,
                te.headline, te.source_author, te.engagement, te.sentiment_score,
                te.credibility_score, te.event_time,
                ft.symbol, ft.team
            FROM transfer_events te
            LEFT JOIN fan_tokens ft ON te.token_id = ft.id
            WHERE te.event_time > NOW() - INTERVAL '48 hours'
            ORDER BY te.event_time DESC
            LIMIT 50
        """
        events = await Database.fetch(events_query)

        # Active alerts
        alerts_query = """
            SELECT
                ta.*, ft.symbol, ft.team
            FROM transfer_alerts ta
            LEFT JOIN fan_tokens ft ON ta.token_id = ft.id
            WHERE ta.is_active = true
            ORDER BY
                CASE ta.severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                ta.created_at DESC
        """
        alerts = await Database.fetch(alerts_query)

        # Token activity summary
        token_summary_query = """
            SELECT
                ft.symbol,
                ft.team,
                COUNT(*) as event_count,
                SUM(te.engagement) as total_engagement,
                AVG(te.sentiment_score) as avg_sentiment,
                STRING_AGG(DISTINCT te.player_name, ', ') FILTER (WHERE te.player_name IS NOT NULL) as players
            FROM transfer_events te
            JOIN fan_tokens ft ON te.token_id = ft.id
            WHERE te.event_time > NOW() - INTERVAL '24 hours'
            GROUP BY ft.symbol, ft.team
            ORDER BY event_count DESC
            LIMIT 10
        """
        token_summary = await Database.fetch(token_summary_query)

        # Correlate with social spikes
        correlation_query = """
            SELECT
                ft.symbol,
                COUNT(DISTINCT te.id) as transfer_events,
                COUNT(DISTINCT ss.id) as social_signals,
                AVG(ss.sentiment_score) as social_sentiment
            FROM fan_tokens ft
            LEFT JOIN transfer_events te ON ft.id = te.token_id
                AND te.event_time > NOW() - INTERVAL '24 hours'
            LEFT JOIN social_signals ss ON ft.id = ss.token_id
                AND ss.time > NOW() - INTERVAL '24 hours'
            WHERE ft.is_active = true
            GROUP BY ft.symbol
            HAVING COUNT(DISTINCT te.id) > 0
            ORDER BY transfer_events DESC
        """
        correlations = await Database.fetch(correlation_query)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "events": [dict(e) for e in events],
            "alerts": [dict(a) for a in alerts],
            "token_activity": [dict(t) for t in token_summary],
            "social_correlation": [dict(c) for c in correlations],
            "stats": {
                "total_events_24h": sum(t["event_count"] for t in token_summary) if token_summary else 0,
                "active_alerts": len(alerts),
                "tokens_with_activity": len(token_summary),
            }
        }

    async def get_token_transfers(self, symbol: str) -> Dict[str, Any]:
        """Get transfer activity for a specific token"""
        token = await Database.fetchrow(
            "SELECT id, symbol, team FROM fan_tokens WHERE UPPER(symbol) = UPPER($1)",
            symbol
        )
        if not token:
            return {"error": f"Token {symbol} not found"}

        events = await Database.fetch("""
            SELECT * FROM transfer_events
            WHERE token_id = $1
            ORDER BY event_time DESC
            LIMIT 30
        """, token["id"])

        alerts = await Database.fetch("""
            SELECT * FROM transfer_alerts
            WHERE token_id = $1 AND is_active = true
            ORDER BY created_at DESC
        """, token["id"])

        return {
            "symbol": token["symbol"],
            "team": token["team"],
            "events": [dict(e) for e in events],
            "alerts": [dict(a) for a in alerts],
            "stats": {
                "total_events": len(events),
                "active_alerts": len(alerts),
            }
        }


async def collect_transfers_once() -> int:
    """One-time transfer collection"""
    tracker = TransferTracker()
    return await tracker.collect_transfer_signals()
