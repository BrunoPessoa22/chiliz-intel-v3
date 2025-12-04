"""
Campaign Recommendations API Routes
AI-powered campaign recommendations for executives
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from services.recommendations_engine import RecommendationsEngine
from services.slack_notifier import send_recommendation_alert
from services.database import Database

router = APIRouter()

# Cache to track already-notified recommendations
_notified_cache: dict = {}  # {symbol: last_notified_type}


@router.get("")
async def get_recommendations():
    """
    Get all AI-generated campaign recommendations.

    Returns categorized recommendations:
    - campaign_now: Immediate opportunities (act within 24h)
    - campaign_soon: Good opportunities this week
    - amplify: Organic growth to boost
    - avoid: Tokens with negative signals

    Each recommendation includes:
    - headline: One-line summary
    - reasoning: Why this recommendation
    - action: What to do
    - confidence: Data confidence level
    - data: Supporting metrics
    """
    try:
        engine = RecommendationsEngine()
        recommendations = await engine.get_all_recommendations()
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}")
async def get_token_recommendation(symbol: str):
    """
    Get specific recommendation for a token.

    Args:
        symbol: Token symbol (e.g., CHZ, BAR, PSG)

    Returns recommendation with reasoning and action items.
    """
    try:
        engine = RecommendationsEngine()
        recommendation = await engine.get_token_recommendation(symbol.upper())

        if not recommendation:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for token {symbol}"
            )

        return recommendation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/executive")
async def get_executive_summary():
    """
    Get a brief executive summary of current recommendations.
    Perfect for quick briefings or Slack notifications.
    """
    try:
        engine = RecommendationsEngine()
        recommendations = await engine.get_all_recommendations()

        return {
            "summary": recommendations["executive_summary"],
            "stats": recommendations["summary"],
            "top_opportunity": recommendations["campaign_now"][0] if recommendations["campaign_now"] else None,
            "top_risk": recommendations["avoid"][0] if recommendations["avoid"] else None,
            "generated_at": recommendations["generated_at"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify")
async def send_new_recommendations_to_slack():
    """
    Check for new recommendations and send Slack notifications.
    Only sends notifications for NEW recommendations (not previously notified).

    Call this endpoint periodically (e.g., every 15 minutes) to get Slack alerts
    for new campaign opportunities.
    """
    global _notified_cache

    try:
        engine = RecommendationsEngine()
        recommendations = await engine.get_all_recommendations()

        notifications_sent = 0
        new_recommendations = []

        # Check campaign_now recommendations (highest priority - always notify)
        for rec in recommendations.get("campaign_now", []):
            symbol = rec["symbol"]
            rec_type = rec["type"]
            cache_key = f"{symbol}_{rec_type}"

            if cache_key not in _notified_cache:
                success = await send_recommendation_alert(rec)
                if success:
                    _notified_cache[cache_key] = datetime.now(timezone.utc)
                    notifications_sent += 1
                    new_recommendations.append(symbol)

        # Check campaign_soon recommendations (notify for new opportunities)
        for rec in recommendations.get("campaign_soon", []):
            symbol = rec["symbol"]
            rec_type = rec["type"]
            cache_key = f"{symbol}_{rec_type}"

            if cache_key not in _notified_cache:
                success = await send_recommendation_alert(rec)
                if success:
                    _notified_cache[cache_key] = datetime.now(timezone.utc)
                    notifications_sent += 1
                    new_recommendations.append(symbol)

        # Check avoid recommendations (high priority - always notify)
        for rec in recommendations.get("avoid", []):
            symbol = rec["symbol"]
            rec_type = rec["type"]
            cache_key = f"{symbol}_{rec_type}"

            if cache_key not in _notified_cache:
                success = await send_recommendation_alert(rec)
                if success:
                    _notified_cache[cache_key] = datetime.now(timezone.utc)
                    notifications_sent += 1
                    new_recommendations.append(symbol)

        # Clean old cache entries (older than 24 hours)
        now = datetime.now(timezone.utc)
        expired_keys = [
            k for k, v in _notified_cache.items()
            if (now - v).total_seconds() > 86400
        ]
        for key in expired_keys:
            del _notified_cache[key]

        return {
            "status": "success",
            "notifications_sent": notifications_sent,
            "new_recommendations": new_recommendations,
            "cache_size": len(_notified_cache),
            "timestamp": now.isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify/test")
async def test_slack_notification():
    """
    Send a test notification to Slack.
    Use this to verify your Slack webhook is configured correctly.
    """
    try:
        test_recommendation = {
            "symbol": "TEST",
            "team": "Test Token",
            "type": "campaign_now",
            "urgency": "immediate",
            "headline": "This is a test notification from Fan Token Intel",
            "action": "No action required - this is just a test!",
            "reasoning": [
                "Testing Slack webhook integration",
                "Verifying notification formatting",
                "Confirming delivery"
            ],
            "confidence_label": "High",
            "data": {
                "signal_count_24h": 1234,
                "avg_sentiment": 0.75,
                "signal_change_ratio": 2.5,
            }
        }

        success = await send_recommendation_alert(test_recommendation)

        return {
            "status": "success" if success else "failed",
            "message": "Test notification sent" if success else "Failed to send - check webhook URL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
