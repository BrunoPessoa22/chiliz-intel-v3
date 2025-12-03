"""
DEX Whale Tracker - Real-time whale swap tracking from Chiliz Chain
Monitors FanX DEX swaps via RPC subscription
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware

from config.settings import chiliz_chain_config
from services.database import Database, get_token_id

logger = logging.getLogger(__name__)

# Whale threshold in USD
WHALE_THRESHOLD_USD = 10_000

# FanX DEX Contracts on Chiliz Chain
FANX_FACTORY = "0xE2918AA38088878546c1A18F2F9b1BC83297fdD3"
FANX_ROUTER = "0x1918EbB39492C8b98865c5E53219c3f1AE79e76F"

# CHZ is the native token, wrapped as WCHZ
WCHZ_ADDRESS = "0x677F7e16C7Dd57be1D4C8aD1244883214953DC47"

# Known fan token addresses on Chiliz Chain
TOKEN_ADDRESSES = {
    "0x...bar": "BAR",  # FC Barcelona - actual address needed
    "0x...psg": "PSG",  # Paris Saint-Germain
    "0x...juv": "JUV",  # Juventus
    # Add more as we discover them
}

# ABI for UniswapV2-style Swap events (FanX uses similar)
SWAP_EVENT_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "name": "sender", "type": "address"},
        {"indexed": False, "name": "amount0In", "type": "uint256"},
        {"indexed": False, "name": "amount1In", "type": "uint256"},
        {"indexed": False, "name": "amount0Out", "type": "uint256"},
        {"indexed": False, "name": "amount1Out", "type": "uint256"},
        {"indexed": True, "name": "to", "type": "address"},
    ],
    "name": "Swap",
    "type": "event"
}

# Swap event signature
SWAP_TOPIC = Web3.keccak(text="Swap(address,uint256,uint256,uint256,uint256,address)").hex()


class ChilizChainClient:
    """Client for interacting with Chiliz Chain RPC"""

    def __init__(self, rpc_url: str = None):
        self.rpc_url = rpc_url or chiliz_chain_config.rpc_url
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        # Add PoA middleware for Chiliz Chain
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

    def is_connected(self) -> bool:
        """Check if connected to RPC"""
        try:
            return self.w3.is_connected()
        except:
            return False

    def get_latest_block(self) -> int:
        """Get latest block number"""
        return self.w3.eth.block_number

    async def get_swap_events(self, from_block: int, to_block: int) -> List[Dict]:
        """Get swap events from blocks"""
        try:
            # Create filter for Swap events
            filter_params = {
                'fromBlock': from_block,
                'toBlock': to_block,
                'topics': [SWAP_TOPIC]
            }

            logs = self.w3.eth.get_logs(filter_params)
            return [self._parse_swap_log(log) for log in logs]

        except Exception as e:
            logger.error(f"Error fetching swap events: {e}")
            return []

    def _parse_swap_log(self, log: Dict) -> Optional[Dict]:
        """Parse a swap event log"""
        try:
            # Decode event data
            data = log['data']
            topics = log['topics']

            # Sender is first indexed param
            sender = '0x' + topics[1].hex()[-40:]
            # Recipient is second indexed param
            to_address = '0x' + topics[2].hex()[-40:]

            # Decode non-indexed data (amounts)
            amounts = self.w3.codec.decode(
                ['uint256', 'uint256', 'uint256', 'uint256'],
                bytes.fromhex(data[2:])  # Remove 0x prefix
            )

            amount0_in, amount1_in, amount0_out, amount1_out = amounts

            return {
                'tx_hash': log['transactionHash'].hex(),
                'block_number': log['blockNumber'],
                'pool_address': log['address'],
                'sender': sender,
                'to_address': to_address,
                'amount0_in': amount0_in,
                'amount1_in': amount1_in,
                'amount0_out': amount0_out,
                'amount1_out': amount1_out,
            }

        except Exception as e:
            logger.error(f"Error parsing swap log: {e}")
            return None

    async def get_token_price_chz(self, token_address: str) -> float:
        """Get token price in CHZ from pool reserves"""
        # This would need to call getReserves on the pool
        # For now, return 1.0 and rely on external price data
        return 1.0


class DEXWhaleTracker:
    """Track whale swaps on FanX DEX"""

    def __init__(self):
        self.client = ChilizChainClient()
        self.recent_swaps: List[Dict] = []
        self.max_recent = 100
        self._running = False
        self._last_block = 0
        self._chz_price_usd = 0.08  # Default, should be updated

    async def update_chz_price(self):
        """Update CHZ price from database or API"""
        try:
            # Get latest CHZ price from price_volume_ticks
            row = await Database.fetchrow("""
                SELECT price FROM price_volume_ticks pvt
                JOIN fan_tokens ft ON pvt.token_id = ft.id
                WHERE ft.symbol = 'CHZ'
                ORDER BY pvt.time DESC LIMIT 1
            """)
            if row and row['price']:
                self._chz_price_usd = float(row['price'])
                logger.info(f"Updated CHZ price: ${self._chz_price_usd:.4f}")
        except Exception as e:
            logger.warning(f"Failed to update CHZ price: {e}")

    async def start(self):
        """Start monitoring DEX swaps"""
        logger.info("Starting DEX Whale Tracker for Chiliz Chain")

        if not self.client.is_connected():
            logger.error(f"Cannot connect to Chiliz Chain RPC at {self.client.rpc_url}")
            return

        self._running = True
        self._last_block = self.client.get_latest_block() - 100  # Start 100 blocks back

        logger.info(f"Connected to Chiliz Chain. Latest block: {self._last_block + 100}")

        # Update CHZ price periodically
        price_task = asyncio.create_task(self._price_update_loop())

        try:
            while self._running:
                await self._poll_new_blocks()
                await asyncio.sleep(3)  # Poll every 3 seconds (Chiliz has ~5s blocks)

        except Exception as e:
            logger.error(f"DEX tracker error: {e}")
        finally:
            price_task.cancel()

    async def _price_update_loop(self):
        """Update CHZ price every 5 minutes"""
        while self._running:
            await self.update_chz_price()
            await asyncio.sleep(300)

    async def _poll_new_blocks(self):
        """Poll for new blocks and process swap events"""
        try:
            current_block = self.client.get_latest_block()

            if current_block <= self._last_block:
                return

            # Process in chunks of 100 blocks
            from_block = self._last_block + 1
            to_block = min(current_block, from_block + 100)

            swaps = await self.client.get_swap_events(from_block, to_block)

            for swap in swaps:
                if swap:
                    await self._process_swap(swap)

            self._last_block = to_block

        except Exception as e:
            logger.error(f"Error polling blocks: {e}")

    async def _process_swap(self, swap: Dict):
        """Process a swap event and check if it's a whale trade"""
        try:
            # Determine which token was swapped
            # In UniswapV2 style: if amount0_in > 0, token0 was sold
            # We need to identify which token is CHZ and which is the fan token

            # For now, estimate value based on amounts and CHZ price
            total_amount = max(
                swap['amount0_in'] + swap['amount0_out'],
                swap['amount1_in'] + swap['amount1_out']
            ) / 1e18  # Assuming 18 decimals

            # Estimate USD value
            value_usd = total_amount * self._chz_price_usd

            if value_usd < WHALE_THRESHOLD_USD:
                return

            # Determine direction (buy/sell fan token)
            is_buy = swap['amount0_in'] > 0  # Simplified logic

            # Try to identify the token
            token_symbol = self._identify_token(swap['pool_address'])

            whale_swap = {
                'tx_hash': swap['tx_hash'],
                'block_number': swap['block_number'],
                'pool_address': swap['pool_address'],
                'from_address': swap['sender'],
                'to_address': swap['to_address'],
                'token_in': 'CHZ' if is_buy else (token_symbol or 'UNKNOWN'),
                'token_out': (token_symbol or 'UNKNOWN') if is_buy else 'CHZ',
                'amount_in': total_amount if is_buy else total_amount,
                'amount_out': total_amount,
                'value_usd': value_usd,
                'dex_name': 'FanX',
                'time': datetime.now(timezone.utc),
            }

            logger.info(
                f"🦈 DEX WHALE: {'BUY' if is_buy else 'SELL'} {token_symbol or 'Token'} "
                f"${value_usd:,.0f} on FanX - tx: {swap['tx_hash'][:16]}..."
            )

            # Add to memory cache
            self.recent_swaps.insert(0, whale_swap)
            if len(self.recent_swaps) > self.max_recent:
                self.recent_swaps = self.recent_swaps[:self.max_recent]

            # Save to database
            await self._save_swap(whale_swap, token_symbol)

        except Exception as e:
            logger.error(f"Error processing swap: {e}")

    def _identify_token(self, pool_address: str) -> Optional[str]:
        """Identify fan token from pool address"""
        # This would need a mapping of pool addresses to tokens
        # For now, return None
        return None

    async def _save_swap(self, swap: Dict, token_symbol: Optional[str]):
        """Save whale swap to database"""
        try:
            token_id = await get_token_id(token_symbol) if token_symbol else None

            query = """
                INSERT INTO dex_whale_swaps
                (time, token_id, tx_hash, block_number, from_address, to_address,
                 token_in, token_out, amount_in, amount_out, value_usd, dex_name, pool_address)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (tx_hash) DO NOTHING
            """

            await Database.execute(
                query,
                swap['time'],
                token_id,
                swap['tx_hash'],
                swap['block_number'],
                swap['from_address'],
                swap['to_address'],
                swap['token_in'],
                swap['token_out'],
                Decimal(str(swap['amount_in'])),
                Decimal(str(swap['amount_out'])),
                Decimal(str(swap['value_usd'])),
                swap['dex_name'],
                swap['pool_address'],
            )

        except Exception as e:
            logger.error(f"Error saving DEX swap: {e}")

    async def stop(self):
        """Stop the tracker"""
        logger.info("Stopping DEX Whale Tracker")
        self._running = False

    def get_recent_swaps(self, limit: int = 50) -> List[Dict]:
        """Get recent whale swaps from memory"""
        return self.recent_swaps[:limit]


