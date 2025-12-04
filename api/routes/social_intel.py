"""
Social Intelligence API Routes
Combined social data from X, LunarCrush, and Reddit
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from services.lunarcrush_tracker import (
    get_lunarcrush_summary,
    collect_lunarcrush_metrics,
    LunarCrushTracker,
)
from services.reddit_tracker import (
    get_reddit_summary,
    collect_reddit_signals,
)
from services.database import Database

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/overview")
async def get_social_overview(
    symbol: Optional[str] = Query(default=None, description="Filter by token symbol")
):
    """
    Get combined social intelligence overview.
    Aggregates data from X, LunarCrush, and Reddit.
    """
    try:
        if symbol:
            # Single token overview
            return await get_token_social_overview(symbol.upper())

        # All tokens overview
        query = """
            SELECT * FROM social_metrics_combined
            ORDER BY combined_sentiment_score DESC
            LIMIT 20
        """

        rows = await Database.fetch(query)

        return {
            "overview": [dict(row) for row in rows] if rows else [],
            "count": len(rows) if rows else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching social overview: {e}")
        return {
            "overview": [],
            "count": 0,
            "error": "Social metrics view may not exist yet",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def get_token_social_overview(symbol: str) -> dict:
    """Get detailed social overview for a single token."""
    try:
        # Get LunarCrush data
        lc_data = await get_lunarcrush_summary(symbol)

        # Get Reddit data
        reddit_data = await get_reddit_summary(symbol, hours=24)

        # Get X data from database
        x_query = """
            SELECT
                COUNT(*) as signal_count,
                AVG(sentiment_score) as avg_sentiment,
                SUM(engagement) as total_engagement,
                SUM(CASE WHEN is_influencer THEN 1 ELSE 0 END) as influencer_count
            FROM social_signals ss
            JOIN fan_tokens ft ON ss.token_id = ft.id
            WHERE ft.symbol = $1
            AND ss.time > NOW() - INTERVAL '24 hours'
        """
        x_row = await Database.fetchrow(x_query, symbol)

        return {
            "symbol": symbol,
            "lunarcrush": {
                "galaxy_score": lc_data.get("galaxy_score") if lc_data else None,
                "alt_rank": lc_data.get("alt_rank") if lc_data else None,
                "sentiment": lc_data.get("sentiment") if lc_data else None,
                "social_volume_24h": lc_data.get("social_volume_24h") if lc_data else None,
                "available": lc_data is not None,
            },
            "twitter": {
                "signal_count_24h": x_row["signal_count"] if x_row else 0,
                "avg_sentiment": float(x_row["avg_sentiment"]) if x_row and x_row["avg_sentiment"] else 0.5,
                "total_engagement": x_row["total_engagement"] if x_row else 0,
                "influencer_count": x_row["influencer_count"] if x_row else 0,
            },
            "reddit": reddit_data,
            "combined_score": calculate_combined_score(lc_data, x_row, reddit_data),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching token social overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def calculate_combined_score(lc_data: dict, x_row, reddit_data: dict) -> float:
    """Calculate weighted combined sentiment score."""
    scores = []
    weights = []

    # LunarCrush (40% weight if available)
    if lc_data and lc_data.get("sentiment"):
        scores.append(lc_data["sentiment"] * 100)
        weights.append(0.4)

    # X/Twitter (35% weight)
    if x_row and x_row.get("avg_sentiment"):
        scores.append(float(x_row["avg_sentiment"]) * 100)
        weights.append(0.35)
    else:
        scores.append(50)
        weights.append(0.35)

    # Reddit (25% weight)
    if reddit_data and reddit_data.get("avg_sentiment"):
        scores.append(reddit_data["avg_sentiment"] * 100)
        weights.append(0.25)
    else:
        scores.append(50)
        weights.append(0.25)

    # Normalize weights
    total_weight = sum(weights)
    if total_weight > 0:
        return round(sum(s * w for s, w in zip(scores, weights)) / total_weight, 1)
    return 50.0


@router.get("/lunarcrush/{symbol}")
async def get_lunarcrush_data(symbol: str):
    """
    Get LunarCrush social metrics for a specific token.
    Returns Galaxy Score, sentiment, social volume, and more.
    """
    try:
        data = await get_lunarcrush_summary(symbol.upper())

        if not data:
            return {
                "symbol": symbol.upper(),
                "available": False,
                "message": "Token not tracked on LunarCrush",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "symbol": symbol.upper(),
            "available": True,
            "data": {
                "galaxy_score": data.get("galaxy_score"),
                "alt_rank": data.get("alt_rank"),
                "sentiment": data.get("sentiment"),
                "social_volume": data.get("social_volume"),
                "social_volume_24h": data.get("social_volume_24h"),
                "social_dominance": data.get("social_dominance"),
                "price": data.get("price"),
                "price_change_24h": data.get("percent_change_24h"),
                "market_cap": data.get("market_cap"),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching LunarCrush data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lunarcrush/history/{symbol}")
async def get_lunarcrush_history(
    symbol: str,
    days: int = Query(default=7, ge=1, le=30)
):
    """
    Get historical LunarCrush metrics for a token.
    """
    try:
        query = """
            SELECT
                time,
                galaxy_score,
                alt_rank,
                sentiment,
                social_volume_24h,
                price,
                price_change_24h
            FROM lunarcrush_metrics lm
            JOIN fan_tokens ft ON lm.token_id = ft.id
            WHERE ft.symbol = $1
            AND lm.time > NOW() - make_interval(days => $2)
            ORDER BY time DESC
        """

        rows = await Database.fetch(query, symbol.upper(), days)

        return {
            "symbol": symbol.upper(),
            "period_days": days,
            "data": [
                {
                    "time": row["time"].isoformat(),
                    "galaxy_score": float(row["galaxy_score"]) if row["galaxy_score"] else None,
                    "alt_rank": row["alt_rank"],
                    "sentiment": float(row["sentiment"]) if row["sentiment"] else None,
                    "social_volume_24h": row["social_volume_24h"],
                    "price": float(row["price"]) if row["price"] else None,
                    "price_change_24h": float(row["price_change_24h"]) if row["price_change_24h"] else None,
                }
                for row in rows
            ] if rows else [],
            "count": len(rows) if rows else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching LunarCrush history: {e}")
        return {
            "symbol": symbol.upper(),
            "period_days": days,
            "data": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/reddit/{symbol}")
async def get_reddit_data(
    symbol: str,
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    Get Reddit activity summary for a specific token.
    """
    try:
        summary = await get_reddit_summary(symbol.upper(), hours)
        return summary

    except Exception as e:
        logger.error(f"Error fetching Reddit data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reddit/posts/{symbol}")
