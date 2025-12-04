"""
AI-Powered Campaign Recommendations Engine
Generates actionable campaign recommendations for C-level executives
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from services.database import Database

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    CAMPAIGN_NOW = "campaign_now"          # Strong signal to launch campaign
    CAMPAIGN_SOON = "campaign_soon"        # Good opportunity coming up
    AMPLIFY = "amplify"                    # Organic growth - boost it
    HOLD = "hold"                          # Wait for better timing
    AVOID = "avoid"                        # Negative signals - don't campaign


class Urgency(Enum):
    IMMEDIATE = "immediate"    # Act within 24 hours
    THIS_WEEK = "this_week"    # Act within 7 days
    MONITOR = "monitor"        # Keep watching


@dataclass
class Recommendation:
    token_symbol: str
    token_team: str
    recommendation_type: RecommendationType
    urgency: Urgency
    headline: str
    reasoning: List[str]
    action: str
    confidence: float  # 0-1
    data_points: Dict[str, Any]


class RecommendationsEngine:
    """Generate AI-powered campaign recommendations"""

    # Thresholds for recommendations
    SOCIAL_SPIKE_THRESHOLD = 2.0      # 2x normal activity
    POSITIVE_SENTIMENT_THRESHOLD = 0.6
    NEGATIVE_SENTIMENT_THRESHOLD = 0.4
    MIN_SIGNALS_FOR_CONFIDENCE = 50

    async def get_all_recommendations(self) -> Dict[str, Any]:
        """Get all current recommendations across tokens"""
        recommendations = []

        # Get token data with social signals
        tokens_data = await self._get_tokens_with_signals()

        for token in tokens_data:
            rec = await self._analyze_token(token)
            if rec:
                recommendations.append(rec)

        # Sort by urgency and confidence
        recommendations.sort(
            key=lambda r: (
                0 if r.urgency == Urgency.IMMEDIATE else (1 if r.urgency == Urgency.THIS_WEEK else 2),
                -r.confidence
            )
        )

        # Categorize recommendations
        campaign_now = [r for r in recommendations if r.recommendation_type == RecommendationType.CAMPAIGN_NOW]
        campaign_soon = [r for r in recommendations if r.recommendation_type == RecommendationType.CAMPAIGN_SOON]
        amplify = [r for r in recommendations if r.recommendation_type == RecommendationType.AMPLIFY]
        avoid = [r for r in recommendations if r.recommendation_type == RecommendationType.AVOID]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_analyzed": len(tokens_data),
                "campaign_opportunities": len(campaign_now) + len(campaign_soon),
                "tokens_to_avoid": len(avoid),
                "amplify_opportunities": len(amplify),
            },
            "campaign_now": [self._recommendation_to_dict(r) for r in campaign_now],
            "campaign_soon": [self._recommendation_to_dict(r) for r in campaign_soon],
            "amplify": [self._recommendation_to_dict(r) for r in amplify],
            "avoid": [self._recommendation_to_dict(r) for r in avoid],
            "executive_summary": self._generate_executive_summary(recommendations),
        }

    async def get_token_recommendation(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get specific recommendation for a token"""
        token_data = await self._get_token_data(symbol)
        if not token_data:
            return None

        rec = await self._analyze_token(token_data)
        if not rec:
            return {"symbol": symbol, "recommendation": "Insufficient data for recommendation"}

        return self._recommendation_to_dict(rec)

    async def _get_tokens_with_signals(self) -> List[Dict]:
        """Get all tokens with their current signal data"""
        query = """
            WITH token_signals AS (
                SELECT
                    ft.id,
                    ft.symbol,
                    ft.team,
                    ft.league,
                    COUNT(ss.id) as signal_count_24h,
                    AVG(ss.sentiment_score) as avg_sentiment,
                    SUM(ss.engagement) as total_engagement,
                    SUM(CASE WHEN ss.is_high_priority THEN 1 ELSE 0 END) as high_priority_count,
                    SUM(CASE WHEN ss.sentiment_score > 0.6 THEN 1 ELSE 0 END) as positive_signals,
                    SUM(CASE WHEN ss.sentiment_score < 0.4 THEN 1 ELSE 0 END) as negative_signals
                FROM fan_tokens ft
                LEFT JOIN social_signals ss ON ft.id = ss.token_id
                    AND ss.time > NOW() - INTERVAL '24 hours'
                WHERE ft.is_active = true
                AND ft.symbol NOT IN ('SANTOS', 'LAZIO', 'PORTO', 'ALPINE')
                GROUP BY ft.id, ft.symbol, ft.team, ft.league
            ),
            token_signals_prev AS (
                SELECT
                    ft.id,
                    COUNT(ss.id) as signal_count_prev_24h
                FROM fan_tokens ft
                LEFT JOIN social_signals ss ON ft.id = ss.token_id
                    AND ss.time BETWEEN NOW() - INTERVAL '48 hours' AND NOW() - INTERVAL '24 hours'
                WHERE ft.is_active = true
                GROUP BY ft.id
            )
            SELECT
                ts.*,
                tsp.signal_count_prev_24h,
                CASE
                    WHEN tsp.signal_count_prev_24h > 0
                    THEN ts.signal_count_24h::float / tsp.signal_count_prev_24h
                    ELSE 1.0
                END as signal_change_ratio
            FROM token_signals ts
            LEFT JOIN token_signals_prev tsp ON ts.id = tsp.id
            WHERE ts.signal_count_24h > 0
            ORDER BY ts.signal_count_24h DESC
        """

        rows = await Database.fetch(query)
        return [dict(row) for row in rows]

    async def _get_token_data(self, symbol: str) -> Optional[Dict]:
        """Get specific token data"""
        tokens = await self._get_tokens_with_signals()
        for token in tokens:
            if token["symbol"].upper() == symbol.upper():
                return token
        return None

    async def _analyze_token(self, token: Dict) -> Optional[Recommendation]:
        """Analyze a token and generate recommendation"""
        symbol = token["symbol"]
        team = token.get("team", symbol)

        signal_count = token.get("signal_count_24h", 0)
        avg_sentiment = token.get("avg_sentiment", 0.5)
        signal_change = token.get("signal_change_ratio", 1.0)
        positive_signals = token.get("positive_signals", 0)
        negative_signals = token.get("negative_signals", 0)
        high_priority = token.get("high_priority_count", 0)
        engagement = token.get("total_engagement", 0)

        # Calculate confidence based on data volume
        confidence = min(1.0, signal_count / self.MIN_SIGNALS_FOR_CONFIDENCE)

        reasoning = []
        data_points = {
            "signal_count_24h": signal_count,
            "avg_sentiment": round(avg_sentiment, 2) if avg_sentiment else 0.5,
            "signal_change_ratio": round(signal_change, 2) if signal_change else 1.0,
            "positive_signals": positive_signals,
            "negative_signals": negative_signals,
            "high_priority_signals": high_priority,
            "total_engagement": engagement,
        }

        # Decision logic

        # AVOID: Negative sentiment spike
        if avg_sentiment and avg_sentiment < self.NEGATIVE_SENTIMENT_THRESHOLD and signal_count > 20:
            reasoning.append(f"Negative sentiment detected ({avg_sentiment:.0%})")
            reasoning.append(f"{negative_signals} negative signals in 24h")
            if signal_change > 1.5:
                reasoning.append(f"Activity spiking {signal_change:.1f}x during negative period")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.AVOID,
                urgency=Urgency.IMMEDIATE,
                headline=f"Avoid {symbol} - Negative sentiment spike",
                reasoning=reasoning,
                action=f"Do NOT run campaigns on {symbol} until sentiment improves. Monitor for recovery.",
                confidence=confidence,
                data_points=data_points,
            )

        # CAMPAIGN NOW: High activity + positive sentiment + spike
        if (signal_change >= self.SOCIAL_SPIKE_THRESHOLD and
            avg_sentiment and avg_sentiment >= self.POSITIVE_SENTIMENT_THRESHOLD and
            signal_count >= 30):

            reasoning.append(f"Social activity spiking {signal_change:.1f}x vs yesterday")
            reasoning.append(f"Strong positive sentiment ({avg_sentiment:.0%})")
            reasoning.append(f"{positive_signals} positive signals driving momentum")
            if high_priority > 5:
                reasoning.append(f"{high_priority} high-priority mentions (influencers/news)")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.CAMPAIGN_NOW,
                urgency=Urgency.IMMEDIATE,
                headline=f"Campaign NOW on {symbol} - Momentum is peaking",
                reasoning=reasoning,
                action=f"Launch {symbol} campaign immediately to ride the organic momentum wave.",
                confidence=confidence,
                data_points=data_points,
            )

        # AMPLIFY: Good organic growth, positive sentiment
        if (avg_sentiment and avg_sentiment >= 0.55 and
            signal_change >= 1.3 and
            signal_count >= 20):

            reasoning.append(f"Organic growth detected ({signal_change:.1f}x activity increase)")
            reasoning.append(f"Positive community sentiment ({avg_sentiment:.0%})")
            reasoning.append(f"{signal_count} signals showing sustained interest")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.AMPLIFY,
                urgency=Urgency.THIS_WEEK,
                headline=f"Amplify {symbol} - Organic growth opportunity",
                reasoning=reasoning,
                action=f"Boost {symbol} with targeted content to amplify existing organic momentum.",
                confidence=confidence,
                data_points=data_points,
            )

        # CAMPAIGN SOON: Stable positive sentiment, good engagement
        if (avg_sentiment and avg_sentiment >= 0.5 and
            signal_count >= 50 and
            high_priority >= 3):

            reasoning.append(f"Healthy engagement levels ({signal_count} signals)")
            reasoning.append(f"Neutral-positive sentiment ({avg_sentiment:.0%})")
            reasoning.append(f"{high_priority} influencer/news mentions")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.CAMPAIGN_SOON,
                urgency=Urgency.THIS_WEEK,
                headline=f"{symbol} ready for campaign - Good baseline activity",
                reasoning=reasoning,
                action=f"Plan {symbol} campaign for this week. Consider timing around team events.",
                confidence=confidence,
                data_points=data_points,
            )

        # Default: HOLD/MONITOR
        if signal_count >= 10:
            reasoning.append(f"Moderate activity ({signal_count} signals)")
            reasoning.append(f"Sentiment neutral ({avg_sentiment:.0%})" if avg_sentiment else "Limited sentiment data")
            reasoning.append("No strong signals for campaign timing")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.HOLD,
                urgency=Urgency.MONITOR,
                headline=f"{symbol} - Monitor for opportunities",
                reasoning=reasoning,
                action=f"Continue monitoring {symbol}. Wait for sentiment shift or activity spike.",
                confidence=confidence,
                data_points=data_points,
            )

        return None  # Not enough data

    def _recommendation_to_dict(self, rec: Recommendation) -> Dict[str, Any]:
        """Convert recommendation to API response format"""
        return {
            "symbol": rec.token_symbol,
            "team": rec.token_team,
            "type": rec.recommendation_type.value,
            "urgency": rec.urgency.value,
            "headline": rec.headline,
            "reasoning": rec.reasoning,
            "action": rec.action,
            "confidence": round(rec.confidence, 2),
            "confidence_label": self._confidence_label(rec.confidence),
            "data": rec.data_points,
        }

    def _confidence_label(self, confidence: float) -> str:
        if confidence >= 0.8:
            return "High"
        elif confidence >= 0.5:
            return "Medium"
        else:
            return "Low"

    def _generate_executive_summary(self, recommendations: List[Recommendation]) -> str:
        """Generate a one-paragraph executive summary"""
        campaign_now = [r for r in recommendations if r.recommendation_type == RecommendationType.CAMPAIGN_NOW]
        avoid = [r for r in recommendations if r.recommendation_type == RecommendationType.AVOID]
        amplify = [r for r in recommendations if r.recommendation_type == RecommendationType.AMPLIFY]

        parts = []

        if campaign_now:
            tokens = ", ".join([r.token_symbol for r in campaign_now[:3]])
            parts.append(f"**Immediate opportunity**: {tokens} showing strong momentum - campaign now to maximize impact.")

        if avoid:
            tokens = ", ".join([r.token_symbol for r in avoid[:3]])
            parts.append(f"**Caution**: Avoid campaigns on {tokens} due to negative sentiment.")

        if amplify:
            tokens = ", ".join([r.token_symbol for r in amplify[:3]])
            parts.append(f"**Growth opportunity**: {tokens} showing organic growth - consider amplification.")

        if not parts:
            return "Market is stable. No urgent campaign opportunities or risks detected. Continue monitoring for emerging signals."

        return " ".join(parts)
