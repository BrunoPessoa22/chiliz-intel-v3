"""
AI Management Assistant API Routes
Natural language Q&A for executives using Claude via OpenRouter
"""
import json
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import aiohttp

from config.settings import openrouter_config
from services.database import Database

router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model"""
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    """Chat request model"""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response model"""
    response: str
    session_id: str
    data: Optional[Dict[str, Any]] = None
    chart_type: Optional[str] = None
    sources: Optional[List[str]] = None


class AIAssistant:
    """AI Management Assistant using Claude via OpenRouter"""

    SYSTEM_PROMPT = """You are an AI Management Assistant for Chiliz, helping executives understand fan token market data and make campaign decisions.

You have access to REAL-TIME data about:
- Fan token prices, volumes, and market caps (from CoinGecko)
- Social activity metrics: tweet counts, sentiment, engagement (from X/Twitter)
- Social → Price correlations: whether social noise predicts price movements
- Campaign impact data: before/during/after comparisons
- Upcoming match fixtures and catalysts

CORE PoC QUESTIONS YOU CAN ANSWER:
1. "Does social noise predict price?" → Use correlation data to answer with specific r values and lag times
2. "Did our campaign work?" → Use campaign impact metrics to show before/after changes
3. "Which token should we campaign for?" → Combine social momentum, upcoming fixtures, and price position

When answering questions:
1. Be concise and executive-focused - they want decisions, not essays
2. Use SPECIFIC numbers: "BAR tweets up 45%, price lagged by 6 hours" not "social activity increased"
3. Give actionable recommendations: "Launch campaign now" or "Wait for match day"
4. If data is insufficient, say so clearly and explain what's needed

Format responses with:
- **Bold** for key metrics and recommendations
- Bullet points for lists
- Short paragraphs (2-3 sentences max)"""

    def __init__(self):
        self.api_key = openrouter_config.api_key
        self.base_url = openrouter_config.base_url
        self.model = openrouter_config.model

    async def get_context_data(self, query: str) -> Dict[str, Any]:
        """Fetch relevant data based on the query"""
        context = {}
        query_lower = query.lower()

        # Check for pre-built queries first
        prebuilt = await self._match_prebuilt_query(query)
        if prebuilt:
            context["prebuilt_result"] = prebuilt

        # Always include current portfolio overview from live data
        try:
            from services.live_data import get_live_service
            service = await get_live_service()
            overview = await service.get_portfolio_overview()
            context["portfolio_overview"] = overview

            # Get top tokens
            tokens = await service.fetch_all_tokens()
            context["top_tokens"] = tokens[:10]  # Top 10 by market cap
        except Exception as e:
            context["portfolio_error"] = str(e)

        # If asking about correlation / prediction / social
        if any(word in query_lower for word in ["predict", "correlat", "social", "twitter", "noise", "lead", "lag"]):
            try:
                from services.correlation_engine import CorrelationEngine
                engine = CorrelationEngine()
                correlation_summary = await engine.get_social_correlation_summary()
                context["social_correlation"] = correlation_summary
            except Exception as e:
                context["correlation_error"] = str(e)

        # If asking about campaigns / impact / marketing
        if any(word in query_lower for word in ["campaign", "marketing", "impact", "initiative"]):
            try:
                campaigns = await Database.fetch("""
                    SELECT c.name, c.campaign_type, c.start_date, c.end_date, c.status, ft.symbol
                    FROM campaigns c
                    JOIN fan_tokens ft ON c.token_id = ft.id
                    ORDER BY c.start_date DESC LIMIT 5
                """)
                context["recent_campaigns"] = [dict(c) for c in campaigns]
            except Exception as e:
                context["campaigns_error"] = str(e)

        # If asking about specific token
        for word in query_lower.split():
            if len(word) >= 2 and word.upper() in ["CHZ", "BAR", "PSG", "JUV", "ATM", "ACM", "ASR", "CITY", "INTER", "NAP", "GAL", "OG", "MENGO"]:
                symbol = word.upper()
                try:
                    # Get token details
                    token = await Database.fetchrow(
                        "SELECT id, symbol, team, league FROM fan_tokens WHERE symbol = $1",
                        symbol
                    )
                    if token:
                        context["focused_token"] = dict(token)

                        # Get social metrics
                        social = await Database.fetchrow("""
                            SELECT tweet_count_24h, sentiment_score, engagement_total
                            FROM social_metrics WHERE token_id = $1
                            ORDER BY time DESC LIMIT 1
                        """, token["id"])
                        if social:
                            context["token_social"] = dict(social)

                        # Get correlation for this token
                        from services.correlation_engine import CorrelationEngine
                        engine = CorrelationEngine()
                        corr = await engine.analyze_social_price_correlation(token["id"], symbol, 14)
                        if corr:
                            context["token_correlation"] = corr
                except Exception as e:
                    context["token_detail_error"] = str(e)
                break

        # If asking about fixtures / matches / events
        if any(word in query_lower for word in ["match", "fixture", "game", "event", "upcoming"]):
            try:
                # Use the fixtures endpoint data
                from api.routes.live import get_live_fixtures
                fixtures = await get_live_fixtures()
                context["upcoming_fixtures"] = fixtures.get("fixtures", [])[:10]
            except Exception as e:
                context["fixtures_error"] = str(e)

        # If asking about recommendation / which token / campaign for
        if any(word in query_lower for word in ["recommend", "which", "should", "best", "opportunity"]):
            try:
                # Get tokens with positive social momentum
                momentum = await Database.fetch("""
                    SELECT ft.symbol, ft.team,
                           sm.tweet_count_24h, sm.sentiment_score,
                           tma.price_change_24h
                    FROM fan_tokens ft
                    LEFT JOIN LATERAL (
                        SELECT * FROM social_metrics WHERE token_id = ft.id ORDER BY time DESC LIMIT 1
                    ) sm ON true
                    LEFT JOIN LATERAL (
                        SELECT * FROM token_metrics_aggregated WHERE token_id = ft.id ORDER BY time DESC LIMIT 1
                    ) tma ON true
                    WHERE ft.is_active = true
                    ORDER BY sm.tweet_count_24h DESC NULLS LAST
                    LIMIT 10
                """)
                context["momentum_tokens"] = [dict(m) for m in momentum]
            except Exception as e:
                context["momentum_error"] = str(e)

        return context

    async def _match_prebuilt_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Check if query matches any pre-built query patterns"""
        query_lower = query.lower()

        prebuilt_query = """
            SELECT name, sql_template, response_template, chart_type
            FROM prebuilt_queries
            WHERE is_active = true
        """
        prebuilts = await Database.fetch(prebuilt_query)

        for pb in prebuilts:
            # Check trigger patterns (stored as TEXT[])
            patterns_query = """
                SELECT trigger_patterns FROM prebuilt_queries WHERE name = $1
            """
            patterns = await Database.fetchval(patterns_query, pb["name"])
            if patterns:
                for pattern in patterns:
                    if pattern.lower() in query_lower:
                        # Execute the pre-built query
                        try:
                            result = await Database.fetch(pb["sql_template"])
                            return {
                                "name": pb["name"],
                                "response_template": pb["response_template"],
                                "chart_type": pb["chart_type"],
                                "data": [dict(r) for r in result],
                            }
                        except Exception as e:
                            pass  # Fall through to AI response

        return None

    async def chat(self, message: str, session_id: str) -> Dict[str, Any]:
        """Process a chat message and return AI response"""
        import logging
        logger = logging.getLogger(__name__)

        start_time = time.time()

        # Get context data with error handling
        try:
            context = await self.get_context_data(message)
        except Exception as e:
            logger.error(f"Error getting context data: {e}")
            context = {"error": str(e)}

        # Build messages for Claude
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Context data:
{json.dumps(context, indent=2, default=str)}

User question: {message}

Please answer based on the data provided. Be specific with numbers and percentages."""
            }
        ]

        # Check API key
        if not self.api_key:
            raise HTTPException(
                status_code=500,
                detail="OpenRouter API key not configured"
            )

        # Call OpenRouter API
        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://chiliz.com",
                        "X-Title": "Chiliz Marketing Intelligence",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": openrouter_config.max_tokens,
                        "temperature": openrouter_config.temperature,
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"OpenRouter API error: {resp.status} - {error_text}")
                        raise HTTPException(
                            status_code=500,
                            detail=f"AI service error: {error_text[:200]}"
                        )

                    data = await resp.json()
                    response_text = data["choices"][0]["message"]["content"]
                    tokens_used = data.get("usage", {}).get("total_tokens", 0)

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error calling OpenRouter: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to connect to AI service: {str(e)}")

        response_time = int((time.time() - start_time) * 1000)

        # Save conversation to database (non-blocking, ignore errors)
        try:
            await self._save_conversation(session_id, "user", message)
            await self._save_conversation(
                session_id, "assistant", response_text,
                tokens_used=tokens_used,
                response_time=response_time,
                context_data=context
            )
        except Exception as e:
            logger.warning(f"Failed to save conversation: {e}")

        # Log analytics (non-blocking, ignore errors)
        try:
            await self._log_analytics(message, response_text, response_time)
        except Exception as e:
            logger.warning(f"Failed to log analytics: {e}")

        return {
            "response": response_text,
            "data": context.get("prebuilt_result", {}).get("data"),
            "chart_type": context.get("prebuilt_result", {}).get("chart_type"),
        }

    async def _save_conversation(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens_used: int = None,
        response_time: int = None,
        context_data: Dict = None
    ):
        """Save conversation message to database"""
        query = """
            INSERT INTO conversations
            (session_id, role, content, tokens_used, model_used, response_time_ms, context_data)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        await Database.execute(
            query,
            uuid.UUID(session_id),
            role,
            content,
            tokens_used,
            self.model if role == "assistant" else None,
            response_time,
            json.dumps(context_data) if context_data else None,
        )

    async def _log_analytics(self, query: str, response: str, response_time: int):
        """Log query analytics for improving the assistant"""
        analytics_query = """
            INSERT INTO query_analytics
            (natural_language_query, execution_time_ms, was_successful)
            VALUES ($1, $2, $3)
        """
        await Database.execute(analytics_query, query, response_time, True)


# Initialize assistant
assistant = AIAssistant()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the AI Management Assistant
    Ask questions about fan token performance, health, liquidity, etc.
    """
    session_id = request.session_id or str(uuid.uuid4())

    result = await assistant.chat(request.message, session_id)

    return ChatResponse(
        response=result["response"],
        session_id=session_id,
        data=result.get("data"),
        chart_type=result.get("chart_type"),
    )


