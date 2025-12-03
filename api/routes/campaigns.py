"""
Campaign Tracking API Routes
Track marketing campaigns and measure their impact on social noise and price.
PoC Core Feature: Do our marketing campaigns create measurable noise and impact?
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.database import Database

logger = logging.getLogger(__name__)
router = APIRouter()


class CampaignCreate(BaseModel):
    """Create campaign request"""
    name: str
    token_symbol: str
    campaign_type: str  # social_push, partnership, airdrop, match_day, announcement
    start_date: datetime
    end_date: Optional[datetime] = None
    description: Optional[str] = None
    budget_usd: Optional[float] = None
    target_reach: Optional[int] = None


class CampaignResponse(BaseModel):
    """Campaign response"""
    id: int
    name: str
    token_symbol: str
    campaign_type: str
    start_date: datetime
    end_date: Optional[datetime]
    status: str
    metrics: Optional[dict] = None


# =====================================================
# CAMPAIGN CRUD
# =====================================================

@router.post("/", response_model=CampaignResponse)
async def create_campaign(campaign: CampaignCreate):
    """
    Create a new campaign tracking entry.
    This allows measuring social/price impact before and after campaign.
    """
    # Get token ID
    token = await Database.fetchrow(
        "SELECT id FROM fan_tokens WHERE UPPER(symbol) = UPPER($1)",
        campaign.token_symbol
    )
    if not token:
        raise HTTPException(status_code=404, detail=f"Token {campaign.token_symbol} not found")

    # Determine status
    now = datetime.now(timezone.utc)
    if campaign.start_date > now:
        status = "scheduled"
    elif campaign.end_date and campaign.end_date < now:
        status = "completed"
    else:
        status = "active"

    # Insert campaign
    query = """
        INSERT INTO campaigns
        (token_id, name, campaign_type, start_date, end_date, description, budget_usd, target_reach, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id, name, campaign_type, start_date, end_date, status
    """

    try:
        row = await Database.fetchrow(
            query,
            token["id"],
            campaign.name,
            campaign.campaign_type,
            campaign.start_date,
            campaign.end_date,
            campaign.description,
            campaign.budget_usd,
            campaign.target_reach,
            status
        )

        return CampaignResponse(
            id=row["id"],
            name=row["name"],
            token_symbol=campaign.token_symbol,
            campaign_type=row["campaign_type"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            status=row["status"]
        )
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_campaigns(status: Optional[str] = None, token: Optional[str] = None):
    """List all campaigns with optional filtering"""
    conditions = ["1=1"]
    params = []
    param_idx = 1

    if status:
        conditions.append(f"c.status = ${param_idx}")
        params.append(status)
        param_idx += 1

    if token:
        conditions.append(f"UPPER(ft.symbol) = UPPER(${param_idx})")
        params.append(token)
        param_idx += 1

    query = f"""
        SELECT c.*, ft.symbol as token_symbol
        FROM campaigns c
        JOIN fan_tokens ft ON c.token_id = ft.id
        WHERE {' AND '.join(conditions)}
        ORDER BY c.start_date DESC
        LIMIT 50
    """

    rows = await Database.fetch(query, *params)

    return {
        "campaigns": [
            {
                "id": r["id"],
                "name": r["name"],
                "token_symbol": r["token_symbol"],
                "campaign_type": r["campaign_type"],
                "start_date": r["start_date"].isoformat() if r["start_date"] else None,
                "end_date": r["end_date"].isoformat() if r["end_date"] else None,
                "status": r["status"],
                "budget_usd": float(r["budget_usd"]) if r["budget_usd"] else None,
            }
            for r in rows
        ],
        "count": len(rows)
    }


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: int):
    """Get campaign details with basic metrics"""
    query = """
        SELECT c.*, ft.symbol as token_symbol, ft.team
        FROM campaigns c
        JOIN fan_tokens ft ON c.token_id = ft.id
        WHERE c.id = $1
    """
    row = await Database.fetchrow(query, campaign_id)

    if not row:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "id": row["id"],
        "name": row["name"],
        "token_symbol": row["token_symbol"],
        "team": row["team"],
        "campaign_type": row["campaign_type"],
        "start_date": row["start_date"].isoformat() if row["start_date"] else None,
        "end_date": row["end_date"].isoformat() if row["end_date"] else None,
        "status": row["status"],
        "description": row["description"],
        "budget_usd": float(row["budget_usd"]) if row["budget_usd"] else None,
        "target_reach": row["target_reach"],
    }


# =====================================================
# CAMPAIGN IMPACT ANALYSIS (PoC Core Feature)
# =====================================================

@router.get("/{campaign_id}/impact")
async def get_campaign_impact(campaign_id: int):
    """
    Calculate the impact of a campaign on social noise and price.
    Compares metrics before, during, and after the campaign.
    THIS IS THE CORE PoC DELIVERABLE: Campaign Impact Measurement
    """
    # Get campaign details
    campaign = await Database.fetchrow("""
        SELECT c.*, ft.symbol, ft.id as token_id
        FROM campaigns c
        JOIN fan_tokens ft ON c.token_id = ft.id
        WHERE c.id = $1
    """, campaign_id)

    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    token_id = campaign["token_id"]
    start_date = campaign["start_date"]
    end_date = campaign["end_date"] or datetime.now(timezone.utc)

    # Calculate period lengths
    campaign_duration = (end_date - start_date).days or 1
    before_start = start_date - timedelta(days=campaign_duration)
    after_end = end_date + timedelta(days=campaign_duration)

    # Get social metrics for each period
    social_before = await _get_period_social_metrics(token_id, before_start, start_date)
    social_during = await _get_period_social_metrics(token_id, start_date, end_date)
    social_after = await _get_period_social_metrics(token_id, end_date, after_end)

    # Get market metrics for each period
    market_before = await _get_period_market_metrics(token_id, before_start, start_date)
    market_during = await _get_period_market_metrics(token_id, start_date, end_date)
    market_after = await _get_period_market_metrics(token_id, end_date, after_end)

    # Calculate changes
    social_impact = _calculate_impact(social_before, social_during, social_after)
    market_impact = _calculate_impact(market_before, market_during, market_after)

    # Generate assessment
    assessment = _assess_campaign_impact(social_impact, market_impact)

    return {
        "campaign": {
            "id": campaign_id,
            "name": campaign["name"],
            "token": campaign["symbol"],
            "type": campaign["campaign_type"],
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "duration_days": campaign_duration,
        },
        "social_metrics": {
            "before": social_before,
            "during": social_during,
            "after": social_after,
            "impact": social_impact,
        },
        "market_metrics": {
            "before": market_before,
            "during": market_during,
            "after": market_after,
            "impact": market_impact,
        },
        "assessment": assessment,
        "poc_answer": _generate_poc_campaign_answer(social_impact, market_impact, campaign["name"]),
    }


async def _get_period_social_metrics(token_id: int, start: datetime, end: datetime) -> dict:
    """Get aggregated social metrics for a period"""
    query = """
        SELECT
            COALESCE(AVG(tweet_count_24h), 0) as avg_tweets,
            COALESCE(MAX(tweet_count_24h), 0) as max_tweets,
            COALESCE(SUM(engagement_total), 0) as total_engagement,
            COALESCE(AVG(sentiment_score), 0.5) as avg_sentiment,
            COALESCE(SUM(influencer_mentions), 0) as influencer_mentions,
            COUNT(*) as data_points
        FROM social_metrics
        WHERE token_id = $1 AND time >= $2 AND time < $3
    """
    row = await Database.fetchrow(query, token_id, start, end)

    if not row or row["data_points"] == 0:
        return {"avg_tweets": 0, "max_tweets": 0, "total_engagement": 0, "avg_sentiment": 0.5, "influencer_mentions": 0, "has_data": False}

    return {
        "avg_tweets": round(float(row["avg_tweets"]), 1),
        "max_tweets": int(row["max_tweets"]),
        "total_engagement": int(row["total_engagement"]),
        "avg_sentiment": round(float(row["avg_sentiment"]), 3),
        "influencer_mentions": int(row["influencer_mentions"]),
        "has_data": True
    }


async def _get_period_market_metrics(token_id: int, start: datetime, end: datetime) -> dict:
    """Get aggregated market metrics for a period"""
    query = """
        SELECT
            COALESCE(AVG(vwap_price), 0) as avg_price,
            COALESCE(AVG(total_volume_24h), 0) as avg_volume,
            COUNT(*) as data_points
        FROM token_metrics_aggregated
        WHERE token_id = $1 AND time >= $2 AND time < $3
    """
    row = await Database.fetchrow(query, token_id, start, end)

    if not row or row["data_points"] == 0:
        return {"avg_price": 0, "avg_volume": 0, "has_data": False}

    # Get price at start and end for return calculation
    start_price = await Database.fetchval("""
        SELECT vwap_price FROM token_metrics_aggregated
        WHERE token_id = $1 AND time >= $2 ORDER BY time ASC LIMIT 1
    """, token_id, start)

    end_price = await Database.fetchval("""
        SELECT vwap_price FROM token_metrics_aggregated
        WHERE token_id = $1 AND time < $2 ORDER BY time DESC LIMIT 1
    """, token_id, end)

    price_return = 0
    if start_price and end_price and start_price > 0:
        price_return = ((end_price - start_price) / start_price) * 100

    return {
        "avg_price": round(float(row["avg_price"]), 4),
        "avg_volume": round(float(row["avg_volume"]), 2),
        "price_return_pct": round(price_return, 2),
        "has_data": True
    }


def _calculate_impact(before: dict, during: dict, after: dict) -> dict:
    """Calculate percentage changes between periods"""
    if not before.get("has_data") or not during.get("has_data"):
        return {"has_data": False}

    def pct_change(old, new):
        if old == 0:
            return 0 if new == 0 else 100
        return round(((new - old) / old) * 100, 1)

    impact = {"has_data": True}

    # Social metrics impact
    if "avg_tweets" in before:
        impact["tweet_change_pct"] = pct_change(before["avg_tweets"], during["avg_tweets"])
        impact["engagement_change_pct"] = pct_change(before["total_engagement"], during["total_engagement"])
        impact["sentiment_change"] = round(during["avg_sentiment"] - before["avg_sentiment"], 3)

    # Market metrics impact
    if "avg_volume" in before:
        impact["volume_change_pct"] = pct_change(before["avg_volume"], during["avg_volume"])
        impact["price_during_campaign"] = during.get("price_return_pct", 0)

    return impact


def _assess_campaign_impact(social_impact: dict, market_impact: dict) -> dict:
    """Generate campaign effectiveness assessment"""
    if not social_impact.get("has_data") or not market_impact.get("has_data"):
        return {
            "rating": "INSUFFICIENT_DATA",
            "social_effectiveness": "Unknown - no data available",
            "market_effectiveness": "Unknown - no data available",
            "recommendation": "Ensure data collection is running during campaign period"
        }

    tweet_change = social_impact.get("tweet_change_pct", 0)
    engagement_change = social_impact.get("engagement_change_pct", 0)
    volume_change = market_impact.get("volume_change_pct", 0)
    price_return = market_impact.get("price_during_campaign", 0)

    # Rating logic
    social_score = (tweet_change + engagement_change) / 2
    market_score = (volume_change + price_return) / 2

    if social_score > 50 and market_score > 10:
        rating = "HIGHLY_EFFECTIVE"
    elif social_score > 20 and market_score > 0:
        rating = "EFFECTIVE"
    elif social_score > 0:
        rating = "PARTIAL_EFFECT"
    else:
        rating = "NO_CLEAR_IMPACT"

    return {
        "rating": rating,
        "social_effectiveness": f"Tweets +{tweet_change:.0f}%, Engagement +{engagement_change:.0f}%",
        "market_effectiveness": f"Volume +{volume_change:.0f}%, Price {price_return:+.1f}%",
        "recommendation": _get_recommendation(rating, tweet_change, price_return)
    }


def _get_recommendation(rating: str, tweet_change: float, price_return: float) -> str:
    """Generate actionable recommendation"""
    if rating == "HIGHLY_EFFECTIVE":
        return "Campaign successful. Consider similar campaigns for other tokens. Document what worked."
    elif rating == "EFFECTIVE":
        return "Campaign showed impact. Analyze which elements drove engagement for optimization."
    elif rating == "PARTIAL_EFFECT":
        if tweet_change > 20 and price_return <= 0:
            return "Social buzz generated but didn't translate to price. Consider timing with market conditions."
        else:
            return "Modest impact detected. Consider increasing campaign intensity or adjusting targeting."
    else:
        return "Campaign had limited measurable impact. Review targeting, timing, and messaging."


def _generate_poc_campaign_answer(social_impact: dict, market_impact: dict, campaign_name: str) -> str:
    """Generate the PoC answer for campaign impact measurement"""
    if not social_impact.get("has_data"):
        return f"Cannot measure impact of '{campaign_name}' - insufficient data. Ensure data collection was active during campaign."

    tweet_change = social_impact.get("tweet_change_pct", 0)
    engagement_change = social_impact.get("engagement_change_pct", 0)
    volume_change = market_impact.get("volume_change_pct", 0)
    price_return = market_impact.get("price_during_campaign", 0)

    if tweet_change > 50:
        social_verdict = f"YES - Campaign generated significant social noise (+{tweet_change:.0f}% tweets)"
    elif tweet_change > 0:
        social_verdict = f"PARTIAL - Campaign increased social activity (+{tweet_change:.0f}% tweets)"
    else:
        social_verdict = "NO - Campaign did not measurably increase social activity"

    if price_return > 5:
        market_verdict = f"with positive market impact (+{price_return:.1f}% price)"
    elif price_return > 0:
        market_verdict = f"with modest market response (+{price_return:.1f}% price)"
    else:
        market_verdict = f"but no positive price movement ({price_return:.1f}%)"

    return f"{social_verdict} {market_verdict}. Volume change: {volume_change:+.0f}%."


# =====================================================
# DATABASE SCHEMA (add to migrations)
# =====================================================

CAMPAIGNS_SCHEMA = """
-- Campaigns table for tracking marketing initiatives
CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    token_id INTEGER REFERENCES fan_tokens(id),
    name VARCHAR(200) NOT NULL,
    campaign_type VARCHAR(50) NOT NULL, -- social_push, partnership, airdrop, match_day, announcement
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    description TEXT,
    budget_usd DECIMAL(12, 2),
    target_reach INTEGER,
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, active, completed, cancelled
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_token ON campaigns(token_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_dates ON campaigns(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
"""
