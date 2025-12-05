"""
Slack Notification Service
Sends alerts to Slack for recommendations, transfers, and other events
Uses Slack Bot API (chat.postMessage) for flexible channel targeting
"""
import logging
import aiohttp
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Slack Bot configuration
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "social-sentiment")
SLACK_API_URL = "https://slack.com/api/chat.postMessage"


async def _send_to_slack(blocks: List[Dict], text: str, attachments: Optional[List[Dict]] = None) -> bool:
    """
    Send a message to Slack using the Bot API.

    Args:
        blocks: Slack block kit blocks
        text: Fallback text for notifications
        attachments: Optional attachments with colors
    """
    if not SLACK_BOT_TOKEN:
        logger.warning("SLACK_BOT_TOKEN not configured")
        return False

    payload = {
        "channel": SLACK_CHANNEL,
        "text": text,
        "blocks": blocks,
    }

    if attachments:
        payload["attachments"] = attachments

    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SLACK_API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    logger.info(f"Sent Slack message to #{SLACK_CHANNEL}")
                    return True
                else:
                    logger.error(f"Slack API error: {data.get('error')}")
                    return False
    except Exception as e:
        logger.error(f"Failed to send Slack message: {e}")
        return False


async def send_recommendation_alert(recommendation: Dict[str, Any]) -> bool:
    """
    Send a campaign recommendation alert to Slack.

    Args:
        recommendation: The recommendation dict with type, symbol, reasoning, etc.
    """
    rec_type = recommendation.get("type", "")
    symbol = recommendation.get("symbol", "")
    headline = recommendation.get("headline", "")
    action = recommendation.get("action", "")
    reasoning = recommendation.get("reasoning", [])
    data = recommendation.get("data", {})
    confidence = recommendation.get("confidence_label", "Unknown")

    # Emoji based on recommendation type
    emoji_map = {
        "campaign_now": ":rocket:",
        "market_momentum": ":chart_with_upwards_trend:",
        "amplify": ":loudspeaker:",
        "watch": ":eyes:",
        "avoid": ":no_entry:",
    }
    emoji = emoji_map.get(rec_type, ":bulb:")

    # Color based on type
    color_map = {
        "campaign_now": "#22c55e",  # Green - highest priority
        "market_momentum": "#f59e0b",  # Orange - market moving
        "amplify": "#a855f7",  # Purple - social growth
        "watch": "#6b7280",  # Gray - monitor
        "avoid": "#ef4444",  # Red - negative
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
                    "text": f"*Price 24h:*\n{data.get('price_change_24h', 0):+.1f}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Volume:*\n${data.get('volume_usd', 0):,.0f}"
                },
            ]
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Signals (24h):*\n{data.get('signal_count_24h', 0):,}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Sentiment:*\n{(data.get('avg_sentiment', 0.5) * 100):.0f}%"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Social Change:*\n{data.get('signal_change_ratio', 1.0):.1f}x"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Volume Change:*\n{data.get('volume_change_ratio', 1.0):.1f}x"
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

    attachments = [
        {
            "color": color,
            "blocks": []
        }
    ]

    fallback_text = f"{emoji} {headline}"
    return await _send_to_slack(blocks, fallback_text, attachments)


async def send_transfer_alert(alert: Dict[str, Any]) -> bool:
    """
    Send a transfer alert to Slack.

    Args:
        alert: The transfer alert dict
    """
    symbol = alert.get("symbol", "")
    headline = alert.get("headline", "")
    description = alert.get("description", "")
    severity = alert.get("severity", "low")
    event_count = alert.get("event_count", 0)

    # Emoji based on severity
    emoji_map = {
        "critical": ":red_circle:",
        "high": ":large_orange_circle:",
        "medium": ":large_yellow_circle:",
        "low": ":large_green_circle:",
    }
    emoji = emoji_map.get(severity, ":white_circle:")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":soccer: Transfer Alert: {symbol}",
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

    fallback_text = f":soccer: Transfer Alert: {symbol} - {headline}"
    return await _send_to_slack(blocks, fallback_text)


async def send_daily_summary(summary: Dict[str, Any]) -> bool:
    """
    Send a daily summary to Slack.
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": ":bar_chart: Daily Fan Token Intelligence Summary",
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

    fallback_text = ":bar_chart: Daily Fan Token Intelligence Summary"
    return await _send_to_slack(blocks, fallback_text)
