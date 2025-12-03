"""
Token API Routes - Core token data endpoints
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.database import Database

router = APIRouter()


class TokenMetrics(BaseModel):
    """Token metrics response model"""
    symbol: str
    name: str
    team: str
    price: float
    price_change_1h: Optional[float]
    price_change_24h: Optional[float]
    price_change_7d: Optional[float]
    volume_24h: float
    market_cap: float
    total_holders: Optional[int]
    holder_change_24h: Optional[int]
    liquidity_1pct: float
    spread_bps: Optional[float]
    health_score: Optional[int]
    health_grade: Optional[str]
    active_exchanges: int
    last_updated: datetime


@router.get("/", response_model=List[TokenMetrics])
async def get_all_tokens(
    sort_by: str = Query("volume_24h", description="Sort field"),
    order: str = Query("desc", description="Sort order (asc/desc)")
):
    """Get all fan tokens with latest metrics"""
    query = """
        SELECT
            ft.symbol, ft.name, ft.team,
            tma.vwap_price as price,
            tma.price_change_1h,
            tma.price_change_24h,
            tma.price_change_7d,
            tma.total_volume_24h as volume_24h,
            tma.market_cap,
            tma.total_holders,
            tma.holder_change_24h,
            tma.total_liquidity_1pct as liquidity_1pct,
            tma.avg_spread_bps as spread_bps,
            tma.health_score,
            tma.health_grade,
            tma.active_exchanges,
            tma.time as last_updated
        FROM fan_tokens ft
        LEFT JOIN LATERAL (
            SELECT * FROM token_metrics_aggregated
            WHERE token_id = ft.id
            ORDER BY time DESC LIMIT 1
        ) tma ON true
        WHERE ft.is_active = true
        ORDER BY tma.total_volume_24h DESC NULLS LAST
    """

    rows = await Database.fetch(query)

    return [
        TokenMetrics(
            symbol=row["symbol"],
            name=row["name"],
            team=row["team"],
            price=float(row["price"] or 0),
            price_change_1h=float(row["price_change_1h"]) if row["price_change_1h"] else None,
            price_change_24h=float(row["price_change_24h"]) if row["price_change_24h"] else None,
            price_change_7d=float(row["price_change_7d"]) if row["price_change_7d"] else None,
            volume_24h=float(row["volume_24h"] or 0),
            market_cap=float(row["market_cap"] or 0),
            total_holders=int(row["total_holders"]) if row["total_holders"] else None,
            holder_change_24h=int(row["holder_change_24h"]) if row["holder_change_24h"] else None,
            liquidity_1pct=float(row["liquidity_1pct"] or 0),
            spread_bps=float(row["spread_bps"]) if row["spread_bps"] else None,
            health_score=int(row["health_score"]) if row["health_score"] else None,
            health_grade=row["health_grade"],
            active_exchanges=int(row["active_exchanges"] or 0),
            last_updated=row["last_updated"] or datetime.now(timezone.utc),
        )
        for row in rows
    ]


@router.get("/{symbol}")
async def get_token(symbol: str):
    """Get detailed metrics for a single token"""
    # Get token info
    token_query = """
        SELECT id, symbol, name, team, league, country, coingecko_id,
               total_supply, circulating_supply, launch_date
        FROM fan_tokens WHERE UPPER(symbol) = UPPER($1)
    """
    token = await Database.fetchrow(token_query, symbol)
    if not token:
        raise HTTPException(status_code=404, detail=f"Token {symbol} not found")

    # Get latest aggregated metrics
    metrics_query = """
        SELECT * FROM token_metrics_aggregated
        WHERE token_id = $1
        ORDER BY time DESC LIMIT 1
    """
    metrics = await Database.fetchrow(metrics_query, token["id"])

    # Get latest holder snapshot
    holder_query = """
        SELECT * FROM holder_snapshots
        WHERE token_id = $1
        ORDER BY time DESC LIMIT 1
    """
    holders = await Database.fetchrow(holder_query, token["id"])

    # Get exchange breakdown
    exchange_query = """
        SELECT e.name, e.code, pv.price, pv.volume_24h, st.spread_bps
        FROM price_volume_ticks pv
        JOIN exchanges e ON pv.exchange_id = e.id
        LEFT JOIN spread_ticks st ON pv.token_id = st.token_id
            AND pv.exchange_id = st.exchange_id
            AND pv.time = st.time
        WHERE pv.token_id = $1 AND pv.time > NOW() - INTERVAL '10 minutes'
        ORDER BY pv.volume_24h DESC
    """
    exchanges = await Database.fetch(exchange_query, token["id"])

    # Get correlation data
    corr_query = """
        SELECT * FROM correlation_analysis
        WHERE token_id = $1
        ORDER BY analysis_date DESC LIMIT 1
    """
    correlations = await Database.fetchrow(corr_query, token["id"])

    return {
        "token": dict(token),
        "metrics": dict(metrics) if metrics else None,
        "holders": dict(holders) if holders else None,
        "exchanges": [dict(e) for e in exchanges],
        "correlations": dict(correlations) if correlations else None,
    }


@router.get("/{symbol}/history")
async def get_token_history(
    symbol: str,
    interval: str = Query("1h", description="Time interval (1h, 4h, 1d)"),
    days: int = Query(7, description="Number of days of history")
):
    """Get historical price/volume data for a token"""
    # Get token ID
    token_id = await Database.fetchval(
        "SELECT id FROM fan_tokens WHERE UPPER(symbol) = UPPER($1)", symbol
    )
    if not token_id:
        raise HTTPException(status_code=404, detail=f"Token {symbol} not found")

    # Map interval to bucket
    bucket_map = {
        "1h": "1 hour",
        "4h": "4 hours",
        "1d": "1 day",
    }
    bucket = bucket_map.get(interval, "1 hour")

    query = f"""
        SELECT
            time_bucket('{bucket}', time) as bucket,
            AVG(vwap_price) as price,
            SUM(total_volume_24h) as volume,
            AVG(avg_spread_bps) as spread,
            AVG(total_liquidity_1pct) as liquidity
        FROM token_metrics_aggregated
        WHERE token_id = $1 AND time > NOW() - INTERVAL '1 day' * $2
        GROUP BY bucket
        ORDER BY bucket
    """

    rows = await Database.fetch(query, token_id, days)

    return {
        "symbol": symbol,
        "interval": interval,
        "days": days,
        "data": [
            {
                "time": row["bucket"].isoformat(),
                "price": float(row["price"] or 0),
                "volume": float(row["volume"] or 0),
                "spread": float(row["spread"] or 0),
                "liquidity": float(row["liquidity"] or 0),
            }
            for row in rows
        ]
    }


@router.get("/{symbol}/exchanges")
async def get_token_exchanges(symbol: str):
    """Get per-exchange breakdown for a token"""
    token_id = await Database.fetchval(
        "SELECT id FROM fan_tokens WHERE UPPER(symbol) = UPPER($1)", symbol
    )
    if not token_id:
        raise HTTPException(status_code=404, detail=f"Token {symbol} not found")

    query = """
        SELECT
            e.name as exchange_name,
            e.code as exchange_code,
            pv.price,
            pv.volume_24h,
            st.best_bid,
            st.best_ask,
            st.spread_bps,
            ls.bid_depth_2pct,
            ls.ask_depth_2pct,
            ls.slippage_buy_10k,
            ls.slippage_sell_10k
        FROM exchanges e
        LEFT JOIN LATERAL (
            SELECT * FROM price_volume_ticks
            WHERE token_id = $1 AND exchange_id = e.id
            ORDER BY time DESC LIMIT 1
        ) pv ON true
        LEFT JOIN LATERAL (
            SELECT * FROM spread_ticks
            WHERE token_id = $1 AND exchange_id = e.id
            ORDER BY time DESC LIMIT 1
        ) st ON true
        LEFT JOIN LATERAL (
            SELECT * FROM liquidity_snapshots
            WHERE token_id = $1 AND exchange_id = e.id
            ORDER BY time DESC LIMIT 1
        ) ls ON true
        WHERE pv.price IS NOT NULL
        ORDER BY pv.volume_24h DESC
    """

    rows = await Database.fetch(query, token_id)

    return {
        "symbol": symbol,
        "exchanges": [
            {
                "name": row["exchange_name"],
                "code": row["exchange_code"],
                "price": float(row["price"] or 0),
                "volume_24h": float(row["volume_24h"] or 0),
                "best_bid": float(row["best_bid"] or 0),
                "best_ask": float(row["best_ask"] or 0),
                "spread_bps": float(row["spread_bps"] or 0),
                "depth_2pct": {
                    "bid": float(row["bid_depth_2pct"] or 0),
                    "ask": float(row["ask_depth_2pct"] or 0),
                },
                "slippage_10k": {
                    "buy": float(row["slippage_buy_10k"] or 0),
                    "sell": float(row["slippage_sell_10k"] or 0),
                },
            }
            for row in rows
        ]
    }