@router.get("/suggested-questions")
async def get_suggested_questions():
    """Get suggested questions for executives"""
    return {
        "suggestions": [
            {
                "category": "Portfolio Overview",
                "questions": [
                    "How is the portfolio performing today?",
                    "Which tokens need attention?",
                    "What's our total market cap?",
                ]
            },
            {
                "category": "Performance",
                "questions": [
                    "Who are the top performers this week?",
                    "Which tokens are underperforming?",
                    "How is BAR doing compared to last month?",
                ]
            },
            {
                "category": "Liquidity",
                "questions": [
                    "Which tokens have the best liquidity?",
                    "Can we execute a $50k trade on PSG?",
                    "What's the slippage for large CHZ trades?",
                ]
            },
            {
                "category": "Community",
                "questions": [
                    "Which tokens are growing their holder base?",
                    "Are there any concerning holder distributions?",
                    "What's the community sentiment around JUV?",
                ]
            },
            {
                "category": "Alerts",
                "questions": [
                    "Are there any active alerts?",
                    "What signals should I be aware of?",
                    "Any unusual activity today?",
                ]
            },
        ]
    }


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get conversation history for a session"""
    query = """
        SELECT role, content, created_at
        FROM conversations
        WHERE session_id = $1
        ORDER BY created_at ASC
    """
    rows = await Database.fetch(query, uuid.UUID(session_id))

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["created_at"].isoformat(),
            }
            for row in rows
        ]
    }
