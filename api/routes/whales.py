"""
Whale Tracking API Routes
Real-time CEX and DEX whale transaction monitoring
"""
import logging
from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from services.cex_whale_tracker import (
    get_recent_whale_trades,
    get_whale_flow_summary,
    get_cex_tracker,
    WHALE_THRESHOLD_USD,
)
from services.dex_whale_tracker import (
    get_recent_dex_swaps,
    get_dex_volume_summary,
    get_dex_tracker,
)
from services.database import Database

logger = logging.getLogger(__name__)
router = APIRouter()


class WhaleTransaction(BaseModel):
    """Whale transaction model"""
    time: str
    venue: str  # 'cex' or 'dex'
    symbol: str
    exchange: str
    side: str  # 'buy' or 'sell'
    price: float
    quantity: float
    value_usd: float
    is_aggressive: bool = False
    tx_hash: Optional[str] = None


class WhaleFlowSummary(BaseModel):
    """Whale flow summary for a token"""
    symbol: str
    buy_volume: float
    sell_volume: float
    net_flow: float
    buy_count: int
    sell_count: int
    signal: str  # 'bullish', 'bearish', 'neutral'


@router.get("/cex/trades")
async def get_cex_whale_trades(
    limit: int = Query(default=50, ge=1, le=200),
    symbol: Optional[str] = Query(default=None, description="Filter by token symbol"),
    exchange: Optional[str] = Query(default=None, description="Filter by exchange"),
    min_value: float = Query(default=WHALE_THRESHOLD_USD, ge=1000)
):
    """
    Get recent CEX whale trades.
    Returns trades above the threshold from tracked exchanges.
    """
    try:
        trades = await get_recent_whale_trades(
            limit=limit,
            symbol=symbol,
            exchange=exchange,
            min_value=min_value
        )

        return {
            "trades": trades,
            "count": len(trades),
            "threshold_usd": min_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching CEX whale trades: {e}")
        # Return empty if table doesn't exist yet
        return {
            "trades": [],
            "count": 0,
            "threshold_usd": min_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Whale tracking initializing..."
        }


@router.get("/cex/flow")
async def get_cex_whale_flow(
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    Get CEX whale flow summary.
    Shows net buy/sell pressure per token.
    """
    try:
        summary = await get_whale_flow_summary(hours=hours)
        return summary

    except Exception as e:
        logger.error(f"Error fetching whale flow: {e}")
        return {
            "period_hours": hours,
            "tokens": [],
            "totals": {"buy_volume": 0, "sell_volume": 0, "net_flow": 0},
            "note": "Whale tracking initializing..."
        }


@router.get("/dex/swaps")
async def get_dex_whale_swaps(
    limit: int = Query(default=50, ge=1, le=200),
    symbol: Optional[str] = Query(default=None, description="Filter by token symbol"),
    min_value: float = Query(default=WHALE_THRESHOLD_USD, ge=1000)
):
    """
    Get recent DEX whale swaps from Chiliz Chain (FanX).
    """
    try:
        swaps = await get_recent_dex_swaps(
            limit=limit,
            token_symbol=symbol,
            min_value=min_value
        )

        return {
            "swaps": swaps,
            "count": len(swaps),
            "dex": "FanX",
            "chain": "Chiliz Chain",
            "threshold_usd": min_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching DEX swaps: {e}")
        return {
            "swaps": [],
            "count": 0,
            "dex": "FanX",
            "chain": "Chiliz Chain",
            "threshold_usd": min_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "DEX tracking initializing..."
        }


@router.get("/dex/volume")
async def get_dex_volume(
    hours: int = Query(default=24, ge=1, le=168)
):
    """
    Get DEX volume summary.
    """
    try:
        summary = await get_dex_volume_summary(hours=hours)
        return summary

    except Exception as e:
        logger.error(f"Error fetching DEX volume: {e}")
        return {
            "period_hours": hours,
            "dex": "FanX",
            "tokens": [],
            "note": "DEX tracking initializing..."
        }


@router.get("/combined")
async def get_combined_whale_activity(
    limit: int = Query(default=50, ge=1, le=100),
    symbol: Optional[str] = Query(default=None),
    min_value: float = Query(default=WHALE_THRESHOLD_USD)
):
    """
    Get combined whale activity from both CEX and DEX.
    Returns unified view sorted by time.
    """
    try:
        # Fetch from both sources
        cex_trades = await get_recent_whale_trades(
            limit=limit,
            symbol=symbol,
            min_value=min_value
        )

        dex_swaps = await get_recent_dex_swaps(
            limit=limit,
            token_symbol=symbol,
            min_value=min_value
        )

        # Normalize and combine
        combined = []

        for trade in cex_trades:
            combined.append({
                **trade,
                'venue': 'cex',
                'tx_hash': None,
            })

        for swap in dex_swaps:
            combined.append({
                'time': swap['time'],
                'symbol': swap['token_out'] if swap['side'] == 'buy' else swap['token_in'],
                'exchange': swap['dex_name'],
                'side': swap['side'],
                'price': swap['value_usd'] / max(swap['amount_out'], 0.001),
                'quantity': swap['amount_out'],
                'value_usd': swap['value_usd'],
                'is_aggressive': False,
                'venue': 'dex',
                'tx_hash': swap['tx_hash'],
            })

        # Sort by time
        combined.sort(key=lambda x: x['time'], reverse=True)

        return {
            "transactions": combined[:limit],
            "count": len(combined[:limit]),
            "cex_count": len(cex_trades),
            "dex_count": len(dex_swaps),
            "threshold_usd": min_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching combined whale activity: {e}")
        return {
            "transactions": [],
            "count": 0,
            "cex_count": 0,
            "dex_count": 0,
            "threshold_usd": min_value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/live")
async def get_live_whale_activity():
    """
    Get live whale activity from in-memory cache.
    For real-time WebSocket-style updates.
    """
    try:
        cex_tracker = await get_cex_tracker()
        dex_tracker = await get_dex_tracker()

        cex_trades = cex_tracker.get_recent_trades(limit=25)
        dex_swaps = dex_tracker.get_recent_swaps(limit=25)

        # Format for frontend
        live_activity = []

        for trade in cex_trades:
            live_activity.append({
                'time': trade['time'].isoformat() if hasattr(trade['time'], 'isoformat') else trade['time'],
                'venue': 'cex',
                'symbol': trade['symbol'],
                'exchange': trade['exchange'],
                'side': trade['side'],
                'value_usd': trade['value_usd'],
                'is_aggressive': trade.get('is_aggressive', False),
            })

        for swap in dex_swaps:
            live_activity.append({
                'time': swap['time'].isoformat() if hasattr(swap['time'], 'isoformat') else swap['time'],
                'venue': 'dex',
                'symbol': swap.get('token_out', 'UNKNOWN'),
                'exchange': swap.get('dex_name', 'FanX'),
                'side': 'buy' if swap.get('token_in') == 'CHZ' else 'sell',
                'value_usd': swap['value_usd'],
                'tx_hash': swap.get('tx_hash'),
            })

        # Sort by time
        live_activity.sort(
            key=lambda x: x['time'] if isinstance(x['time'], str) else x['time'].isoformat(),
            reverse=True
        )

        return {
            "activity": live_activity[:50],
            "count": len(live_activity),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching live whale activity: {e}")
        return {
            "activity": [],
            "count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/wallets")
async def get_known_wallets():
    """
    Get list of known whale wallets (exchanges, funds, etc.)
    """
    try:
        query = """
            SELECT address, label, wallet_type, e.name as exchange_name
            FROM whale_wallets ww
            LEFT JOIN exchanges e ON ww.exchange_id = e.id
            WHERE ww.is_tracked = TRUE
            ORDER BY ww.wallet_type, ww.label
        """

        rows = await Database.fetch(query)

        wallets = [
            {
                'address': row['address'],
                'label': row['label'],
                'type': row['wallet_type'],
                'exchange': row['exchange_name'],
            }
            for row in rows
        ]

        return {
            "wallets": wallets,
            "count": len(wallets),
        }

    except Exception as e:
        logger.error(f"Error fetching wallets: {e}")
        return {"wallets": [], "count": 0}


@router.get("/stats")
async def get_whale_stats():
    """
    Get overall whale tracking statistics.
    """
    try:
        # Get CEX stats
        cex_stats = await Database.fetchrow("""
            SELECT
                COUNT(*) as total_trades,
                SUM(value_usd) as total_volume,
                AVG(value_usd) as avg_trade_size,
                MAX(value_usd) as largest_trade,
                COUNT(DISTINCT exchange_name) as exchanges_active,
                COUNT(DISTINCT symbol) as tokens_active
            FROM cex_whale_transactions
            WHERE time > NOW() - INTERVAL '24 hours'
        """)

        # Get DEX stats
        dex_stats = await Database.fetchrow("""
            SELECT
                COUNT(*) as total_swaps,
                SUM(value_usd) as total_volume,
                AVG(value_usd) as avg_swap_size,
                MAX(value_usd) as largest_swap
            FROM dex_whale_swaps
            WHERE time > NOW() - INTERVAL '24 hours'
        """)

        return {
            "period": "24h",
            "cex": {
                "total_trades": cex_stats['total_trades'] or 0 if cex_stats else 0,
                "total_volume": float(cex_stats['total_volume'] or 0) if cex_stats else 0,
                "avg_trade_size": float(cex_stats['avg_trade_size'] or 0) if cex_stats else 0,
                "largest_trade": float(cex_stats['largest_trade'] or 0) if cex_stats else 0,
                "exchanges_active": cex_stats['exchanges_active'] or 0 if cex_stats else 0,
                "tokens_active": cex_stats['tokens_active'] or 0 if cex_stats else 0,
            },
            "dex": {
                "total_swaps": dex_stats['total_swaps'] or 0 if dex_stats else 0,
                "total_volume": float(dex_stats['total_volume'] or 0) if dex_stats else 0,
                "avg_swap_size": float(dex_stats['avg_swap_size'] or 0) if dex_stats else 0,
                "largest_swap": float(dex_stats['largest_swap'] or 0) if dex_stats else 0,
            },
            "threshold_usd": WHALE_THRESHOLD_USD,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching whale stats: {e}")
        return {
            "period": "24h",
            "cex": {},
            "dex": {},
            "threshold_usd": WHALE_THRESHOLD_USD,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
