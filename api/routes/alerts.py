"""
Alerts API Routes
Signal generation and alert management
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import httpx
import os

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.database import Database

router = APIRouter()

# Slack configuration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


class AlertRule(BaseModel):
    """Alert rule configuration"""
    name: str
    description: Optional[str]
    metric: str
    condition: str  # 'gt', 'lt', 'eq', 'change_pct'
    threshold: float
    token_filter: Optional[List[str]] = None
    severity: str = "medium"
    cooldown_minutes: int = 60
    delivery_channel: str = "slack"


class Signal(BaseModel):
    """Trading/Market signal"""
    token_symbol: str
    signal_type: str
    direction: Optional[str]
    confidence: float
    title: str
    description: str
    time_horizon: str
    management_priority: str


@router.get("/active")
async def get_active_alerts():
    """Get all active (unresolved) signals"""
    query = """
        SELECT
            s.id, ft.symbol, s.signal_type, s.direction, s.confidence,
            s.title, s.description, s.time_horizon, s.management_priority,
            s.created_at
        FROM signals s
        JOIN fan_tokens ft ON s.token_id = ft.id
        WHERE s.is_resolved = false
        ORDER BY s.created_at DESC
    """

    rows = await Database.fetch(query)

    return {
        "alerts": [
            {
                "id": row["id"],
                "symbol": row["symbol"],
                "type": row["signal_type"],
                "direction": row["direction"],
                "confidence": float(row["confidence"] or 0),
                "title": row["title"],
                "description": row["description"],
                "time_horizon": row["time_horizon"],
                "priority": row["management_priority"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in rows
        ],
        "count": len(rows),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/history")
async def get_alert_history(
    days: int = Query(7, description="Number of days of history"),
    resolved_only: bool = Query(False, description="Only show resolved alerts")
):
    """Get alert history"""
    query = """
        SELECT
            s.id, ft.symbol, s.signal_type, s.direction, s.confidence,
            s.title, s.description, s.time_horizon, s.management_priority,
            s.created_at, s.is_resolved, s.actual_outcome, s.resolved_at
        FROM signals s
        JOIN fan_tokens ft ON s.token_id = ft.id
        WHERE s.created_at > NOW() - INTERVAL '1 day' * $1
    """
    if resolved_only:
        query += " AND s.is_resolved = true"
    query += " ORDER BY s.created_at DESC"

    rows = await Database.fetch(query, days)

    return {
        "history": [
            {
                "id": row["id"],
                "symbol": row["symbol"],
                "type": row["signal_type"],
                "direction": row["direction"],
                "confidence": float(row["confidence"] or 0),
                "title": row["title"],
                "description": row["description"],
                "priority": row["management_priority"],
                "created_at": row["created_at"].isoformat(),
                "is_resolved": row["is_resolved"],
                "outcome": row["actual_outcome"],
                "resolved_at": row["resolved_at"].isoformat() if row["resolved_at"] else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.post("/resolve/{alert_id}")
async def resolve_alert(alert_id: int, outcome: str = Query(..., description="Outcome: 'correct', 'incorrect', 'neutral'")):
    """Mark an alert as resolved with outcome"""
    query = """
        UPDATE signals
        SET is_resolved = true, actual_outcome = $2, resolved_at = NOW()
        WHERE id = $1
        RETURNING id
    """

    result = await Database.fetchval(query, alert_id, outcome)
    if not result:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    return {"status": "resolved", "alert_id": alert_id, "outcome": outcome}


@router.get("/rules")
async def get_alert_rules():
    """Get all configured alert rules"""
    query = """
        SELECT id, name, description, metric, condition, threshold,
               token_filter, severity, cooldown_minutes, delivery_channel,
               is_active, last_triggered_at, trigger_count
        FROM alert_rules
        ORDER BY severity DESC, name
    """

    rows = await Database.fetch(query)

    return {
        "rules": [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "metric": row["metric"],
                "condition": row["condition"],
                "threshold": float(row["threshold"]),
                "token_filter": row["token_filter"],
                "severity": row["severity"],
                "cooldown_minutes": row["cooldown_minutes"],
                "delivery_channel": row["delivery_channel"],
                "is_active": row["is_active"],
                "last_triggered": row["last_triggered_at"].isoformat() if row["last_triggered_at"] else None,
                "trigger_count": row["trigger_count"],
            }
            for row in rows
        ]
    }


@router.post("/rules")
async def create_alert_rule(rule: AlertRule):
    """Create a new alert rule"""
    query = """
        INSERT INTO alert_rules
        (name, description, metric, condition, threshold, token_filter,
         severity, cooldown_minutes, delivery_channel)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
    """

    import json
    token_filter_json = json.dumps(rule.token_filter) if rule.token_filter else None

    rule_id = await Database.fetchval(
        query,
        rule.name, rule.description, rule.metric, rule.condition,
        rule.threshold, token_filter_json, rule.severity,
        rule.cooldown_minutes, rule.delivery_channel
    )

    return {"status": "created", "rule_id": rule_id}


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: int):
    """Delete an alert rule"""
    query = "DELETE FROM alert_rules WHERE id = $1 RETURNING id"
    result = await Database.fetchval(query, rule_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return {"status": "deleted", "rule_id": rule_id}


@router.post("/rules/{rule_id}/toggle")
async def toggle_alert_rule(rule_id: int):
    """Toggle an alert rule on/off"""
    query = """
        UPDATE alert_rules
        SET is_active = NOT is_active
        WHERE id = $1
        RETURNING id, is_active
    """

    row = await Database.fetchrow(query, rule_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Rule {rule_id} not found")

    return {"rule_id": row["id"], "is_active": row["is_active"]}


@router.post("/test-slack")
async def test_slack_alert():
    """Send a test alert to Slack to verify integration"""
    if not SLACK_WEBHOOK_URL:
        raise HTTPException(status_code=400, detail="SLACK_WEBHOOK_URL not configured")

    test_signal = {
        "signal_type": "test",
        "title": "🧪 Test Alert from Fan Token Intel",
        "direction": "neutral",
        "confidence": 1.0,
        "description": "This is a test alert to verify Slack integration is working correctly.",
        "time_horizon": "immediate",
        "management_priority": "high",
    }

    await _send_slack_alert(test_signal)

    return {
        "status": "sent",
        "message": "Test alert sent to Slack. Check your Slack channel.",
        "webhook_configured": True,
    }


@router.post("/generate")
async def trigger_signal_generation():
    """Manually trigger signal generation and get results"""
    count = await generate_signals()
    return {
        "status": "completed",
        "signals_generated": count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Signal Generation Functions

async def generate_signals():
    """Generate signals based on current market conditions"""
    signals = []

    # 1. Price Movement Signals
    price_signals = await _check_price_movements()
    signals.extend(price_signals)

    # 2. Volume Anomaly Signals
    volume_signals = await _check_volume_anomalies()
    signals.extend(volume_signals)

    # 3. Health Score Changes
    health_signals = await _check_health_changes()
    signals.extend(health_signals)

    # 4. Holder Movement Signals
    holder_signals = await _check_holder_movements()
    signals.extend(holder_signals)

    # 5. Liquidity Warnings
    liquidity_signals = await _check_liquidity_issues()
    signals.extend(liquidity_signals)

    # Insert new signals
    for signal in signals:
        await _insert_signal(signal)

    return len(signals)


async def _check_price_movements() -> List[Dict]:
    """Check for significant price movements"""
    signals = []

    query = """
        SELECT DISTINCT ON (token_id)
            ft.id as token_id, ft.symbol,
            tma.price_change_24h, tma.price_change_7d
        FROM token_metrics_aggregated tma
        JOIN fan_tokens ft ON tma.token_id = ft.id
        WHERE ft.is_active = true
        ORDER BY token_id, time DESC
    """
    rows = await Database.fetch(query)

    for row in rows:
        change_24h = float(row["price_change_24h"] or 0)

        if change_24h > 15:
            signals.append({
                "token_id": row["token_id"],
                "signal_type": "price_surge",
                "direction": "bullish",
                "confidence": min(0.9, 0.5 + change_24h / 50),
                "title": f"{row['symbol']} Price Surge (+{change_24h:.1f}%)",
                "description": f"{row['symbol']} has increased {change_24h:.1f}% in the last 24 hours. Consider taking profits or reviewing position.",
                "time_horizon": "short",
                "management_priority": "high" if change_24h > 25 else "medium",
            })
        elif change_24h < -15:
            signals.append({
                "token_id": row["token_id"],
                "signal_type": "price_drop",
                "direction": "bearish",
                "confidence": min(0.9, 0.5 + abs(change_24h) / 50),
                "title": f"{row['symbol']} Price Drop ({change_24h:.1f}%)",
                "description": f"{row['symbol']} has dropped {abs(change_24h):.1f}% in the last 24 hours. Review for buying opportunity or risk assessment.",
                "time_horizon": "short",
                "management_priority": "high" if change_24h < -25 else "medium",
            })

    return signals


async def _check_volume_anomalies() -> List[Dict]:
    """Check for unusual volume"""
    signals = []

    query = """
        WITH recent_volume AS (
            SELECT token_id, AVG(total_volume_24h) as avg_volume
            FROM token_metrics_aggregated
            WHERE time > NOW() - INTERVAL '7 days'
            GROUP BY token_id
        ),
        current_volume AS (
            SELECT DISTINCT ON (token_id)
                token_id, total_volume_24h as current_vol
            FROM token_metrics_aggregated
            ORDER BY token_id, time DESC
        )
        SELECT ft.id as token_id, ft.symbol,
               cv.current_vol, rv.avg_volume,
               cv.current_vol / NULLIF(rv.avg_volume, 0) as volume_ratio
        FROM fan_tokens ft
        JOIN current_volume cv ON ft.id = cv.token_id
        JOIN recent_volume rv ON ft.id = rv.token_id
        WHERE ft.is_active = true
    """
    rows = await Database.fetch(query)

    for row in rows:
        ratio = float(row["volume_ratio"] or 1)

        if ratio > 3:
            signals.append({
                "token_id": row["token_id"],
                "signal_type": "volume_spike",
                "direction": None,
                "confidence": min(0.85, 0.5 + (ratio - 3) / 10),
                "title": f"{row['symbol']} Volume Spike ({ratio:.1f}x average)",
                "description": f"{row['symbol']} volume is {ratio:.1f}x higher than 7-day average. Investigate for news or unusual activity.",
                "time_horizon": "immediate",
                "management_priority": "high",
            })

    return signals


async def _check_health_changes() -> List[Dict]:
    """Check for health score deterioration"""
    signals = []

    query = """
        WITH latest AS (
            SELECT DISTINCT ON (token_id)
                token_id, health_score, health_grade, time
            FROM token_metrics_aggregated
            ORDER BY token_id, time DESC
        ),
        previous AS (
            SELECT DISTINCT ON (token_id)
                token_id, health_score as prev_score
            FROM token_metrics_aggregated
            WHERE time < NOW() - INTERVAL '24 hours'
            ORDER BY token_id, time DESC
        )
        SELECT ft.id as token_id, ft.symbol,
               l.health_score, l.health_grade, p.prev_score,
               l.health_score - COALESCE(p.prev_score, l.health_score) as score_change
        FROM fan_tokens ft
        JOIN latest l ON ft.id = l.token_id
        LEFT JOIN previous p ON ft.id = p.token_id
        WHERE ft.is_active = true
    """
    rows = await Database.fetch(query)

    for row in rows:
        score_change = float(row["score_change"] or 0)
        health_score = int(row["health_score"] or 0)

        if score_change < -15:
            signals.append({
                "token_id": row["token_id"],
                "signal_type": "health_decline",
                "direction": "bearish",
                "confidence": min(0.8, 0.5 + abs(score_change) / 30),
                "title": f"{row['symbol']} Health Declining (now {health_score})",
                "description": f"{row['symbol']} health score dropped {abs(score_change):.0f} points. Current grade: {row['health_grade']}. Review metrics.",
                "time_horizon": "medium",
                "management_priority": "high" if health_score < 50 else "medium",
            })

    return signals


async def _check_holder_movements() -> List[Dict]:
    """Check for significant holder changes"""
    signals = []

    query = """
        SELECT DISTINCT ON (token_id)
            ft.id as token_id, ft.symbol,
            hs.total_holders, hs.holder_change_24h, hs.holder_change_7d
        FROM holder_snapshots hs
        JOIN fan_tokens ft ON hs.token_id = ft.id
        WHERE ft.is_active = true
        ORDER BY token_id, time DESC
    """
    rows = await Database.fetch(query)

    for row in rows:
        change_24h = int(row["holder_change_24h"] or 0)
        total = int(row["total_holders"] or 1)
        pct_change = (change_24h / total) * 100

        if pct_change < -5:
            signals.append({
                "token_id": row["token_id"],
                "signal_type": "holder_exodus",
                "direction": "bearish",
                "confidence": min(0.75, 0.4 + abs(pct_change) / 20),
                "title": f"{row['symbol']} Losing Holders ({change_24h:+d})",
                "description": f"{row['symbol']} lost {abs(change_24h)} holders ({abs(pct_change):.1f}%) in 24h. Potential distribution or concern.",
                "time_horizon": "medium",
                "management_priority": "medium",
            })
        elif pct_change > 5:
            signals.append({
                "token_id": row["token_id"],
                "signal_type": "holder_growth",
                "direction": "bullish",
                "confidence": min(0.75, 0.4 + pct_change / 20),
                "title": f"{row['symbol']} Holder Growth ({change_24h:+d})",
                "description": f"{row['symbol']} gained {change_24h} new holders ({pct_change:.1f}%) in 24h. Growing community interest.",
                "time_horizon": "medium",
                "management_priority": "low",
            })

    return signals


async def _check_liquidity_issues() -> List[Dict]:
    """Check for liquidity concerns"""
    signals = []

    query = """
        SELECT DISTINCT ON (ls.token_id)
            ft.id as token_id, ft.symbol,
            ls.bid_depth_2pct + ls.ask_depth_2pct as total_depth,
            ls.slippage_buy_10k, ls.slippage_sell_10k
        FROM liquidity_snapshots ls
        JOIN fan_tokens ft ON ls.token_id = ft.id
        WHERE ft.is_active = true
        ORDER BY ls.token_id, ls.time DESC
    """
    rows = await Database.fetch(query)

    for row in rows:
        slippage = max(
            float(row["slippage_buy_10k"] or 0),
            float(row["slippage_sell_10k"] or 0)
        )
        depth = float(row["total_depth"] or 0)

        if slippage > 5:
            signals.append({
                "token_id": row["token_id"],
                "signal_type": "liquidity_warning",
                "direction": None,
                "confidence": min(0.9, 0.5 + slippage / 20),
                "title": f"{row['symbol']} Low Liquidity ({slippage:.1f}% slippage)",
                "description": f"{row['symbol']} has high slippage ({slippage:.1f}% on $10k trade). Total depth: ${depth:,.0f}. Large trades not recommended.",
                "time_horizon": "immediate",
                "management_priority": "high",
            })

    return signals


async def _insert_signal(signal: Dict):
    """Insert a new signal, avoiding duplicates"""
    # Check for recent similar signal
    check_query = """
        SELECT id FROM signals
        WHERE token_id = $1 AND signal_type = $2
          AND created_at > NOW() - INTERVAL '4 hours'
          AND is_resolved = false
    """
    existing = await Database.fetchval(check_query, signal["token_id"], signal["signal_type"])
    if existing:
        return  # Don't duplicate

    insert_query = """
        INSERT INTO signals
        (token_id, signal_type, direction, confidence, title, description,
         time_horizon, management_priority)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
    """
    signal_id = await Database.fetchval(
        insert_query,
        signal["token_id"], signal["signal_type"], signal["direction"],
        signal["confidence"], signal["title"], signal["description"],
        signal["time_horizon"], signal["management_priority"]
    )

    # Send Slack notification for high priority signals
    if signal.get("management_priority") in ["high", "critical"]:
        await _send_slack_alert(signal)

    return signal_id


async def _send_slack_alert(signal: Dict):
    """Send alert to Slack webhook"""
    if not SLACK_WEBHOOK_URL:
        return

    # Emoji based on signal type
    emoji_map = {
        "price_surge": "🚀",
        "price_drop": "📉",
        "volume_spike": "📊",
        "health_decline": "⚠️",
        "holder_exodus": "🚪",
        "holder_growth": "📈",
        "liquidity_warning": "💧",
    }
    emoji = emoji_map.get(signal.get("signal_type", ""), "🔔")

    # Direction color
    direction = signal.get("direction", "")
    direction_emoji = "🟢" if direction == "bullish" else "🔴" if direction == "bearish" else "🟡"

    # Build Slack message blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {signal.get('title', 'New Signal')}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Type:*\n{signal.get('signal_type', 'N/A').replace('_', ' ').title()}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Direction:*\n{direction_emoji} {direction.title() if direction else 'Neutral'}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Confidence:*\n{signal.get('confidence', 0):.0%}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Priority:*\n{signal.get('management_priority', 'medium').upper()}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_{signal.get('description', '')}_"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Time Horizon: {signal.get('time_horizon', 'N/A')}"
                }
            ]
        },
        {
            "type": "divider"
        }
    ]

    payload = {
        "text": signal.get("title", "New Signal"),
        "blocks": blocks
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(SLACK_WEBHOOK_URL, json=payload, timeout=10.0)
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")
