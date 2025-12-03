"""
PILLAR 3: Holder Data Tracker
Tracks on-chain holder metrics from Chiliz Chain
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import chiliz_chain_config
from services.database import Database, get_token_id, get_all_tokens

logger = logging.getLogger(__name__)


# Chiliz Chain Block Explorer API (similar to Etherscan)
CHILIZ_EXPLORER_API = "https://explorer.chiliz.com/api"


class HolderTracker:
    """Tracks token holder metrics on Chiliz Chain"""

    def __init__(self):
        self.rpc_url = chiliz_chain_config.rpc_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_holder_count(self, contract_address: str) -> Optional[int]:
        """
        Fetch holder count for a token contract.
        Uses Chiliz Chain explorer API.
        """
        if not contract_address or contract_address == "0x...":
            return None

        try:
            # Try to get token holder count from explorer
            url = f"{CHILIZ_EXPLORER_API}"
            params = {
                "module": "token",
                "action": "getTokenHolders",
                "contractaddress": contract_address,
                "page": 1,
                "offset": 1,
            }

            async with self.session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Extract holder count from response
                    if data.get("status") == "1":
                        return len(data.get("result", []))
                return None
        except Exception as e:
            logger.debug(f"Error fetching holder count: {e}")
            return None

    async def fetch_holder_distribution(self, contract_address: str) -> Optional[Dict[str, Any]]:
        """
        Fetch holder distribution data.
        Returns top holder percentages and wallet size distribution.
        """
        if not contract_address or contract_address == "0x...":
            return None

        try:
            # Fetch top holders
            url = f"{CHILIZ_EXPLORER_API}"
            params = {
                "module": "token",
                "action": "getTokenHolders",
                "contractaddress": contract_address,
                "page": 1,
                "offset": 100,  # Top 100 holders
            }

            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                if data.get("status") != "1":
                    return None

                holders = data.get("result", [])
                if not holders:
                    return None

                # Calculate distribution metrics
                total_balance = sum(float(h.get("value", 0)) for h in holders)

                # Top holder percentages
                top_10 = sum(float(h.get("value", 0)) for h in holders[:10])
                top_50 = sum(float(h.get("value", 0)) for h in holders[:50])
                top_100 = sum(float(h.get("value", 0)) for h in holders[:100])

                # Wallet size distribution (by percentage of total supply)
                wallets_micro = 0   # < 0.01%
                wallets_small = 0   # 0.01% - 0.1%
                wallets_medium = 0  # 0.1% - 1%
                wallets_large = 0   # 1% - 5%
                wallets_whale = 0   # > 5%

                for holder in holders:
                    balance = float(holder.get("value", 0))
                    pct = (balance / total_balance * 100) if total_balance > 0 else 0

                    if pct < 0.01:
                        wallets_micro += 1
                    elif pct < 0.1:
                        wallets_small += 1
                    elif pct < 1:
                        wallets_medium += 1
                    elif pct < 5:
                        wallets_large += 1
                    else:
                        wallets_whale += 1

                return {
                    "top_10_percentage": (top_10 / total_balance) if total_balance > 0 else 0,
                    "top_50_percentage": (top_50 / total_balance) if total_balance > 0 else 0,
                    "top_100_percentage": (top_100 / total_balance) if total_balance > 0 else 0,
                    "wallets_micro": wallets_micro,
                    "wallets_small": wallets_small,
                    "wallets_medium": wallets_medium,
                    "wallets_large": wallets_large,
                    "wallets_whale": wallets_whale,
                }

        except Exception as e:
            logger.error(f"Error fetching holder distribution: {e}")
            return None

    def calculate_gini_coefficient(self, balances: List[float]) -> float:
        """
        Calculate Gini coefficient for holder distribution.
        0 = perfect equality, 1 = perfect inequality
        """
        if not balances or len(balances) < 2:
            return 0

        sorted_balances = sorted(balances)
        n = len(sorted_balances)
        cumulative = 0
        for i, balance in enumerate(sorted_balances):
            cumulative += (n - i) * balance

        total = sum(sorted_balances)
        if total == 0:
            return 0

        gini = (2 * cumulative) / (n * total) - (n + 1) / n
        return max(0, min(1, gini))  # Clamp to [0, 1]

    async def get_previous_holder_count(self, token_id: int, days_ago: int = 1) -> Optional[int]:
        """Get holder count from X days ago for calculating change"""
        query = """
            SELECT total_holders FROM holder_snapshots
            WHERE token_id = $1 AND time < NOW() - INTERVAL '1 day' * $2
            ORDER BY time DESC LIMIT 1
        """
        return await Database.fetchval(query, token_id, days_ago)

    async def collect_holder_data(self, token: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Collect holder data for a single token"""
        token_id = await get_token_id(token["symbol"])
        if not token_id:
            return None

        # For now, we'll use mock data since Chiliz Chain explorer API access varies
        # In production, this would fetch real on-chain data
        now = datetime.now(timezone.utc)

        # Get previous holder counts for change calculation
        prev_24h = await self.get_previous_holder_count(token_id, 1)
        prev_7d = await self.get_previous_holder_count(token_id, 7)

        # Mock holder data (replace with real API calls in production)
        # Real implementation would use contract_address from chiliz_chain_config
        total_holders = 10000 + hash(token["symbol"]) % 50000  # Deterministic mock

        holder_change_24h = (total_holders - prev_24h) if prev_24h else None
        holder_change_7d = (total_holders - prev_7d) if prev_7d else None

        return {
            "time": now,
            "token_id": token_id,
            "total_holders": total_holders,
            "holder_change_24h": holder_change_24h,
            "holder_change_7d": holder_change_7d,
            "top_10_percentage": 0.35,  # Mock: 35% held by top 10
            "top_50_percentage": 0.55,
            "top_100_percentage": 0.65,
            "wallets_micro": 5000,
            "wallets_small": 3000,
            "wallets_medium": 1500,
            "wallets_large": 400,
            "wallets_whale": 100,
            "gini_coefficient": 0.72,
        }

    async def collect_all(self) -> int:
        """Collect holder data for all tokens"""
        tokens = await get_all_tokens()
        all_data = []

        for token in tokens:
            data = await self.collect_holder_data(token)
            if data:
                all_data.append(data)

        if all_data:
            await self._insert_holder_data(all_data)

        logger.info(f"Collected {len(all_data)} holder records")
        return len(all_data)

    async def _insert_holder_data(self, data: List[Dict[str, Any]]):
        """Batch insert holder data"""
        query = """
            INSERT INTO holder_snapshots
            (time, token_id, total_holders, holder_change_24h, holder_change_7d,
             top_10_percentage, top_50_percentage, top_100_percentage,
             wallets_micro, wallets_small, wallets_medium, wallets_large, wallets_whale,
             gini_coefficient)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (time, token_id) DO UPDATE SET
                total_holders = EXCLUDED.total_holders,
                holder_change_24h = EXCLUDED.holder_change_24h,
                holder_change_7d = EXCLUDED.holder_change_7d
        """

        args = [
            (
                d["time"], d["token_id"], d["total_holders"], d["holder_change_24h"],
                d["holder_change_7d"], d["top_10_percentage"], d["top_50_percentage"],
                d["top_100_percentage"], d["wallets_micro"], d["wallets_small"],
                d["wallets_medium"], d["wallets_large"], d["wallets_whale"],
                d["gini_coefficient"]
            )
            for d in data
        ]

        await Database.executemany(query, args)


async def run_tracker():
    """Main tracking loop"""
    from config.settings import COLLECTION_INTERVALS

    interval = COLLECTION_INTERVALS["holders"]
    logger.info(f"Starting holder tracker (interval: {interval}s)")

    while True:
        try:
            async with HolderTracker() as tracker:
                count = await tracker.collect_all()
                logger.info(f"Holder tracking complete: {count} records")
        except Exception as e:
            logger.error(f"Holder tracking error: {e}")

        await asyncio.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_tracker())
