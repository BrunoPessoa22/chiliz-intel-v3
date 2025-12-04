"""
Transfer Room API Routes
Track transfer news, rumors, and their impact on fan tokens
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

from services.transfer_tracker import TransferTracker, collect_transfers_once

router = APIRouter()


@router.get("")
async def get_transfer_summary():
    """
    Get transfer room summary.

    Returns:
    - events: Recent transfer news/rumors (last 48h)
    - alerts: Active transfer alerts (spike in activity)
    - token_activity: Tokens with most transfer mentions
    - social_correlation: How transfers correlate with social activity
    """
    try:
        tracker = TransferTracker()
        summary = await tracker.get_transfer_summary()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_transfer_alerts():
    """
    Get active transfer alerts.
    Alerts are generated when:
    - Unusual spike in transfer mentions for a token
    - Tier 1 journalist mentions a fan token team
    - High engagement transfer news
    """
    try:
        tracker = TransferTracker()
        summary = await tracker.get_transfer_summary()
        return {
            "alerts": summary["alerts"],
            "count": len(summary["alerts"]),
            "generated_at": summary["generated_at"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/{symbol}")
async def get_token_transfers(symbol: str):
    """
    Get transfer activity for a specific token.

    Args:
        symbol: Token symbol (e.g., BAR, MENGO, JUV)

    Returns transfer events and alerts related to that team.
    """
    try:
        tracker = TransferTracker()
        result = await tracker.get_token_transfers(symbol)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect")
async def trigger_transfer_collection():
    """
    Manually trigger transfer news collection.
    Searches Twitter for transfer-related mentions.
    """
    try:
        count = await collect_transfers_once()
        return {
            "status": "success",
            "events_collected": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/players")
async def get_tracked_players():
    """
    Get list of players being tracked for transfer news.
    """
    from services.transfer_tracker import TRACKED_PLAYERS, TEAM_TOKEN_MAP

    return {
        "tracked_players": TRACKED_PLAYERS,
        "team_token_mapping": TEAM_TOKEN_MAP,
        "total_players": len(TRACKED_PLAYERS),
        "total_teams": len(set(TEAM_TOKEN_MAP.values())),
    }


@router.get("/sources")
async def get_credible_sources():
    """
    Get list of credible transfer sources being tracked.
    """
    from services.database import Database

    sources = await Database.fetch("""
        SELECT source_name, source_type, twitter_handle, credibility_tier, description
        FROM transfer_sources
        WHERE is_active = true
        ORDER BY credibility_tier, source_name
    """)

    return {
        "sources": [dict(s) for s in sources],
        "tiers": {
            1: "Highest credibility (Fabrizio Romano, Ornstein)",
            2: "High credibility (Major outlets)",
            3: "Medium credibility (Aggregators)",
        }
    }
