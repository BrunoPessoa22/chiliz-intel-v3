"""
Social Signals API Routes
Real-time social media signal tracking from X/Twitter
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from services.social_signal_tracker import (
    get_recent_signals,
    get_signal_stats,
    get_signal_tracker,
    collect_signals_for_token,
)
from services.database import Database

logger = logging.getLogger(__name__)
router = APIRouter()


class SocialSignal(BaseModel):
    """Social signal model"""
    time: str
    token: Optional[str]
    type: str
    source: str
    url: Optional[str]
    title: Optional[str]
    content: str
    sentiment: str
    sentiment_score: float
    engagement: int
    followers: int
    is_influencer: bool
    is_high_priority: bool
    categories: List[str]


@router.get("/")
async def get_signals(
    limit: int = Query(default=50, ge=1, le=200),
    token: Optional[str] = Query(default=None, description="Filter by token symbol"),
    type: Optional[str] = Query(default=None, description="Filter by signal type (tweet, news)"),
    high_priority: bool = Query(default=False, description="Only high priority signals"),
    categories: Optional[str] = Query(default=None, description="Filter by categories (comma-separated)")
):
    """
    Get recent social signals.
    Returns signals from X/Twitter and other sources.
    """
    try:
        # Parse categories if provided
        category_list = None
        if categories:
            category_list = [c.strip() for c in categories.split(',')]

        signals = await get_recent_signals(
            limit=limit,
            token_symbol=token,
            signal_type=type,
            high_priority_only=high_priority,
            categories=category_list
        )

        return {
            "signals": signals,
            "count": len(signals),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching signals: {e}")
        # Return empty if table doesn't exist yet
        return {
            "signals": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Social tracking initializing..."
        }


@router.get("/stats")
async def get_social_stats(
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    Get social signal statistics.
    Shows signal counts, sentiment breakdown, engagement per token.
    """
    try:
        stats = await get_signal_stats(hours=hours)
        return stats

    except Exception as e:
        logger.error(f"Error fetching signal stats: {e}")
        return {
            "period_hours": hours,
            "tokens": [],
            "note": "Social tracking initializing..."
        }


