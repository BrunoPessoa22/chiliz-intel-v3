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
    CAMPAIGN_NOW = "campaign_now"          # Strong signal to launch campaign (social + market confirmation)
    MARKET_MOMENTUM = "market_momentum"    # Price/volume spike without social (still high priority)
    AMPLIFY = "amplify"                    # Social growth with volume - boost it
    WATCH = "watch"                        # Interesting signals but low volume - monitor only
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

    # Market thresholds (NEW)
    MIN_VOLUME_USD = 10_000           # $10k minimum for high priority actions
    PRICE_SPIKE_THRESHOLD = 15.0      # 15% price increase triggers attention
    VOLUME_SPIKE_THRESHOLD = 3.0      # 3x volume increase

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
        market_momentum = [r for r in recommendations if r.recommendation_type == RecommendationType.MARKET_MOMENTUM]
        amplify = [r for r in recommendations if r.recommendation_type == RecommendationType.AMPLIFY]
        watch = [r for r in recommendations if r.recommendation_type == RecommendationType.WATCH]
        avoid = [r for r in recommendations if r.recommendation_type == RecommendationType.AVOID]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_analyzed": len(tokens_data),
                "campaign_opportunities": len(campaign_now) + len(market_momentum),
                "amplify_opportunities": len(amplify),
                "watching": len(watch),
                "tokens_to_avoid": len(avoid),
            },
            "campaign_now": [self._recommendation_to_dict(r) for r in campaign_now],
            "market_momentum": [self._recommendation_to_dict(r) for r in market_momentum],
            "amplify": [self._recommendation_to_dict(r) for r in amplify],
            "watch": [self._recommendation_to_dict(r) for r in watch],
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
        """Get all tokens with their current signal data AND market data"""
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
            ),
            market_data AS (
                SELECT DISTINCT ON (token_id)
                    token_id,
                    total_volume_24h as volume_usd,
                    price_change_24h,
                    vwap_price as current_price
                FROM token_metrics_aggregated
                ORDER BY token_id, time DESC
            ),
            volume_avg AS (
                SELECT
                    token_id,
                    AVG(total_volume_24h) as avg_volume_7d
                FROM token_metrics_aggregated
                WHERE time > NOW() - INTERVAL '7 days'
                GROUP BY token_id
            )
            SELECT
                ts.*,
                tsp.signal_count_prev_24h,
                CASE
                    WHEN tsp.signal_count_prev_24h > 0
                    THEN ts.signal_count_24h::float / tsp.signal_count_prev_24h
                    ELSE 1.0
                END as signal_change_ratio,
                COALESCE(md.volume_usd, 0) as volume_usd,
                COALESCE(md.price_change_24h, 0) as price_change_24h,
                COALESCE(md.current_price, 0) as current_price,
                COALESCE(va.avg_volume_7d, 0) as avg_volume_7d,
                CASE
                    WHEN va.avg_volume_7d > 0
                    THEN md.volume_usd / va.avg_volume_7d
                    ELSE 1.0
                END as volume_change_ratio
            FROM token_signals ts
            LEFT JOIN token_signals_prev tsp ON ts.id = tsp.id
            LEFT JOIN market_data md ON ts.id = md.token_id
            LEFT JOIN volume_avg va ON ts.id = va.token_id
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
        """Analyze a token and generate recommendation based on social + market signals"""
        symbol = token["symbol"]
        team = token.get("team", symbol)

        # Social metrics
        signal_count = token.get("signal_count_24h", 0) or 0
        avg_sentiment = token.get("avg_sentiment") or 0.5
        signal_change = token.get("signal_change_ratio") or 1.0
        positive_signals = token.get("positive_signals", 0) or 0
        negative_signals = token.get("negative_signals", 0) or 0
        high_priority = token.get("high_priority_count", 0) or 0
        engagement = token.get("total_engagement", 0) or 0

        # Market metrics (NEW)
        volume_usd = float(token.get("volume_usd", 0) or 0)
        price_change_24h = float(token.get("price_change_24h", 0) or 0)
        volume_change_ratio = float(token.get("volume_change_ratio", 1.0) or 1.0)
        current_price = float(token.get("current_price", 0) or 0)

        # Derived flags
        has_sufficient_volume = volume_usd >= self.MIN_VOLUME_USD
        has_price_spike = price_change_24h >= self.PRICE_SPIKE_THRESHOLD
        has_volume_spike = volume_change_ratio >= self.VOLUME_SPIKE_THRESHOLD
        has_social_spike = signal_change >= self.SOCIAL_SPIKE_THRESHOLD and signal_count >= 20
        has_positive_sentiment = avg_sentiment >= self.POSITIVE_SENTIMENT_THRESHOLD
        has_negative_sentiment = avg_sentiment < self.NEGATIVE_SENTIMENT_THRESHOLD and signal_count > 10
        has_market_signal = has_price_spike or has_volume_spike

        # Calculate confidence based on data completeness
        confidence_factors = [
            min(1.0, signal_count / self.MIN_SIGNALS_FOR_CONFIDENCE),
            1.0 if volume_usd > 0 else 0.5,
            1.0 if has_sufficient_volume else 0.7,
        ]
        confidence = sum(confidence_factors) / len(confidence_factors)

        reasoning = []
        data_points = {
            "signal_count_24h": signal_count,
            "avg_sentiment": round(avg_sentiment, 2),
            "signal_change_ratio": round(signal_change, 2),
            "positive_signals": positive_signals,
            "negative_signals": negative_signals,
            "high_priority_signals": high_priority,
            "total_engagement": engagement,
            # Market data (NEW)
            "volume_usd": round(volume_usd, 2),
            "price_change_24h": round(price_change_24h, 2),
            "volume_change_ratio": round(volume_change_ratio, 2),
            "current_price": round(current_price, 4),
            "has_sufficient_volume": has_sufficient_volume,
        }

        # ========================================
        # PRIORITY 1: AVOID - Negative Sentiment
        # ========================================
        if has_negative_sentiment:
            reasoning.append(f"Negative sentiment detected ({avg_sentiment:.0%})")
            reasoning.append(f"{negative_signals} negative signals in 24h")
            if signal_change > 1.5:
                reasoning.append(f"Activity spiking {signal_change:.1f}x during negative period")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.AVOID,
                urgency=Urgency.IMMEDIATE,
                headline=f"Avoid {symbol} - Negative sentiment",
                reasoning=reasoning,
                action=f"Do NOT run campaigns on {symbol} until sentiment improves. Monitor for recovery.",
                confidence=confidence,
                data_points=data_points,
            )

        # ========================================
        # PRIORITY 2: CAMPAIGN NOW - Social + Market + Volume
        # Social spike WITH market confirmation (price or volume spike)
        # ========================================
        if has_social_spike and has_market_signal and has_sufficient_volume:
            reasoning.append(f"Social activity spiking {signal_change:.1f}x vs yesterday")
            if has_price_spike:
                reasoning.append(f"Price surging +{price_change_24h:.1f}% in 24h")
            if has_volume_spike:
                reasoning.append(f"Volume spiking {volume_change_ratio:.1f}x vs 7-day average")
            reasoning.append(f"Strong volume: ${volume_usd:,.0f} (above $10k threshold)")
            if has_positive_sentiment:
                reasoning.append(f"Positive sentiment ({avg_sentiment:.0%})")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.CAMPAIGN_NOW,
                urgency=Urgency.IMMEDIATE,
                headline=f"CAMPAIGN NOW: {symbol} - Social + Market momentum confirmed",
                reasoning=reasoning,
                action=f"Launch {symbol} campaign IMMEDIATELY. Both social and market signals aligned.",
                confidence=min(0.95, confidence + 0.1),
                data_points=data_points,
            )

        # ========================================
        # PRIORITY 3: MARKET MOMENTUM - Price/Volume spike (no social needed)
        # ========================================
        if has_market_signal and has_sufficient_volume and not has_social_spike:
            if has_price_spike:
                reasoning.append(f"Price surging +{price_change_24h:.1f}% in 24h")
            if has_volume_spike:
                reasoning.append(f"Volume spiking {volume_change_ratio:.1f}x vs 7-day average")
            reasoning.append(f"Strong volume: ${volume_usd:,.0f}")
            reasoning.append(f"Social activity normal ({signal_count} signals) - opportunity to amplify market move")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.MARKET_MOMENTUM,
                urgency=Urgency.THIS_WEEK,
                headline=f"MARKET MOMENTUM: {symbol} +{price_change_24h:.1f}% - Consider campaign",
                reasoning=reasoning,
                action=f"Market is moving on {symbol}. Launch campaign to amplify price/volume momentum.",
                confidence=confidence,
                data_points=data_points,
            )

        # ========================================
        # PRIORITY 4: AMPLIFY - Social spike with volume (no price confirmation yet)
        # ========================================
        if has_social_spike and has_sufficient_volume and not has_market_signal:
            reasoning.append(f"Social activity spiking {signal_change:.1f}x vs yesterday")
            reasoning.append(f"Volume healthy: ${volume_usd:,.0f}")
            reasoning.append(f"Price stable ({price_change_24h:+.1f}%) - social leading indicator")
            if has_positive_sentiment:
                reasoning.append(f"Positive sentiment ({avg_sentiment:.0%})")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.AMPLIFY,
                urgency=Urgency.THIS_WEEK,
                headline=f"AMPLIFY: {symbol} - Social spike, volume ready",
                reasoning=reasoning,
                action=f"Boost {symbol} now. Social momentum building, market may follow.",
                confidence=confidence,
                data_points=data_points,
            )

        # ========================================
        # PRIORITY 5: WATCH - Interesting signals but low volume
        # ========================================
        has_any_signal = (
            has_social_spike or
            has_market_signal or
            (signal_count >= 30 and has_positive_sentiment) or
            high_priority >= 3
        )

        if has_any_signal and not has_sufficient_volume:
            if has_social_spike:
                reasoning.append(f"Social activity spiking {signal_change:.1f}x")
            if has_price_spike:
                reasoning.append(f"Price up +{price_change_24h:.1f}%")
            if has_volume_spike:
                reasoning.append(f"Volume up {volume_change_ratio:.1f}x")
            reasoning.append(f"LOW VOLUME: ${volume_usd:,.0f} (below $10k threshold)")
            reasoning.append("Monitor but don't prioritize - liquidity insufficient for campaign ROI")

            return Recommendation(
                token_symbol=symbol,
                token_team=team,
                recommendation_type=RecommendationType.WATCH,
                urgency=Urgency.MONITOR,
                headline=f"WATCH: {symbol} - Signals present but low volume",
                reasoning=reasoning,
                action=f"Monitor {symbol}. Interesting signals but volume too low for immediate action.",
                confidence=confidence * 0.8,
                data_points=data_points,
            )

        # ========================================
        # DEFAULT: No recommendation (not enough signals)
        # ========================================
        return None

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
        market_momentum = [r for r in recommendations if r.recommendation_type == RecommendationType.MARKET_MOMENTUM]
        amplify = [r for r in recommendations if r.recommendation_type == RecommendationType.AMPLIFY]
        watch = [r for r in recommendations if r.recommendation_type == RecommendationType.WATCH]
        avoid = [r for r in recommendations if r.recommendation_type == RecommendationType.AVOID]

        parts = []

        if campaign_now:
            tokens = ", ".join([r.token_symbol for r in campaign_now[:3]])
            parts.append(f"**IMMEDIATE ACTION**: {tokens} - social AND market signals aligned. Campaign now.")

        if market_momentum:
            tokens_with_change = [f"{r.token_symbol} (+{r.data_points.get('price_change_24h', 0):.0f}%)" for r in market_momentum[:3]]
            parts.append(f"**MARKET MOMENTUM**: {', '.join(tokens_with_change)} - price/volume spiking, consider campaign.")

        if amplify:
            tokens = ", ".join([r.token_symbol for r in amplify[:3]])
            parts.append(f"**AMPLIFY**: {tokens} - social momentum building with good volume.")

        if avoid:
            tokens = ", ".join([r.token_symbol for r in avoid[:3]])
            parts.append(f"**AVOID**: {tokens} - negative sentiment detected.")

        if watch and not (campaign_now or market_momentum or amplify):
            tokens = ", ".join([r.token_symbol for r in watch[:3]])
            parts.append(f"**WATCHING**: {tokens} - signals present but low volume. Monitor only.")

        if not parts:
            return "Market is stable. No urgent campaign opportunities or risks detected. Continue monitoring for emerging signals."

        return " ".join(parts)