async def get_reddit_posts(
    symbol: str,
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    Get recent Reddit posts mentioning a specific token.
    """
    try:
        query = """
            SELECT
                rs.time,
                rs.subreddit,
                rs.title,
                rs.url,
                rs.author,
                rs.score,
                rs.num_comments,
                rs.sentiment,
                rs.sentiment_score,
                rs.is_high_priority,
                rs.is_trending
            FROM reddit_signals rs
            JOIN fan_tokens ft ON rs.token_id = ft.id
            WHERE ft.symbol = $1
            ORDER BY rs.time DESC
            LIMIT $2
        """

        rows = await Database.fetch(query, symbol.upper(), limit)

        return {
            "symbol": symbol.upper(),
            "posts": [
                {
                    "time": row["time"].isoformat(),
                    "subreddit": row["subreddit"],
                    "title": row["title"],
                    "url": row["url"],
                    "author": row["author"],
                    "score": row["score"],
                    "num_comments": row["num_comments"],
                    "sentiment": row["sentiment"],
                    "sentiment_score": float(row["sentiment_score"]) if row["sentiment_score"] else 0.5,
                    "is_high_priority": row["is_high_priority"],
                    "is_trending": row["is_trending"],
                }
                for row in rows
            ] if rows else [],
            "count": len(rows) if rows else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching Reddit posts: {e}")
        return {
            "symbol": symbol.upper(),
            "posts": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/trending")
async def get_trending_tokens():
    """
    Get trending tokens based on combined social metrics.
    Ranks tokens by social activity across all platforms.
    """
    try:
        query = """
            WITH social_activity AS (
                -- X activity
                SELECT
                    token_id,
                    COUNT(*) as x_signals,
                    SUM(engagement) as x_engagement,
                    AVG(sentiment_score) as x_sentiment
                FROM social_signals
                WHERE time > NOW() - INTERVAL '6 hours'
                GROUP BY token_id
            ),
            reddit_activity AS (
                -- Reddit activity
                SELECT
                    token_id,
                    COUNT(*) as reddit_posts,
                    SUM(score) as reddit_score,
                    AVG(sentiment_score) as reddit_sentiment
                FROM reddit_signals
                WHERE time > NOW() - INTERVAL '6 hours'
                GROUP BY token_id
            ),
            lunarcrush_latest AS (
                -- Latest LunarCrush
                SELECT DISTINCT ON (token_id)
                    token_id,
                    galaxy_score,
                    social_volume_24h
                FROM lunarcrush_metrics
                ORDER BY token_id, time DESC
            )
            SELECT
                ft.symbol,
                ft.team,
                COALESCE(sa.x_signals, 0) as x_signals,
                COALESCE(sa.x_engagement, 0) as x_engagement,
                COALESCE(ra.reddit_posts, 0) as reddit_posts,
                COALESCE(ra.reddit_score, 0) as reddit_score,
                lc.galaxy_score,
                lc.social_volume_24h,
                -- Trend score = weighted combination
                (
                    COALESCE(sa.x_signals, 0) * 10 +
                    COALESCE(sa.x_engagement, 0) * 0.01 +
                    COALESCE(ra.reddit_posts, 0) * 20 +
                    COALESCE(ra.reddit_score, 0) * 0.5 +
                    COALESCE(lc.galaxy_score, 50) * 2
                ) as trend_score
            FROM fan_tokens ft
            LEFT JOIN social_activity sa ON ft.id = sa.token_id
            LEFT JOIN reddit_activity ra ON ft.id = ra.token_id
            LEFT JOIN lunarcrush_latest lc ON ft.id = lc.token_id
            WHERE ft.is_active = TRUE
            AND (
                COALESCE(sa.x_signals, 0) > 0
                OR COALESCE(ra.reddit_posts, 0) > 0
                OR lc.galaxy_score IS NOT NULL
            )
            ORDER BY trend_score DESC
            LIMIT 15
        """

        rows = await Database.fetch(query)

        return {
            "period": "6h",
            "trending": [
                {
                    "symbol": row["symbol"],
                    "team": row["team"],
                    "x_signals": row["x_signals"],
                    "x_engagement": row["x_engagement"],
                    "reddit_posts": row["reddit_posts"],
                    "reddit_score": row["reddit_score"],
                    "galaxy_score": float(row["galaxy_score"]) if row["galaxy_score"] else None,
                    "social_volume_24h": row["social_volume_24h"],
                    "trend_score": float(row["trend_score"]) if row["trend_score"] else 0,
                }
                for row in rows
            ] if rows else [],
            "count": len(rows) if rows else 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching trending tokens: {e}")
        return {
            "period": "6h",
            "trending": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/collect/lunarcrush")
async def trigger_lunarcrush_collection():
    """
    Manually trigger LunarCrush data collection.
    """
    try:
        count = await collect_lunarcrush_metrics()
        return {
            "status": "success",
            "source": "lunarcrush",
            "tokens_collected": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in LunarCrush collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect/reddit")
async def trigger_reddit_collection():
    """
    Manually trigger Reddit signal collection.
    """
    try:
        count = await collect_reddit_signals()
        return {
            "status": "success",
            "source": "reddit",
            "signals_collected": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in Reddit collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/status")
async def get_sources_status():
    """
    Get status of all social data sources.
    """
    from config.settings import x_api_config, lunarcrush_config, reddit_config

    return {
        "sources": {
            "twitter": {
                "configured": bool(x_api_config.bearer_token),
                "tier": "Basic",
                "capabilities": ["Recent search", "User lookup"],
            },
            "lunarcrush": {
                "configured": bool(lunarcrush_config.api_key),
                "tier": "Free" if not lunarcrush_config.api_key else "Pro",
                "capabilities": ["Galaxy Score", "Sentiment", "Social volume", "Time series"],
            },
            "reddit": {
                "configured": bool(reddit_config.client_id),
                "tier": "Free",
                "capabilities": ["Subreddit search", "New posts", "Hot posts"],
            },
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
