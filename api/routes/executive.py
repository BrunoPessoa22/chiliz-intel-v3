"""
Executive API Routes - C-Level focused endpoints
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from services.database import Database

router = APIRouter()


class PortfolioOverview(BaseModel):
    """Executive portfolio overview"""
    total_market_cap: float
    total_volume_24h: float
    avg_health_score: float
    tokens_count: int
    tokens_grade_a: int
    tokens_grade_b: int
    tokens_grade_c: int
    tokens_grade_d: int
    tokens_grade_f: int
    top_performer: Optional[str]
    top_performer_change: Optional[float]
    worst_performer: Optional[str]
    worst_performer_change: Optional[float]
    timestamp: datetime


@router.get("/overview", response_model=PortfolioOverview)
async def get_portfolio_overview():
    """
    Executive Dashboard: Portfolio Overview
    Single-glance view of the entire fan token portfolio
    """
    query = """
        WITH latest_metrics AS (
            SELECT DISTINCT ON (token_id)
                ft.symbol, tma.*
            FROM token_metrics_aggregated tma
            JOIN fan_tokens ft ON tma.token_id = ft.id
            WHERE ft.is_active = true
            ORDER BY token_id, time DESC
        )
        SELECT
            SUM(market_cap) as total_market_cap,
            SUM(total_volume_24h) as total_volume_24h,
            AVG(health_score) as avg_health_score,
            COUNT(*) as tokens_count,
            COUNT(*) FILTER (WHERE health_grade = 'A') as grade_a,
            COUNT(*) FILTER (WHERE health_grade = 'B') as grade_b,
            COUNT(*) FILTER (WHERE health_grade = 'C') as grade_c,
            COUNT(*) FILTER (WHERE health_grade = 'D') as grade_d,
            COUNT(*) FILTER (WHERE health_grade = 'F') as grade_f,
            (SELECT symbol FROM latest_metrics ORDER BY price_change_24h DESC NULLS LAST LIMIT 1) as top_performer,
            (SELECT price_change_24h FROM latest_metrics ORDER BY price_change_24h DESC NULLS LAST LIMIT 1) as top_change,
            (SELECT symbol FROM latest_metrics ORDER BY price_change_24h ASC NULLS LAST LIMIT 1) as worst_performer,
            (SELECT price_change_24h FROM latest_metrics ORDER BY price_change_24h ASC NULLS LAST LIMIT 1) as worst_change
        FROM latest_metrics
    """

    row = await Database.fetchrow(query)

    return PortfolioOverview(
        total_market_cap=float(row["total_market_cap"] or 0),
        total_volume_24h=float(row["total_volume_24h"] or 0),
        avg_health_score=float(row["avg_health_score"] or 0),
        tokens_count=int(row["tokens_count"] or 0),
        tokens_grade_a=int(row["grade_a"] or 0),
        tokens_grade_b=int(row["grade_b"] or 0),
        tokens_grade_c=int(row["grade_c"] or 0),
        tokens_grade_d=int(row["grade_d"] or 0),
        tokens_grade_f=int(row["grade_f"] or 0),
        top_performer=row["top_performer"],
        top_performer_change=float(row["top_change"]) if row["top_change"] else None,
        worst_performer=row["worst_performer"],
        worst_performer_change=float(row["worst_change"]) if row["worst_change"] else None,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health-matrix")
async def get_health_matrix():
    """
    Executive Dashboard: Health Matrix
    Visual matrix of all tokens with health grades
    """
    query = """
        SELECT DISTINCT ON (token_id)
            ft.symbol, ft.team, ft.league,
            tma.health_score, tma.health_grade,
            tma.price_change_24h, tma.total_volume_24h
        FROM token_metrics_aggregated tma
        JOIN fan_tokens ft ON tma.token_id = ft.id
        WHERE ft.is_active = true
        ORDER BY token_id, time DESC
    """

    rows = await Database.fetch(query)

    # Group by grade
    matrix = {
        "A": [],
        "B": [],
        "C": [],
        "D": [],
        "F": [],
    }

    for row in rows:
        grade = row["health_grade"] or "F"
        matrix[grade].append({
            "symbol": row["symbol"],
            "team": row["team"],
            "league": row["league"],
            "health_score": int(row["health_score"] or 0),
            "price_change_24h": float(row["price_change_24h"] or 0),
            "volume_24h": float(row["total_volume_24h"] or 0),
        })

    return {"matrix": matrix, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/liquidity-report")
async def get_liquidity_report():
    """
    Executive Dashboard: Liquidity Report
    Which tokens can handle large trades?
    """
    query = """
        SELECT DISTINCT ON (ls.token_id)
            ft.symbol, ft.team,
            ls.bid_depth_2pct + ls.ask_depth_2pct as total_depth_2pct,
            ls.slippage_buy_10k, ls.slippage_sell_10k,
            ls.slippage_buy_50k, ls.slippage_sell_50k,
            ls.book_imbalance,
            tma.active_exchanges
        FROM liquidity_snapshots ls
        JOIN fan_tokens ft ON ls.token_id = ft.id
        LEFT JOIN LATERAL (
            SELECT active_exchanges FROM token_metrics_aggregated
            WHERE token_id = ls.token_id ORDER BY time DESC LIMIT 1
        ) tma ON true
        WHERE ft.is_active = true
        ORDER BY ls.token_id, ls.time DESC
    """

    rows = await Database.fetch(query)

    return {
        "report": [
            {
                "symbol": row["symbol"],
                "team": row["team"],
                "total_depth_2pct": float(row["total_depth_2pct"] or 0),
                "slippage": {
                    "buy_10k": float(row["slippage_buy_10k"] or 0),
                    "sell_10k": float(row["slippage_sell_10k"] or 0),
                    "buy_50k": float(row["slippage_buy_50k"] or 0),
                    "sell_50k": float(row["slippage_sell_50k"] or 0),
                },
                "book_imbalance": float(row["book_imbalance"] or 0),
                "active_exchanges": int(row["active_exchanges"] or 0),
                # Trading recommendation
                "max_recommended_trade": _calculate_max_trade(row),
            }
            for row in rows
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _calculate_max_trade(row) -> str:
    """Calculate max recommended trade size based on slippage"""
    slippage_10k = float(row["slippage_buy_10k"] or 100)
    slippage_50k = float(row["slippage_sell_50k"] or 100)

    if slippage_50k < 1:
        return "$100k+"
    elif slippage_10k < 1:
        return "$50k"
    elif slippage_10k < 2:
        return "$10k"
    else:
        return "$1k"


@router.get("/holder-insights")
async def get_holder_insights():
    """
    Executive Dashboard: Holder Insights
    Community growth and distribution analysis
    """
    query = """
        SELECT DISTINCT ON (hs.token_id)
            ft.symbol, ft.team,
            hs.total_holders,
            hs.holder_change_24h,
            hs.holder_change_7d,
            hs.top_10_percentage,
            hs.gini_coefficient,
            hs.wallets_whale,
            hs.wallets_large,
            hs.wallets_medium
        FROM holder_snapshots hs
        JOIN fan_tokens ft ON hs.token_id = ft.id
        WHERE ft.is_active = true
        ORDER BY hs.token_id, hs.time DESC
    """

    rows = await Database.fetch(query)

    return {
        "insights": [
            {
                "symbol": row["symbol"],
                "team": row["team"],
                "total_holders": int(row["total_holders"] or 0),
                "growth": {
                    "24h": int(row["holder_change_24h"] or 0),
                    "7d": int(row["holder_change_7d"] or 0),
                },
                "distribution": {
                    "top_10_pct": float(row["top_10_percentage"] or 0) * 100,
                    "gini": float(row["gini_coefficient"] or 0),
                    "whales": int(row["wallets_whale"] or 0),
                    "large": int(row["wallets_large"] or 0),
                    "medium": int(row["wallets_medium"] or 0),
                },
                "health_indicator": _assess_holder_health(row),
            }
            for row in rows
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _assess_holder_health(row) -> str:
    """Assess holder health based on distribution"""
    gini = float(row["gini_coefficient"] or 1)
    top_10 = float(row["top_10_percentage"] or 1)
    change_7d = int(row["holder_change_7d"] or 0)

    if gini < 0.6 and top_10 < 0.4 and change_7d > 0:
        return "healthy"
    elif gini > 0.8 or top_10 > 0.6:
        return "concentrated"
    elif change_7d < -100:
        return "declining"
    return "neutral"


@router.get("/correlation-summary")
async def get_correlation_summary():
    """
    Executive Dashboard: Correlation Summary
    Key relationships between metrics
    """
    query = """
        SELECT DISTINCT ON (ca.token_id)
            ft.symbol,
            ca.price_volume_corr,
            ca.price_holders_corr,
            ca.price_holders_lag,
            ca.spread_price_corr,
            ca.liquidity_volume_corr,
            ca.market_regime
        FROM correlation_analysis ca
        JOIN fan_tokens ft ON ca.token_id = ft.id
        WHERE ft.is_active = true AND ca.lookback_days = 30
        ORDER BY ca.token_id, ca.analysis_date DESC
    """

    rows = await Database.fetch(query)

    return {
        "summary": [
            {
                "symbol": row["symbol"],
                "correlations": {
                    "price_volume": float(row["price_volume_corr"] or 0),
                    "price_holders": float(row["price_holders_corr"] or 0),
                    "holder_lead_days": int(row["price_holders_lag"] or 0),
                    "spread_price": float(row["spread_price_corr"] or 0),
                    "liquidity_volume": float(row["liquidity_volume_corr"] or 0),
                },
                "market_regime": row["market_regime"] or "unknown",
            }
            for row in rows
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/daily-brief")
async def get_daily_brief():
    """
    Executive Dashboard: Daily Brief
    Key points for management review
    """
    # Get overview
    overview = await get_portfolio_overview()

    # Get active signals
    signals_query = """
        SELECT ft.symbol, s.signal_type, s.title, s.confidence, s.management_priority
        FROM signals s
        JOIN fan_tokens ft ON s.token_id = ft.id
        WHERE s.is_resolved = false AND s.created_at > NOW() - INTERVAL '24 hours'
        ORDER BY s.confidence DESC
        LIMIT 5
    """
    signals = await Database.fetch(signals_query)

    # Get biggest movers
    movers_query = """
        SELECT DISTINCT ON (token_id)
            ft.symbol, tma.price_change_24h, tma.total_volume_24h
        FROM token_metrics_aggregated tma
        JOIN fan_tokens ft ON tma.token_id = ft.id
        WHERE ft.is_active = true
        ORDER BY token_id, time DESC
    """
    movers = await Database.fetch(movers_query)
    sorted_movers = sorted(movers, key=lambda x: abs(float(x["price_change_24h"] or 0)), reverse=True)[:5]

    return {
        "brief": {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "portfolio_summary": {
                "total_market_cap": overview.total_market_cap,
                "total_volume_24h": overview.total_volume_24h,
                "avg_health_score": overview.avg_health_score,
            },
            "key_points": [
                f"Top performer: {overview.top_performer} ({overview.top_performer_change:+.2f}%)" if overview.top_performer else None,
                f"Worst performer: {overview.worst_performer} ({overview.worst_performer_change:+.2f}%)" if overview.worst_performer else None,
                f"Grade A tokens: {overview.tokens_grade_a}",
                f"Tokens needing attention (D/F): {overview.tokens_grade_d + overview.tokens_grade_f}",
            ],
            "active_signals": [
                {
                    "symbol": s["symbol"],
                    "type": s["signal_type"],
                    "title": s["title"],
                    "priority": s["management_priority"],
                }
                for s in signals
            ],
            "biggest_movers": [
                {
                    "symbol": m["symbol"],
                    "change_24h": float(m["price_change_24h"] or 0),
                    "volume_24h": float(m["total_volume_24h"] or 0),
                }
                for m in sorted_movers
            ],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
