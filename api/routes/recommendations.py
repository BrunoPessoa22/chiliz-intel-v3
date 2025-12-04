"""
Campaign Recommendations API Routes
AI-powered campaign recommendations for executives
"""
from fastapi import APIRouter, HTTPException

from services.recommendations_engine import RecommendationsEngine

router = APIRouter()


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
