"""
Chiliz Marketing Intelligence v3.0 - Background Worker
Runs whale tracking and social signal collection as background processes
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


async def run_whale_tracker():
    """Run CEX whale tracker"""
    from services.cex_whale_tracker import start_cex_tracking, stop_cex_tracking

    logger.info("Starting CEX Whale Tracker worker...")

    try:
        await start_cex_tracking()
    except asyncio.CancelledError:
        logger.info("Whale tracker cancelled, shutting down...")
        await stop_cex_tracking()
    except Exception as e:
        logger.error(f"Whale tracker error: {e}")
        raise


async def run_dex_tracker():
    """Run DEX whale tracker"""
    from services.dex_whale_tracker import start_dex_tracking, stop_dex_tracking

    logger.info("Starting DEX Whale Tracker worker...")

    try:
        await start_dex_tracking()
    except asyncio.CancelledError:
        logger.info("DEX tracker cancelled, shutting down...")
        await stop_dex_tracking()
    except Exception as e:
        logger.error(f"DEX tracker error: {e}")


async def run_social_tracker():
    """Run social signal tracker (every 5 minutes)"""
    from services.social_signal_tracker import collect_signals_once

    logger.info("Starting Social Signal Tracker worker...")

    while not shutdown_event.is_set():
        try:
            count = await collect_signals_once()
            logger.info(f"Social collection complete: {count} signals")
        except Exception as e:
            logger.error(f"Social collection error: {e}")

        # Wait 5 minutes before next collection
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=300)
            break  # Shutdown requested
        except asyncio.TimeoutError:
            pass  # Continue loop


async def run_data_aggregation():
    """Run data aggregation and health scoring (every 5 minutes)"""
    from services.aggregator import MetricsAggregator
    from services.health_scorer import HealthScorer

    logger.info("Starting Data Aggregation worker...")

    while not shutdown_event.is_set():
        try:
            aggregator = MetricsAggregator()
            agg_count = await aggregator.aggregate_all()

            scorer = HealthScorer()
            health_count = await scorer.score_all_tokens()

            logger.info(f"Aggregation complete: {agg_count} tokens, {health_count} health scores")
        except Exception as e:
            logger.error(f"Aggregation error: {e}")

        # Wait 5 minutes
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=300)
            break
        except asyncio.TimeoutError:
            pass


async def run_lunarcrush_tracker():
    """Run LunarCrush social intelligence collection (every 15 minutes)"""
    from services.lunarcrush_tracker import collect_lunarcrush_metrics
    from config.settings import lunarcrush_config

    if not lunarcrush_config.api_key:
        logger.warning("LunarCrush API key not configured, skipping tracker")
        return

    logger.info("Starting LunarCrush Tracker worker...")

    while not shutdown_event.is_set():
        try:
            count = await collect_lunarcrush_metrics()
            logger.info(f"LunarCrush collection complete: {count} tokens")
        except Exception as e:
            logger.error(f"LunarCrush collection error: {e}")

        # Wait 15 minutes (staying within free tier limits)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=900)
            break
        except asyncio.TimeoutError:
            pass


async def run_reddit_tracker():
    """Run Reddit community signal collection (every 30 minutes)"""
    from services.reddit_tracker import collect_reddit_signals
    from config.settings import reddit_config

    if not reddit_config.client_id:
        logger.warning("Reddit API not configured, skipping tracker")
        return

    logger.info("Starting Reddit Tracker worker...")

    while not shutdown_event.is_set():
        try:
            count = await collect_reddit_signals()
            logger.info(f"Reddit collection complete: {count} signals")
        except Exception as e:
            logger.error(f"Reddit collection error: {e}")

        # Wait 30 minutes
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=1800)
            break
        except asyncio.TimeoutError:
            pass


async def main():
    """Main worker entry point"""
    logger.info("=" * 60)
    logger.info("Chiliz Marketing Intelligence v3.0 - Worker Starting")
    logger.info(f"Start time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    # Initialize database connection
    from services.database import Database
    try:
        await Database.get_pool()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return

    # Create tasks for all workers
    tasks = [
        asyncio.create_task(run_whale_tracker(), name="whale_tracker"),
        asyncio.create_task(run_social_tracker(), name="social_tracker"),
        asyncio.create_task(run_data_aggregation(), name="aggregation"),
        asyncio.create_task(run_lunarcrush_tracker(), name="lunarcrush_tracker"),
        asyncio.create_task(run_reddit_tracker(), name="reddit_tracker"),
    ]

    # Optionally add DEX tracker if Chiliz RPC is available
    try:
        tasks.append(asyncio.create_task(run_dex_tracker(), name="dex_tracker"))
    except Exception as e:
        logger.warning(f"DEX tracker not available: {e}")

    logger.info(f"Started {len(tasks)} worker tasks")

    try:
        # Wait for all tasks or shutdown
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_EXCEPTION
        )

        # Check for exceptions
        for task in done:
            if task.exception():
                logger.error(f"Task {task.get_name()} failed: {task.exception()}")

    except asyncio.CancelledError:
        logger.info("Main worker cancelled")
    finally:
        # Cancel all pending tasks
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for cancellation to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        # Close database
        await Database.close()
        logger.info("Worker shutdown complete")


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {sig}, initiating shutdown...")
    shutdown_event.set()


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the worker
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker crashed: {e}")
        sys.exit(1)
