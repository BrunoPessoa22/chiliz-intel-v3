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
