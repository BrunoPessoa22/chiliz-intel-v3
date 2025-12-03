"""
Chiliz Marketing Intelligence v3.0 - Main Runner
Runs all services concurrently including whale tracking
"""
import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.database import Database, init_db
from services.price_collector import run_collector as run_price_collector
from services.spread_monitor import run_monitor as run_spread_monitor
from services.liquidity_analyzer import run_analyzer as run_liquidity_analyzer
from services.holder_tracker import run_tracker as run_holder_tracker
from services.social_tracker import run_tracker as run_social_tracker
from services.aggregator import run_aggregator
from services.correlation_engine import run_engine as run_correlation_engine
from services.health_scorer import run_scorer as run_health_scorer
from services.cex_whale_tracker import start_cex_tracking
from services.social_signal_tracker import start_social_tracking

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_dex_tracker_safe():
    """Run DEX tracker with error handling"""
    try:
        from services.dex_whale_tracker import start_dex_tracking
        await start_dex_tracking()
    except ImportError:
        logger.warning("DEX tracker not available (missing web3)")
    except Exception as e:
        logger.error(f"DEX tracker error: {e}")


async def run_all_services():
    """Run all data collection services concurrently"""
    logger.info("=" * 60)
    logger.info("CHILIZ MARKETING INTELLIGENCE v3.0")
    logger.info("With Real-Time Whale Tracking (11 CEXs + DEX)")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

    # Create tasks for all services
    tasks = [
        # Original services
        asyncio.create_task(run_price_collector(), name="price_collector"),
        asyncio.create_task(run_spread_monitor(), name="spread_monitor"),
        asyncio.create_task(run_liquidity_analyzer(), name="liquidity_analyzer"),
        asyncio.create_task(run_holder_tracker(), name="holder_tracker"),
        asyncio.create_task(run_social_tracker(), name="social_tracker"),
        asyncio.create_task(run_aggregator(), name="aggregator"),
        asyncio.create_task(run_correlation_engine(), name="correlation_engine"),
        asyncio.create_task(run_health_scorer(), name="health_scorer"),
        # NEW: Real-time whale tracking
        asyncio.create_task(start_cex_tracking(), name="cex_whale_tracker"),
        asyncio.create_task(start_social_tracking(), name="social_signal_tracker"),
        asyncio.create_task(run_dex_tracker_safe(), name="dex_whale_tracker"),
    ]

    logger.info(f"Started {len(tasks)} services (including whale tracking)")

    # Run until cancelled
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Shutting down services...")
        for task in tasks:
            task.cancel()
        await Database.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(run_all_services())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