# Singleton instance
_dex_tracker: Optional[DEXWhaleTracker] = None


async def get_dex_tracker() -> DEXWhaleTracker:
    """Get or create DEX tracker instance"""
    global _dex_tracker
    if _dex_tracker is None:
        _dex_tracker = DEXWhaleTracker()
    return _dex_tracker


async def start_dex_tracking():
    """Start DEX whale tracking"""
    tracker = await get_dex_tracker()
    await tracker.start()


async def stop_dex_tracking():
    """Stop DEX whale tracking"""
    global _dex_tracker
    if _dex_tracker:
        await _dex_tracker.stop()
        _dex_tracker = None


# API helper functions
async def get_recent_dex_swaps(
    limit: int = 50,
    token_symbol: Optional[str] = None,
    min_value: float = WHALE_THRESHOLD_USD
) -> List[Dict]:
    """Get recent DEX whale swaps from database"""

    conditions = ["value_usd >= $1"]
    params = [Decimal(str(min_value))]
    param_idx = 2

    if token_symbol:
        conditions.append(f"(token_in = ${param_idx} OR token_out = ${param_idx})")
        params.append(token_symbol)
        param_idx += 1

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            time, tx_hash, block_number, from_address, to_address,
            token_in, token_out, amount_in, amount_out, value_usd,
            dex_name, pool_address
        FROM dex_whale_swaps
        WHERE {where_clause}
        ORDER BY time DESC
        LIMIT {limit}
    """

    rows = await Database.fetch(query, *params)

    return [
        {
            'time': row['time'].isoformat(),
            'tx_hash': row['tx_hash'],
            'block_number': row['block_number'],
            'from_address': row['from_address'],
            'to_address': row['to_address'],
            'token_in': row['token_in'],
            'token_out': row['token_out'],
            'amount_in': float(row['amount_in']),
            'amount_out': float(row['amount_out']),
            'value_usd': float(row['value_usd']),
            'dex_name': row['dex_name'],
            'pool_address': row['pool_address'],
            'side': 'buy' if row['token_in'] == 'CHZ' else 'sell',
        }
        for row in rows
    ]


async def get_dex_volume_summary(hours: int = 24) -> Dict:
    """Get DEX volume summary"""

    query = """
        SELECT
            token_out as symbol,
            SUM(CASE WHEN token_in = 'CHZ' THEN value_usd ELSE 0 END) as buy_volume,
            SUM(CASE WHEN token_out = 'CHZ' THEN value_usd ELSE 0 END) as sell_volume,
            COUNT(*) as swap_count
        FROM dex_whale_swaps
        WHERE time > NOW() - INTERVAL '%s hours'
        GROUP BY token_out
        HAVING SUM(value_usd) > 0
        ORDER BY SUM(value_usd) DESC
    """ % hours

    rows = await Database.fetch(query)

    return {
        'period_hours': hours,
        'dex': 'FanX',
        'tokens': [
            {
                'symbol': row['symbol'],
                'buy_volume': float(row['buy_volume'] or 0),
                'sell_volume': float(row['sell_volume'] or 0),
                'total_volume': float((row['buy_volume'] or 0) + (row['sell_volume'] or 0)),
                'swap_count': row['swap_count'],
            }
            for row in rows
        ]
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_dex_tracking())