@router.get("/high-priority")
async def get_high_priority_signals(
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    Get high priority signals only.
    These are crypto+sports intersection signals or from major influencers.
    """
    try:
        signals = await get_recent_signals(
            limit=limit,
            high_priority_only=True
        )

        return {
            "signals": signals,
            "count": len(signals),
            "description": "Crypto + Sports intersection and influencer signals",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching high priority signals: {e}")
        return {
            "signals": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/by-category/{category}")
async def get_signals_by_category(
    category: str,
    limit: int = Query(default=50, ge=1, le=100)
):
    """
    Get signals filtered by category.
    Categories: crypto, sports, fantoken, general
    """
    valid_categories = ['crypto', 'sports', 'fantoken', 'general']
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Valid options: {valid_categories}"
        )

    try:
        signals = await get_recent_signals(
            limit=limit,
            categories=[category]
        )

        return {
            "category": category,
            "signals": signals,
            "count": len(signals),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching signals by category: {e}")
        return {
            "category": category,
            "signals": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/token/{symbol}")
async def get_token_signals(
    symbol: str,
    limit: int = Query(default=50, ge=1, le=100),
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    Get signals for a specific token with sentiment analysis.
    """
    try:
        signals = await get_recent_signals(
            limit=limit,
            token_symbol=symbol.upper()
        )

        # Calculate sentiment summary
        positive = sum(1 for s in signals if s['sentiment'] == 'positive')
        negative = sum(1 for s in signals if s['sentiment'] == 'negative')
        neutral = sum(1 for s in signals if s['sentiment'] == 'neutral')
        total = len(signals)

        avg_sentiment = sum(s['sentiment_score'] for s in signals) / total if total > 0 else 0.5
        total_engagement = sum(s['engagement'] for s in signals)
        influencer_count = sum(1 for s in signals if s['is_influencer'])

        return {
            "symbol": symbol.upper(),
            "signals": signals,
            "count": total,
            "sentiment_summary": {
                "positive_count": positive,
                "negative_count": negative,
                "neutral_count": neutral,
                "avg_sentiment_score": avg_sentiment,
                "sentiment_label": 'positive' if avg_sentiment > 0.55 else 'negative' if avg_sentiment < 0.45 else 'neutral',
            },
            "engagement_summary": {
                "total_engagement": total_engagement,
                "avg_engagement": total_engagement / total if total > 0 else 0,
                "influencer_count": influencer_count,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching token signals: {e}")
        return {
            "symbol": symbol.upper(),
            "signals": [],
            "count": 0,
            "sentiment_summary": {},
            "engagement_summary": {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/trending")
async def get_trending_signals():
    """
    Get trending tokens based on social activity.
    Returns tokens ranked by signal count and engagement.
    """
    try:
        query = """
            SELECT
                ft.symbol,
                COUNT(*) as signal_count,
                SUM(ss.engagement) as total_engagement,
                AVG(ss.sentiment_score) as avg_sentiment,
                SUM(CASE WHEN ss.is_high_priority THEN 1 ELSE 0 END) as high_priority_count
            FROM social_signals ss
            JOIN fan_tokens ft ON ss.token_id = ft.id
            WHERE ss.time > NOW() - INTERVAL '6 hours'
            GROUP BY ft.symbol
            HAVING COUNT(*) >= 3
            ORDER BY signal_count DESC, total_engagement DESC
            LIMIT 10
        """

        rows = await Database.fetch(query)

        trending = [
            {
                'symbol': row['symbol'],
                'signal_count': row['signal_count'],
                'total_engagement': row['total_engagement'],
                'avg_sentiment': float(row['avg_sentiment']) if row['avg_sentiment'] else 0.5,
                'high_priority_signals': row['high_priority_count'],
                'trend_score': row['signal_count'] * 10 + row['total_engagement'] * 0.01,
            }
            for row in rows
        ]

        return {
            "period": "6h",
            "trending": trending,
            "count": len(trending),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching trending signals: {e}")
        return {
            "period": "6h",
            "trending": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/live")
async def get_live_signals():
    """
    Get live signals from in-memory cache.
    For real-time display without database query.
    """
    try:
        tracker = await get_signal_tracker()
        signals = tracker.recent_signals[:50]

        # Format for frontend
        formatted = []
        for s in signals:
            formatted.append({
                'time': s['time'].isoformat() if hasattr(s['time'], 'isoformat') else s['time'],
                'token': s.get('token_symbol'),
                'type': s.get('signal_type', 'tweet'),
                'source': s.get('source', 'Unknown'),
                'title': s.get('title'),
                'content': s.get('content', '')[:280],  # Truncate for display
                'sentiment': s.get('sentiment', 'neutral'),
                'engagement': s.get('engagement', 0),
                'is_influencer': s.get('is_influencer', False),
                'is_high_priority': s.get('is_high_priority', False),
                'categories': s.get('categories', []),
            })

        return {
            "signals": formatted,
            "count": len(formatted),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching live signals: {e}")
        return {
            "signals": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/summary")
async def get_signal_summary():
    """
    Get overall social signal summary.
    Dashboard-friendly overview of social activity.
    """
    try:
        # Get 24h stats
        query = """
            SELECT
                COUNT(*) as total_signals,
                SUM(engagement) as total_engagement,
                AVG(sentiment_score) as avg_sentiment,
                SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive_count,
                SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative_count,
                SUM(CASE WHEN is_high_priority THEN 1 ELSE 0 END) as high_priority_count,
                SUM(CASE WHEN is_influencer THEN 1 ELSE 0 END) as influencer_mentions,
                COUNT(DISTINCT token_id) as tokens_mentioned
            FROM social_signals
            WHERE time > NOW() - INTERVAL '24 hours'
        """

        stats = await Database.fetchrow(query)

        # Get most active token
        top_token_query = """
            SELECT ft.symbol, COUNT(*) as count
            FROM social_signals ss
            JOIN fan_tokens ft ON ss.token_id = ft.id
            WHERE ss.time > NOW() - INTERVAL '24 hours'
            GROUP BY ft.symbol
            ORDER BY count DESC
            LIMIT 1
        """

        top_token = await Database.fetchrow(top_token_query)

        return {
            "period": "24h",
            "total_signals": stats['total_signals'] or 0 if stats else 0,
            "total_engagement": stats['total_engagement'] or 0 if stats else 0,
            "avg_sentiment": float(stats['avg_sentiment']) if stats and stats['avg_sentiment'] else 0.5,
            "sentiment_breakdown": {
                "positive": stats['positive_count'] or 0 if stats else 0,
                "negative": stats['negative_count'] or 0 if stats else 0,
                "neutral": (stats['total_signals'] or 0) - (stats['positive_count'] or 0) - (stats['negative_count'] or 0) if stats else 0,
            },
            "high_priority_signals": stats['high_priority_count'] or 0 if stats else 0,
            "influencer_mentions": stats['influencer_mentions'] or 0 if stats else 0,
            "tokens_mentioned": stats['tokens_mentioned'] or 0 if stats else 0,
            "most_active_token": top_token['symbol'] if top_token else None,
            "most_active_count": top_token['count'] if top_token else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching signal summary: {e}")
        return {
            "period": "24h",
            "total_signals": 0,
            "total_engagement": 0,
            "avg_sentiment": 0.5,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/wordcloud/{symbol}")
async def get_token_wordcloud(
    symbol: str,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=10, le=500, description="Max words to return"),
    token_only: bool = Query(default=True, description="Only fan token related tweets (filters out general team chatter)")
):
    """
    Get word frequency data for word cloud visualization.
    Returns most mentioned words in tweets about this token.
    Updates in real-time as new tweets come in.

    token_only=True (default): Only tweets mentioning token/crypto terms
    token_only=False: All tweets including general team discussion
    """
    import re
    from collections import Counter

    # Words that indicate fan token context (not just team talk)
    TOKEN_CONTEXT_WORDS = {
        'token', 'tokens', 'fan token', 'fantoken', '$', 'chiliz', 'chz', 'socios',
        'buy', 'sell', 'hold', 'hodl', 'pump', 'dump', 'moon', 'price', 'trading',
        'exchange', 'binance', 'mexc', 'crypto', 'blockchain', 'web3', 'nft',
        'reward', 'rewards', 'voting', 'vote', 'poll', 'airdrop', 'stake', 'staking',
        'wallet', 'dex', 'cex', 'liquidity', 'volume', 'market', 'bullish', 'bearish',
    }

    # Stop words to filter out (common words, URLs, mentions, etc.)
    STOP_WORDS = {
        # English common
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
        'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'must', 'shall', 'can', 'need', 'dare', 'ought', 'used', 'it', 'its', 'this',
        'that', 'these', 'those', 'i', 'you', 'he', 'she', 'we', 'they', 'what', 'which',
        'who', 'whom', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
        'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here',
        'there', 'then', 'once', 'if', 'as', 'into', 'about', 'out', 'up', 'down',
        'over', 'under', 'again', 'further', 'any', 'our', 'your', 'his', 'her', 'their',
        'my', 'me', 'him', 'us', 'them', 'am', 'get', 'got', 'go', 'going', 'goes',
        # Social media specific
        'rt', 'via', 'https', 'http', 'co', 'amp', 't', 's', 're', 've', 'll', 'd',
        # Crypto common (filter noise)
        'token', 'tokens', 'fan', 'price', 'crypto', 'buy', 'sell', 'trading',
        # Portuguese common
        'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'um', 'uma',
        'para', 'com', 'por', 'que', 'se', 'mais', 'muito', 'como', 'seu', 'sua',
        # Spanish common
        'el', 'la', 'los', 'las', 'un', 'una', 'es', 'en', 'del', 'al', 'con', 'por',
        'para', 'que', 'se', 'su', 'sus', 'mas', 'pero', 'como', 'este', 'esta',
        # Numbers and single chars
        '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '100',
    }

    try:
        # Fetch tweet content for this token
        query = """
            SELECT content, engagement
            FROM social_signals
            WHERE token_id = (SELECT id FROM fan_tokens WHERE UPPER(symbol) = UPPER($1))
            AND time > NOW() - INTERVAL '%s hours'
            AND content IS NOT NULL
            ORDER BY time DESC
        """ % hours

        rows = await Database.fetch(query, symbol)

        if not rows:
            return {
                "symbol": symbol.upper(),
                "words": [],
                "total_tweets": 0,
                "period_hours": hours,
                "token_only": token_only,
                "message": "No tweets found for this token in the specified period",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Filter to token-related tweets if requested
        if token_only:
            filtered_rows = []
            for row in rows:
                content_lower = (row['content'] or '').lower()
                # Check if tweet contains any token context words
                has_token_context = any(word in content_lower for word in TOKEN_CONTEXT_WORDS)
                # Also check for $ symbol followed by token symbol (e.g., $MENGO, $BAR)
                has_dollar_symbol = f'${symbol.lower()}' in content_lower
                if has_token_context or has_dollar_symbol:
                    filtered_rows.append(row)
            rows = filtered_rows

        if not rows:
            return {
                "symbol": symbol.upper(),
                "words": [],
                "total_tweets": 0,
                "period_hours": hours,
                "token_only": token_only,
                "message": f"No fan token specific tweets found. Try token_only=false to include general team discussion.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Process all tweet content
        word_counts = Counter()
        total_tweets = len(rows)

        for row in rows:
            content = row['content'] or ''
            engagement = row['engagement'] or 1

            # Clean text
            text = content.lower()
            # Remove URLs
            text = re.sub(r'https?://\S+', '', text)
            # Remove mentions (@user)
            text = re.sub(r'@\w+', '', text)
            # Remove hashtag symbols but keep the word
            text = re.sub(r'#(\w+)', r'\1', text)
            # Remove special characters, keep letters and spaces
            text = re.sub(r'[^a-zA-Z\s]', ' ', text)
            # Split into words
            words = text.split()

            # Count words (weight by engagement)
            weight = 1 + (engagement * 0.1)  # Higher engagement = slightly more weight
            for word in words:
                word = word.strip()
                if len(word) >= 3 and word not in STOP_WORDS:
                    word_counts[word] += weight

        # Get top words
        top_words = word_counts.most_common(limit)

        # Format for word cloud (normalize sizes)
        max_count = top_words[0][1] if top_words else 1
        words = [
            {
                "text": word,
                "value": round(count, 1),
                "size": round((count / max_count) * 100, 1),  # Normalized 0-100
            }
            for word, count in top_words
        ]

        return {
            "symbol": symbol.upper(),
            "words": words,
            "total_tweets": total_tweets,
            "unique_words": len(word_counts),
            "period_hours": hours,
            "token_only": token_only,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating word cloud for {symbol}: {e}")
        return {
            "symbol": symbol.upper(),
            "words": [],
            "total_tweets": 0,
            "period_hours": hours,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/wordcloud")
async def get_all_wordcloud(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=10, le=500)
):
    """
    Get word cloud data for ALL tokens combined.
    Shows overall narrative across the fan token ecosystem.
    """
    import re
    from collections import Counter

    STOP_WORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
        'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'must', 'shall', 'can', 'need', 'it', 'its', 'this', 'that', 'these', 'those',
        'i', 'you', 'he', 'she', 'we', 'they', 'what', 'which', 'who', 'when', 'where',
        'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
        'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 'just', 'also', 'now', 'rt', 'via', 'https', 'http', 'co', 'amp', 't',
        's', 're', 've', 'll', 'd', 'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na',
        'um', 'uma', 'para', 'com', 'por', 'que', 'se', 'el', 'la', 'los', 'las', 'un',
        'una', 'es', 'en', 'del', 'al', 'con', 'token', 'tokens', 'fan', 'price', 'crypto',
    }

    try:
        query = """
            SELECT ss.content, ss.engagement, ft.symbol
            FROM social_signals ss
            JOIN fan_tokens ft ON ss.token_id = ft.id
            WHERE ss.time > NOW() - INTERVAL '%s hours'
            AND ss.content IS NOT NULL
            ORDER BY ss.time DESC
        """ % hours

        rows = await Database.fetch(query)

        word_counts = Counter()
        token_mentions = Counter()

        for row in rows:
            content = row['content'] or ''
            engagement = row['engagement'] or 1
            token_mentions[row['symbol']] += 1

            text = content.lower()
            text = re.sub(r'https?://\S+', '', text)
            text = re.sub(r'@\w+', '', text)
            text = re.sub(r'#(\w+)', r'\1', text)
            text = re.sub(r'[^a-zA-Z\s]', ' ', text)
            words = text.split()

            weight = 1 + (engagement * 0.1)
            for word in words:
                word = word.strip()
                if len(word) >= 3 and word not in STOP_WORDS:
                    word_counts[word] += weight

        top_words = word_counts.most_common(limit)
        max_count = top_words[0][1] if top_words else 1

        words = [
            {"text": word, "value": round(count, 1), "size": round((count / max_count) * 100, 1)}
            for word, count in top_words
        ]

        return {
            "symbol": "ALL",
            "words": words,
            "total_tweets": len(rows),
            "unique_words": len(word_counts),
            "tokens_in_data": dict(token_mentions.most_common(10)),
            "period_hours": hours,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating global word cloud: {e}")
        return {
            "symbol": "ALL",
            "words": [],
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/collect/{symbol}")
async def collect_token_signals(symbol: str):
    """
    Manually trigger signal collection for a specific token.
    Use this when you need immediate collection outside the rotation schedule.
    """
    try:
        count = await collect_signals_for_token(symbol.upper())

        return {
            "status": "success",
            "symbol": symbol.upper(),
            "signals_collected": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error collecting signals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
