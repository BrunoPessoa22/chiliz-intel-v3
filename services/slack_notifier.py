"""
Slack Notification Service
Sends alerts to Slack for recommendations, transfers, and other events
"""
import logging
import aiohttp
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from config.settings import slack_config

logger = logging.getLogger(__name__)


async def send_recommendation_alert(recommendation: Dict[str, Any]) -> bool:
    """
    Send a campaign recommendation alert to Slack.

    Args:
        recommendation: The recommendation dict with type, symbol, reasoning, etc.
    """
    if not slack_config.webhook_url:
        logger.warning("Slack webhook URL not configured")
        return False

    rec_type = recommendation.get("type", "")
    symbol = recommendation.get("symbol", "")
    headline = recommendation.get("headline", "")
    action = recommendation.get("action", "")
    reasoning = recommendation.get("reasoning", [])
    data = recommendation.get("data", {})
    confidence = recommendation.get("confidence_label", "Unknown")

    # Emoji based on recommendation type
    emoji_map = {
        "campaign_now": "🚀",
        "campaign_soon": "📅",
        "amplify": "📈",
        "avoid": "⛔",
        "hold": "⏸️",
    }
    emoji = emoji_map.get(rec_type, "💡")

    # Color based on type
    color_map = {
        "campaign_now": "#22c55e",  # Green
        "campaign_soon": "#3b82f6",  # Blue
        "amplify": "#a855f7",  # Purple
        "avoid": "#ef4444",  # Red
        "hold": "#6b7280",  # Gray
    }
    color = color_map.get(rec_type, "#6b7280")

    # Urgency label
    urgency = recommendation.get("urgency", "monitor")
    urgency_label = urgency.replace("_", " ").upper()

    # Build Slack message
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Campaign Recommendation: {symbol}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{headline}*"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Type:*\n{rec_type.replace('_', ' ').title()}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Urgency:*\n{urgency_label}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Signals (24h):*\n{data.get('signal_count_24h', 0):,}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Sentiment:*\n{(data.get('avg_sentiment', 0.5) * 100):.0f}%"
                },
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Reasoning:*\n" + "\n".join([f"• {r}" for r in reasoning[:3]])
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Recommended Action:*\n_{action}_"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Confidence: *{confidence}* | Activity Change: *{data.get('signal_change_ratio', 1.0):.1f}x* | Generated at {datetime.now(timezone.utc).strftime('%H:%M UTC')}"
                }
            ]
        },
        {
            "type": "divider"
        }
    ]

    # Add CTA button
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "View Dashboard",
                    "emoji": True
                },
                "url": "https://fantokenintel.vercel.app/recommendations",
                "style": "primary" if rec_type == "campaign_now" else None
            }
        ]
    })

    payload = {
        "blocks": blocks,
        "attachments": [
            {
                "color": color,
                "blocks": []
            }
        ]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                slack_config.webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Sent Slack alert for {symbol} recommendation")
                    return True
                else:
                    text = await resp.text()
                    logger.error(f"Slack API error: {resp.status} - {text}")
                    return False
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")
        return False


async def send_transfer_alert(alert: Dict[str, Any]) -> bool:
    """
    Send a transfer alert to Slack.

    Args:
        alert: The transfer alert dict
    """
    if not slack_config.webhook_url:
        return False

    symbol = alert.get("symbol", "")
    headline = alert.get("headline", "")
    description = alert.get("description", "")
    severity = alert.get("severity", "low")
    event_count = alert.get("event_count", 0)

    # Emoji based on severity
    emoji_map = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }
    emoji = emoji_map.get(severity, "⚪")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"⚽ Transfer Alert: {symbol}",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{headline}*\n{description}"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Severity:*\n{emoji} {severity.upper()}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Events:*\n{event_count}"
                },
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Transfer Room",
                        "emoji": True
                    },
                    "url": "https://fantokenintel.vercel.app/transfers"
                }
            ]
        }
    ]

    payload = {"blocks": blocks}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                slack_config.webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
    except Exception as e:
        logger.error(f"Failed to send transfer alert: {e}")
        return False


async def send_daily_summary(summary: Dict[str, Any]) -> bool:
    """
    Send a daily summary to Slack.
    """
    if not slack_config.webhook_url:
        return False

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Daily Fan Token Intelligence Summary",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Campaign Opportunities:*\n{summary.get('campaign_opportunities', 0)}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Tokens to Avoid:*\n{summary.get('tokens_to_avoid', 0)}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Transfer Alerts:*\n{summary.get('transfer_alerts', 0)}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Social Signals:*\n{summary.get('total_signals', 0):,}"
                },
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Executive Summary:*\n{summary.get('executive_summary', 'No significant activity.')}"
            }
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Full Dashboard",
                        "emoji": True
                    },
                    "url": "https://fantokenintel.vercel.app",
                    "style": "primary"
                }
            ]
        }
    ]

    payload = {"blocks": blocks}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                slack_config.webhook_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
    except Exception as e:
        logger.error(f"Failed to send daily summary: {e}")
        return False
