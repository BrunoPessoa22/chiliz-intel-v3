"""
Chiliz Marketing Intelligence v3.0 - FastAPI Backend
Executive-focused API with AI Assistant
Updated: 2025-12-03 - X/Twitter Bearer Token configured
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.database import Database, init_db
from services.live_data import cleanup_live_service
from api.routes import tokens, executive, assistant, alerts, live, campaigns, whales, signals, recommendations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Chiliz Marketing Intelligence v3.0")
    try:
        await Database.get_pool()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        logger.warning("Starting without database connection - will retry on requests")

    yield

    # Shutdown
    try:
        await cleanup_live_service()
        await Database.close()
        logger.info("Cleanup complete")
    except Exception:
        pass


app = FastAPI(
    title="Chiliz Marketing Intelligence API",
    description="Executive-focused API for fan token market analysis",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tokens.router, prefix="/api/tokens", tags=["Tokens"])
app.include_router(executive.router, prefix="/api/executive", tags=["Executive"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["AI Assistant"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])
app.include_router(live.router, prefix="/api/live", tags=["Live Data"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(whales.router, prefix="/api/whales", tags=["Whale Tracking"])
app.include_router(signals.router, prefix="/api/signals", tags=["Social Signals"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["AI Recommendations"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Chiliz Marketing Intelligence",
        "version": "3.0.0",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/init-db")
async def initialize_database():
    """Initialize database with schema and seed data"""
    try:
        await init_db()
        return {"status": "success", "message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/health")
async def health_check():
    """Health check endpoint - always returns 200 so Railway doesn't kill the service"""
    db_status = "unknown"
    try:
        # Check database connection
        result = await Database.fetchval("SELECT 1")
        db_status = "healthy" if result == 1 else "unhealthy"
    except Exception as e:
        db_status = f"disconnected: {str(e)[:50]}"

    # Always return 200 - Railway health check needs this
    return JSONResponse(
        status_code=200,
        content={
            "status": "operational",
            "database": db_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.post("/api/run-aggregation")
async def run_aggregation():
    """Manually trigger aggregation and health scoring"""
    from services.aggregator import MetricsAggregator
    from services.health_scorer import HealthScorer

    try:
        # Run aggregation
        aggregator = MetricsAggregator()
        agg_count = await aggregator.aggregate_all()

        # Run health scoring
        scorer = HealthScorer()
        health_count = await scorer.score_all_tokens()

        return {
            "status": "success",
            "aggregated_tokens": agg_count,
            "health_scored_tokens": health_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Manual aggregation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/run-correlation")
async def run_correlation():
    """Manually trigger correlation analysis"""
    from services.correlation_engine import CorrelationEngine

    try:
        engine = CorrelationEngine()
        count = await engine.analyze_all_tokens()

        return {
            "status": "success",
            "analyzed_tokens": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Correlation analysis failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/collect-data")
async def collect_data():
    """Manually trigger hourly data collection (market + social)"""
    from services.historical_collector import run_hourly_collection

    try:
        await run_hourly_collection()
        return {
            "status": "success",
            "message": "Data collection completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/backfill")
async def backfill_data(days: int = Query(default=30, ge=1, le=730)):
    """
    Backfill historical market data.
    With CoinGecko Pro API, supports up to 730 days (2 years).
    Free API limited to 90 days.
    """
    from services.historical_collector import run_backfill

    try:
        await run_backfill(days)
        return {
            "status": "success",
            "message": f"Backfilled {days} days of historical data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/collect-social")
async def collect_social_signals():
    """
    Manually trigger social signal collection from X/Twitter.
    Fetches tweets mentioning CHZ and fan tokens.
    """
    from services.social_signal_tracker import collect_signals_once

    try:
        count = await collect_signals_once()
        return {
            "status": "success",
            "signals_collected": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Social collection failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.get("/api/debug/twitter")
async def debug_twitter():
    """
    Debug Twitter API connection.
    Tests if the bearer token is working.
    """
    import aiohttp
    from urllib.parse import unquote
    from config.settings import x_api_config
    from services.database import get_all_tokens

    token = x_api_config.bearer_token
    token_present = bool(token)
    token_length = len(token) if token else 0

    # Decode if URL encoded
    if token and '%' in token:
        token = unquote(token)

    result = {
        "token_present": token_present,
        "token_length": token_length,
        "token_preview": f"{token[:20]}...{token[-10:]}" if token and len(token) > 30 else "too_short",
        "search_queries_count": len(x_api_config.search_queries),
        "search_query_tokens": list(x_api_config.search_queries.keys())[:10],
    }

    # Check which DB tokens have search queries
    try:
        db_tokens = await get_all_tokens()
        db_symbols = [t["symbol"] for t in db_tokens]
        matched = [s for s in db_symbols if s in x_api_config.search_queries]
        result["db_tokens_count"] = len(db_tokens)
        result["db_tokens_with_queries"] = len(matched)
        result["matched_tokens_sample"] = matched[:5]
    except Exception as e:
        result["db_error"] = str(e)

    if token:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {token}"}
                url = "https://api.twitter.com/2/tweets/search/recent"
                params = {"query": "chiliz", "max_results": 10}
                async with session.get(url, params=params, headers=headers) as resp:
                    result["api_status"] = resp.status
                    data = await resp.json()
                    if resp.status == 200:
                        result["tweets_found"] = len(data.get("data", []))
                        result["success"] = True
                    else:
                        result["error"] = data
                        result["success"] = False
        except Exception as e:
            result["exception"] = str(e)
            result["success"] = False

    return result


@app.get("/api/debug/collect-chz")
async def debug_collect_chz():
    """
    Debug endpoint to collect just CHZ signals directly.
    Bypasses database token lookup for debugging.
    """
    import aiohttp
    from urllib.parse import unquote
    from config.settings import x_api_config

    result = {"steps": []}

    # Get token
    token = x_api_config.bearer_token
    if '%' in token:
        token = unquote(token)

    result["token_length"] = len(token)

    try:
        # Direct API call without using tracker
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            url = "https://api.twitter.com/2/tweets/search/recent"
            params = {
                "query": "chiliz -is:retweet lang:en",
                "max_results": 10,
                "tweet.fields": "created_at,public_metrics,author_id,text",
                "expansions": "author_id",
                "user.fields": "public_metrics,username,name",
            }

            result["request_params"] = params
            result["steps"].append("Making direct API call")

            async with session.get(url, params=params, headers=headers) as resp:
                result["api_status"] = resp.status
                data = await resp.json()

                if resp.status == 200:
                    tweets = data.get("data", [])
                    result["tweets_found"] = len(tweets)
                    if tweets:
                        result["sample_tweet"] = {
                            "id": tweets[0].get("id"),
                            "text": tweets[0].get("text", "")[:100],
                        }
                    result["success"] = True
                else:
                    result["error_response"] = data
                    result["success"] = False

    except Exception as e:
        import traceback
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        result["success"] = False

    return result


@app.get("/api/debug/correlation-data")
async def debug_correlation_data():
    """
    Debug endpoint to check data availability for correlation analysis.
    Shows counts of market and social data by token.
    """
    from services.database import Database

    try:
        # Check market data
        market_query = """
            SELECT ft.symbol, COUNT(*) as market_hours
            FROM token_metrics_aggregated tma
            JOIN fan_tokens ft ON tma.token_id = ft.id
            WHERE tma.time > NOW() - INTERVAL '14 days'
            GROUP BY ft.symbol
            ORDER BY market_hours DESC
            LIMIT 20
        """
        market_data = await Database.fetch(market_query)

        # Check social metrics data
        social_query = """
            SELECT ft.symbol, COUNT(*) as social_hours
            FROM social_metrics sm
            JOIN fan_tokens ft ON sm.token_id = ft.id
            WHERE sm.time > NOW() - INTERVAL '14 days'
            GROUP BY ft.symbol
            ORDER BY social_hours DESC
            LIMIT 20
        """
        social_data = await Database.fetch(social_query)

        # Check aligned data (both exist for same hour)
        aligned_query = """
            SELECT ft.symbol, COUNT(*) as aligned_hours
            FROM token_metrics_aggregated tma
            JOIN fan_tokens ft ON tma.token_id = ft.id
            JOIN social_metrics sm ON sm.token_id = tma.token_id
                AND date_trunc('hour', sm.time) = date_trunc('hour', tma.time)
            WHERE tma.time > NOW() - INTERVAL '14 days'
            GROUP BY ft.symbol
            ORDER BY aligned_hours DESC
            LIMIT 20
        """
        aligned_data = await Database.fetch(aligned_query)

        return {
            "market_data": [dict(r) for r in market_data],
            "social_data": [dict(r) for r in social_data],
            "aligned_data": [dict(r) for r in aligned_data],
            "min_data_points_needed": 5,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.post("/api/aggregate-social")
async def aggregate_social_metrics():
    """
    Aggregate social_signals into social_metrics table.
    This is needed for the correlation engine to work.
    """
    from services.database import Database

    try:
        # Aggregate social signals by token and hour
        # Schema: time, token_id, tweet_count_24h, mention_count_24h, engagement_total,
        #         sentiment_score, positive_count, negative_count, neutral_count, influencer_mentions
        query = """
            INSERT INTO social_metrics (
                time, token_id, tweet_count_24h, mention_count_24h,
                engagement_total, sentiment_score, influencer_mentions
            )
            SELECT
                date_trunc('hour', ss.time) as hour,
                ss.token_id,
                COUNT(*) as tweet_count,
                COUNT(*) as mention_count,
                SUM(ss.engagement) as engagement,
                AVG(ss.sentiment_score) as sentiment,
                SUM(CASE WHEN ss.is_influencer THEN 1 ELSE 0 END) as influencer_mentions
            FROM social_signals ss
            WHERE ss.time > NOW() - INTERVAL '7 days'
            GROUP BY date_trunc('hour', ss.time), ss.token_id
            ON CONFLICT (time, token_id) DO UPDATE SET
                tweet_count_24h = EXCLUDED.tweet_count_24h,
                mention_count_24h = EXCLUDED.mention_count_24h,
                engagement_total = EXCLUDED.engagement_total,
                sentiment_score = EXCLUDED.sentiment_score,
                influencer_mentions = EXCLUDED.influencer_mentions
        """

        await Database.execute(query)

        # Count aggregated rows
        count = await Database.fetchval(
            "SELECT COUNT(*) FROM social_metrics WHERE time > NOW() - INTERVAL '7 days'"
        )

        return {
            "status": "success",
            "aggregated_rows": count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Social aggregation failed: {e}")
        import traceback
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e), "traceback": traceback.format_exc()}
        )


@app.get("/api/exchanges")
async def get_tracked_exchanges():
    """
    Get list of all exchanges being tracked for whale activity.
    """
    from services.cex_whale_tracker import TRACKED_SYMBOLS

    exchanges = []
    for exchange, pairs in TRACKED_SYMBOLS.items():
        exchanges.append({
            "name": exchange,
            "pairs_count": len(pairs),
            "pairs": pairs[:5],  # Show first 5 as sample
            "status": "active"
        })

    return {
        "exchanges": exchanges,
        "total_exchanges": len(exchanges),
        "description": "Real-time whale tracking across all major CEXs listing fan tokens",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
