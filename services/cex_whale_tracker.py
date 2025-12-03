"""
CEX Whale Tracker - Real-time whale transaction tracking from exchanges
Connects to Binance, OKX, HTX, KuCoin, Bybit, Gate.io, MEXC, Upbit, and Mercado Bitcoin WebSocket APIs
Comprehensive fan token coverage across all major exchanges including LATAM
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set
from decimal import Decimal

import aiohttp

from services.database import Database, get_token_id, get_exchange_id

logger = logging.getLogger(__name__)

# Whale threshold in USD
WHALE_THRESHOLD_USD = 10_000

# All CHZ and fan token trading pairs across all exchanges
TRACKED_SYMBOLS = {
    # Binance - Most comprehensive fan token listings
    'binance': [
        'CHZUSDT', 'CHZBTC', 'CHZBUSD', 'CHZEUR', 'CHZTRY',
        'BARUSDT', 'PSGUSDT', 'JUVUSDT', 'ATMAUSDT',
        'ACMUSDT', 'CITYUSDT', 'OGUSDT', 'LAZIOUSDT',
        'PORTOUSDT', 'SANTOSUSDT', 'ALPINEUSDT', 'ASRUSDT'
    ],
    # OKX
    'okx': [
        'CHZ-USDT', 'CHZ-USDC', 'CHZ-EUR',
        'BAR-USDT', 'PSG-USDT', 'JUV-USDT', 'ATM-USDT',
        'ACM-USDT', 'CITY-USDT', 'OG-USDT', 'LAZIO-USDT',
        'PORTO-USDT', 'SANTOS-USDT'
    ],
    # HTX (Huobi) - Strong fan token presence
    'htx': [
        'chzusdt', 'psgusdt', 'juvusdt', 'ogusdt',
        'atmusdt', 'argusdt', 'acmusdt', 'cityusdt',
        'barusdt', 'laziousdt', 'portousdt', 'santosusdt'
    ],
    # KuCoin
    'kucoin': [
        'CHZ-USDT', 'BAR-USDT', 'PSG-USDT', 'JUV-USDT',
        'CITY-USDT', 'ACM-USDT', 'ATM-USDT', 'OG-USDT'
    ],
    # Bybit
    'bybit': [
        'CHZUSDT', 'BARUSDT', 'PSGUSDT', 'JUVUSDT',
        'ACMUSDT', 'CITYUSDT', 'ATMUSDT'
    ],
    # Gate.io
    'gateio': [
        'CHZ_USDT', 'BAR_USDT', 'PSG_USDT', 'JUV_USDT',
        'ACM_USDT', 'CITY_USDT', 'ATM_USDT', 'OG_USDT',
        'LAZIO_USDT', 'PORTO_USDT', 'SANTOS_USDT', 'ALPINE_USDT'
    ],
    # MEXC
    'mexc': [
        'CHZUSDT', 'BARUSDT', 'PSGUSDT', 'JUVUSDT',
        'ACMUSDT', 'CITYUSDT', 'ATMUSDT', 'OGUSDT',
        'LAZIOUSDT', 'PORTOUSDT', 'SANTOSUSDT'
    ],
    # Upbit (Korean exchange - strong fan token volume)
    'upbit': [
        'CHZ-KRW', 'BAR-KRW', 'PSG-KRW', 'JUV-KRW',
        'ACM-KRW', 'CITY-KRW', 'ATM-KRW', 'AFC-KRW',
        'INTER-KRW', 'NAP-KRW'
    ],
    # Kraken
    'kraken': [
        'CHZUSD', 'CHZEUR'
    ],
    # Coinbase
    'coinbase': [
        'CHZ-USD', 'CHZ-EUR', 'CHZ-USDT'
    ],
    # Mercado Bitcoin (Brazil - LATAM's largest exchange)
    'mercadobitcoin': [
        'CHZ-BRL'
    ],
}

# Symbol to token mapping (comprehensive)
SYMBOL_MAP = {
    # CHZ variations
    'CHZ': 'CHZ', 'CHZUSDT': 'CHZ', 'CHZ-USDT': 'CHZ', 'CHZ-USDC': 'CHZ',
    'CHZBTC': 'CHZ', 'CHZBUSD': 'CHZ', 'CHZEUR': 'CHZ', 'CHZ-EUR': 'CHZ',
    'CHZTRY': 'CHZ', 'chzusdt': 'CHZ', 'CHZ_USDT': 'CHZ', 'CHZ-KRW': 'CHZ',
    'CHZUSD': 'CHZ', 'CHZ-USD': 'CHZ',
    # BAR variations
    'BAR': 'BAR', 'BARUSDT': 'BAR', 'BAR-USDT': 'BAR', 'barusdt': 'BAR',
    'BAR_USDT': 'BAR', 'BAR-KRW': 'BAR',
    # PSG variations
    'PSG': 'PSG', 'PSGUSDT': 'PSG', 'PSG-USDT': 'PSG', 'psgusdt': 'PSG',
    'PSG_USDT': 'PSG', 'PSG-KRW': 'PSG',
    # JUV variations
    'JUV': 'JUV', 'JUVUSDT': 'JUV', 'JUV-USDT': 'JUV', 'juvusdt': 'JUV',
    'JUV_USDT': 'JUV', 'JUV-KRW': 'JUV',
    # ATM variations
    'ATM': 'ATM', 'ATMAUSDT': 'ATM', 'ATM-USDT': 'ATM', 'atmusdt': 'ATM',
    'ATM_USDT': 'ATM', 'ATM-KRW': 'ATM', 'ATMUSDT': 'ATM',
    # ACM variations
    'ACM': 'ACM', 'ACMUSDT': 'ACM', 'ACM-USDT': 'ACM', 'acmusdt': 'ACM',
    'ACM_USDT': 'ACM', 'ACM-KRW': 'ACM',
    # CITY variations
    'CITY': 'CITY', 'CITYUSDT': 'CITY', 'CITY-USDT': 'CITY', 'cityusdt': 'CITY',
    'CITY_USDT': 'CITY', 'CITY-KRW': 'CITY',
    # OG variations
    'OG': 'OG', 'OGUSDT': 'OG', 'OG-USDT': 'OG', 'ogusdt': 'OG', 'OG_USDT': 'OG',
    # LAZIO variations
    'LAZIO': 'LAZIO', 'LAZIOUSDT': 'LAZIO', 'LAZIO-USDT': 'LAZIO',
    'laziousdt': 'LAZIO', 'LAZIO_USDT': 'LAZIO',
    # PORTO variations
    'PORTO': 'PORTO', 'PORTOUSDT': 'PORTO', 'PORTO-USDT': 'PORTO',
    'portousdt': 'PORTO', 'PORTO_USDT': 'PORTO',
    # SANTOS variations
    'SANTOS': 'SANTOS', 'SANTOSUSDT': 'SANTOS', 'SANTOS-USDT': 'SANTOS',
    'santosusdt': 'SANTOS', 'SANTOS_USDT': 'SANTOS',
    # ALPINE variations
    'ALPINE': 'ALPINE', 'ALPINEUSDT': 'ALPINE', 'ALPINE_USDT': 'ALPINE',
    # ASR (AS Roma)
    'ASR': 'ASR', 'ASRUSDT': 'ASR', 'ASR-USDT': 'ASR',
    # ARG (Argentina)
    'ARG': 'ARG', 'argusdt': 'ARG', 'ARGUSDT': 'ARG',
    # AFC (Arsenal)
    'AFC': 'AFC', 'AFC-KRW': 'AFC', 'AFC-USDT': 'AFC',
    # INTER (Inter Milan)
    'INTER': 'INTER', 'INTER-KRW': 'INTER', 'INTER-USDT': 'INTER',
    # NAP (Napoli)
    'NAP': 'NAP', 'NAP-KRW': 'NAP', 'NAP-USDT': 'NAP',
    # BRL pairs (Mercado Bitcoin)
    'CHZ-BRL': 'CHZ', 'CHZBRL': 'CHZ',
}


class BinanceWhaleTracker:
    """Track whale trades on Binance via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None

    def _get_stream_names(self) -> List[str]:
        """Get Binance stream names for trade data"""
        streams = []
        for symbol in TRACKED_SYMBOLS.get('binance', []):
            # aggTrade gives us aggregated trades
            streams.append(f"{symbol.lower()}@aggTrade")
        return streams

    async def connect(self):
        """Connect to Binance WebSocket"""
        streams = self._get_stream_names()
        if not streams:
            logger.warning("No Binance streams configured")
            return

        # Combined stream URL
        stream_path = "/".join(streams)
        url = f"wss://stream.binance.com:9443/stream?streams={stream_path}"

        logger.info(f"Connecting to Binance WebSocket with {len(streams)} streams")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True
                    logger.info("Connected to Binance WebSocket")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"Binance WS error: {ws.exception()}")
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            logger.info("Binance WS closed")
                            break

        except Exception as e:
            logger.error(f"Binance WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            # Combined stream format: {"stream": "chzusdt@aggTrade", "data": {...}}
            if 'data' in msg:
                trade = msg['data']
            else:
                trade = msg

            # Parse aggTrade format
            symbol = trade.get('s', '')  # Symbol
            price = float(trade.get('p', 0))  # Price
            quantity = float(trade.get('q', 0))  # Quantity
            is_buyer_maker = trade.get('m', False)  # True = sell (buyer is maker)
            trade_id = str(trade.get('a', ''))  # Aggregate trade ID

            # Calculate USD value
            value_usd = price * quantity

            # Check if whale trade
            if value_usd >= WHALE_THRESHOLD_USD:
                side = 'sell' if is_buyer_maker else 'buy'

                # Get token symbol from pair
                token_symbol = None
                for key, token in SYMBOL_MAP.items():
                    if symbol.upper().startswith(key) or symbol.upper() == key:
                        token_symbol = token
                        break

                if token_symbol:
                    whale_trade = {
                        'exchange': 'binance',
                        'symbol': token_symbol,
                        'pair': symbol,
                        'side': side,
                        'price': price,
                        'quantity': quantity,
                        'value_usd': value_usd,
                        'is_aggressive': not is_buyer_maker,  # Taker = aggressive
                        'trade_id': trade_id,
                        'time': datetime.now(timezone.utc),
                    }

                    await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing Binance trade: {e}")

    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self.ws:
            await self.ws.close()


class OKXWhaleTracker:
    """Track whale trades on OKX via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None

    async def connect(self):
        """Connect to OKX WebSocket"""
        logger.info("Connecting to OKX WebSocket")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True

                    # Subscribe to trade channels
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [
                            {"channel": "trades", "instId": pair}
                            for pair in TRACKED_SYMBOLS.get('okx', [])
                        ]
                    }
                    await ws.send_str(json.dumps(subscribe_msg))
                    logger.info("Subscribed to OKX trade channels")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"OKX WS error: {ws.exception()}")
                            break

        except Exception as e:
            logger.error(f"OKX WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            # Skip subscription confirmations
            if 'event' in msg:
                return

            if 'data' not in msg:
                return

            for trade in msg['data']:
                inst_id = trade.get('instId', '')  # e.g., CHZ-USDT
                price = float(trade.get('px', 0))
                quantity = float(trade.get('sz', 0))
                side = trade.get('side', '').lower()  # 'buy' or 'sell'
                trade_id = trade.get('tradeId', '')

                value_usd = price * quantity

                if value_usd >= WHALE_THRESHOLD_USD:
                    # Get token symbol
                    token_symbol = SYMBOL_MAP.get(inst_id)
                    if not token_symbol:
                        # Try parsing
                        base = inst_id.split('-')[0] if '-' in inst_id else inst_id
                        token_symbol = base

                    whale_trade = {
                        'exchange': 'okx',
                        'symbol': token_symbol,
                        'pair': inst_id,
                        'side': side,
                        'price': price,
                        'quantity': quantity,
                        'value_usd': value_usd,
                        'is_aggressive': True,  # OKX trades are taker trades
                        'trade_id': trade_id,
                        'time': datetime.now(timezone.utc),
                    }

                    await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing OKX trade: {e}")

    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self.ws:
            await self.ws.close()


class HTXWhaleTracker:
    """Track whale trades on HTX (Huobi) via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.ws_url = "wss://api.huobi.pro/ws"
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None

    async def connect(self):
        """Connect to HTX WebSocket"""
        logger.info("Connecting to HTX WebSocket")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True

                    # Subscribe to trade channels
                    for pair in TRACKED_SYMBOLS.get('htx', []):
                        subscribe_msg = {
                            "sub": f"market.{pair}.trade.detail",
                            "id": f"trade_{pair}"
                        }
                        await ws.send_str(json.dumps(subscribe_msg))

                    logger.info("Subscribed to HTX trade channels")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.BINARY:
                            # HTX sends gzip compressed data
                            import gzip
                            data = gzip.decompress(msg.data).decode('utf-8')
                            await self._handle_message(data)
                        elif msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"HTX WS error: {ws.exception()}")
                            break

        except Exception as e:
            logger.error(f"HTX WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            # Handle ping/pong
            if 'ping' in msg:
                pong = {"pong": msg['ping']}
                if self.ws:
                    await self.ws.send_str(json.dumps(pong))
                return

            if 'tick' not in msg or 'data' not in msg['tick']:
                return

            ch = msg.get('ch', '')  # e.g., market.chzusdt.trade.detail
            parts = ch.split('.')
            if len(parts) < 2:
                return

            pair = parts[1]  # e.g., chzusdt

            for trade in msg['tick']['data']:
                price = float(trade.get('price', 0))
                quantity = float(trade.get('amount', 0))
                direction = trade.get('direction', '')  # 'buy' or 'sell'
                trade_id = str(trade.get('tradeId', ''))

                value_usd = price * quantity

                if value_usd >= WHALE_THRESHOLD_USD:
                    token_symbol = SYMBOL_MAP.get(pair, pair.upper().replace('USDT', ''))

                    whale_trade = {
                        'exchange': 'htx',
                        'symbol': token_symbol,
                        'pair': pair,
                        'side': direction,
                        'price': price,
                        'quantity': quantity,
                        'value_usd': value_usd,
                        'is_aggressive': True,
                        'trade_id': trade_id,
                        'time': datetime.now(timezone.utc),
                    }

                    await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing HTX trade: {e}")

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()


class KuCoinWhaleTracker:
    """Track whale trades on KuCoin via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None

    async def _get_token(self):
        """Get KuCoin WebSocket token"""
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.kucoin.com/api/v1/bullet-public") as resp:
                data = await resp.json()
                if data.get('code') == '200000':
                    return data['data']['token'], data['data']['instanceServers'][0]['endpoint']
        return None, None

    async def connect(self):
        """Connect to KuCoin WebSocket"""
        logger.info("Connecting to KuCoin WebSocket")

        try:
            token, endpoint = await self._get_token()
            if not token:
                logger.error("Failed to get KuCoin WebSocket token")
                return

            ws_url = f"{endpoint}?token={token}"

            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True

                    # Subscribe to trade channels
                    for pair in TRACKED_SYMBOLS.get('kucoin', []):
                        subscribe_msg = {
                            "id": int(datetime.now().timestamp() * 1000),
                            "type": "subscribe",
                            "topic": f"/market/match:{pair}",
                            "privateChannel": False,
                            "response": True
                        }
                        await ws.send_str(json.dumps(subscribe_msg))

                    logger.info("Subscribed to KuCoin trade channels")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"KuCoin WS error: {ws.exception()}")
                            break

        except Exception as e:
            logger.error(f"KuCoin WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            if msg.get('type') == 'message' and 'data' in msg:
                trade = msg['data']
                symbol = trade.get('symbol', '')  # e.g., CHZ-USDT
                price = float(trade.get('price', 0))
                quantity = float(trade.get('size', 0))
                side = trade.get('side', '').lower()
                trade_id = trade.get('tradeId', '')

                value_usd = price * quantity

                if value_usd >= WHALE_THRESHOLD_USD:
                    token_symbol = SYMBOL_MAP.get(symbol)
                    if not token_symbol:
                        base = symbol.split('-')[0] if '-' in symbol else symbol
                        token_symbol = base

                    whale_trade = {
                        'exchange': 'kucoin',
                        'symbol': token_symbol,
                        'pair': symbol,
                        'side': side,
                        'price': price,
                        'quantity': quantity,
                        'value_usd': value_usd,
                        'is_aggressive': True,
                        'trade_id': trade_id,
                        'time': datetime.now(timezone.utc),
                    }

                    await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing KuCoin trade: {e}")

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()


class BybitWhaleTracker:
    """Track whale trades on Bybit via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.ws_url = "wss://stream.bybit.com/v5/public/spot"
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None

    async def connect(self):
        """Connect to Bybit WebSocket"""
        logger.info("Connecting to Bybit WebSocket")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True

                    # Subscribe to trade channels
                    args = [f"publicTrade.{pair}" for pair in TRACKED_SYMBOLS.get('bybit', [])]
                    subscribe_msg = {
                        "op": "subscribe",
                        "args": args
                    }
                    await ws.send_str(json.dumps(subscribe_msg))
                    logger.info("Subscribed to Bybit trade channels")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"Bybit WS error: {ws.exception()}")
                            break

        except Exception as e:
            logger.error(f"Bybit WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            if 'data' not in msg:
                return

            for trade in msg['data']:
                symbol = trade.get('s', '')  # e.g., CHZUSDT
                price = float(trade.get('p', 0))
                quantity = float(trade.get('v', 0))
                side = trade.get('S', '').lower()  # Buy or Sell
                trade_id = trade.get('i', '')

                value_usd = price * quantity

                if value_usd >= WHALE_THRESHOLD_USD:
                    token_symbol = SYMBOL_MAP.get(symbol)
                    if not token_symbol:
                        token_symbol = symbol.replace('USDT', '')

                    whale_trade = {
                        'exchange': 'bybit',
                        'symbol': token_symbol,
                        'pair': symbol,
                        'side': side.lower(),
                        'price': price,
                        'quantity': quantity,
                        'value_usd': value_usd,
                        'is_aggressive': True,
                        'trade_id': trade_id,
                        'time': datetime.now(timezone.utc),
                    }

                    await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing Bybit trade: {e}")

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()


class GateIOWhaleTracker:
    """Track whale trades on Gate.io via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.ws_url = "wss://api.gateio.ws/ws/v4/"
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None

    async def connect(self):
        """Connect to Gate.io WebSocket"""
        logger.info("Connecting to Gate.io WebSocket")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True

                    # Subscribe to trade channels
                    subscribe_msg = {
                        "time": int(datetime.now().timestamp()),
                        "channel": "spot.trades",
                        "event": "subscribe",
                        "payload": TRACKED_SYMBOLS.get('gateio', [])
                    }
                    await ws.send_str(json.dumps(subscribe_msg))
                    logger.info("Subscribed to Gate.io trade channels")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"Gate.io WS error: {ws.exception()}")
                            break

        except Exception as e:
            logger.error(f"Gate.io WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            if msg.get('event') != 'update' or 'result' not in msg:
                return

            trade = msg['result']
            symbol = trade.get('currency_pair', '')  # e.g., CHZ_USDT
            price = float(trade.get('price', 0))
            quantity = float(trade.get('amount', 0))
            side = trade.get('side', '').lower()
            trade_id = str(trade.get('id', ''))

            value_usd = price * quantity

            if value_usd >= WHALE_THRESHOLD_USD:
                token_symbol = SYMBOL_MAP.get(symbol)
                if not token_symbol:
                    base = symbol.split('_')[0] if '_' in symbol else symbol
                    token_symbol = base

                whale_trade = {
                    'exchange': 'gateio',
                    'symbol': token_symbol,
                    'pair': symbol,
                    'side': side,
                    'price': price,
                    'quantity': quantity,
                    'value_usd': value_usd,
                    'is_aggressive': True,
                    'trade_id': trade_id,
                    'time': datetime.now(timezone.utc),
                }

                await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing Gate.io trade: {e}")

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()


class MEXCWhaleTracker:
    """Track whale trades on MEXC via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.ws_url = "wss://wbs.mexc.com/ws"
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None

    async def connect(self):
        """Connect to MEXC WebSocket"""
        logger.info("Connecting to MEXC WebSocket")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True

                    # Subscribe to trade channels
                    for pair in TRACKED_SYMBOLS.get('mexc', []):
                        subscribe_msg = {
                            "method": "SUBSCRIPTION",
                            "params": [f"spot@public.deals.v3.api@{pair}"]
                        }
                        await ws.send_str(json.dumps(subscribe_msg))

                    logger.info("Subscribed to MEXC trade channels")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"MEXC WS error: {ws.exception()}")
                            break

        except Exception as e:
            logger.error(f"MEXC WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            if 'd' not in msg or 'deals' not in msg['d']:
                return

            symbol = msg.get('s', '')  # e.g., CHZUSDT

            for trade in msg['d']['deals']:
                price = float(trade.get('p', 0))
                quantity = float(trade.get('v', 0))
                side = 'buy' if trade.get('S') == 1 else 'sell'
                trade_id = trade.get('t', '')

                value_usd = price * quantity

                if value_usd >= WHALE_THRESHOLD_USD:
                    token_symbol = SYMBOL_MAP.get(symbol)
                    if not token_symbol:
                        token_symbol = symbol.replace('USDT', '')

                    whale_trade = {
                        'exchange': 'mexc',
                        'symbol': token_symbol,
                        'pair': symbol,
                        'side': side,
                        'price': price,
                        'quantity': quantity,
                        'value_usd': value_usd,
                        'is_aggressive': True,
                        'trade_id': trade_id,
                        'time': datetime.now(timezone.utc),
                    }

                    await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing MEXC trade: {e}")

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()


class MercadoBitcoinWhaleTracker:
    """Track whale trades on Mercado Bitcoin (Brazil) via WebSocket"""

    def __init__(self, on_whale_trade: callable):
        self.ws_url = "wss://ws.mercadobitcoin.net/ws"
        self.on_whale_trade = on_whale_trade
        self.running = False
        self.ws = None
        # BRL to USD conversion (approximate, updated periodically)
        self.brl_to_usd = 0.20  # ~5 BRL per USD

    async def _update_brl_rate(self):
        """Update BRL to USD rate"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.mercadobitcoin.net/api/v4/tickers?symbols=USDT-BRL") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data and len(data) > 0:
                            usdt_brl = float(data[0].get('last', 5.0))
                            self.brl_to_usd = 1.0 / usdt_brl
                            logger.info(f"Updated BRL/USD rate: {self.brl_to_usd:.4f}")
        except Exception as e:
            logger.warning(f"Failed to update BRL rate: {e}")

    async def connect(self):
        """Connect to Mercado Bitcoin WebSocket"""
        logger.info("Connecting to Mercado Bitcoin WebSocket")

        # Update exchange rate before starting
        await self._update_brl_rate()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(self.ws_url, heartbeat=30) as ws:
                    self.ws = ws
                    self.running = True

                    # Subscribe to trade channels
                    for pair in TRACKED_SYMBOLS.get('mercadobitcoin', []):
                        subscribe_msg = {
                            "type": "subscribe",
                            "subscription": {
                                "name": "trades",
                                "id": pair
                            }
                        }
                        await ws.send_str(json.dumps(subscribe_msg))

                    logger.info("Subscribed to Mercado Bitcoin trade channels")

                    # Periodically update exchange rate
                    last_rate_update = datetime.now(timezone.utc)

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_message(msg.data)

                            # Update rate every 5 minutes
                            if (datetime.now(timezone.utc) - last_rate_update).seconds > 300:
                                await self._update_brl_rate()
                                last_rate_update = datetime.now(timezone.utc)

                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            logger.error(f"Mercado Bitcoin WS error: {ws.exception()}")
                            break

        except Exception as e:
            logger.error(f"Mercado Bitcoin WebSocket error: {e}")
            self.running = False

    async def _handle_message(self, data: str):
        """Handle incoming trade message"""
        try:
            msg = json.loads(data)

            if msg.get('type') != 'trades' or 'data' not in msg:
                return

            symbol = msg.get('id', '')  # e.g., CHZ-BRL

            for trade in msg['data']:
                price_brl = float(trade.get('price', 0))
                quantity = float(trade.get('amount', 0))
                side = 'buy' if trade.get('type') == 'buy' else 'sell'
                trade_id = str(trade.get('tid', ''))

                # Convert BRL to USD
                price_usd = price_brl * self.brl_to_usd
                value_usd = price_usd * quantity

                if value_usd >= WHALE_THRESHOLD_USD:
                    token_symbol = SYMBOL_MAP.get(symbol, 'CHZ')

                    whale_trade = {
                        'exchange': 'mercadobitcoin',
                        'symbol': token_symbol,
                        'pair': symbol,
                        'side': side,
                        'price': price_usd,
                        'price_brl': price_brl,
                        'quantity': quantity,
                        'value_usd': value_usd,
                        'is_aggressive': True,
                        'trade_id': trade_id,
                        'time': datetime.now(timezone.utc),
                    }

                    await self.on_whale_trade(whale_trade)

        except Exception as e:
            logger.error(f"Error parsing Mercado Bitcoin trade: {e}")

    async def disconnect(self):
        self.running = False
        if self.ws:
            await self.ws.close()


class CEXWhaleTracker:
    """Main CEX whale tracker that manages all exchange connections"""

    def __init__(self):
        self.trackers: List[Any] = []
        self.recent_trades: List[Dict] = []  # In-memory cache
        self.max_recent = 100
        self._running = False

    async def _on_whale_trade(self, trade: Dict):
        """Handle whale trade from any exchange"""
        logger.info(
            f"🐋 WHALE {trade['side'].upper()}: {trade['symbol']} on {trade['exchange']} "
            f"${trade['value_usd']:,.0f} @ ${trade['price']:.4f}"
        )

        # Add to in-memory cache
        self.recent_trades.insert(0, trade)
        if len(self.recent_trades) > self.max_recent:
            self.recent_trades = self.recent_trades[:self.max_recent]

        # Save to database
        await self._save_trade(trade)

    async def _save_trade(self, trade: Dict):
        """Save whale trade to database"""
        try:
            token_id = await get_token_id(trade['symbol'])
            exchange_id = await get_exchange_id(trade['exchange'])

            query = """
                INSERT INTO cex_whale_transactions
                (time, token_id, exchange_id, symbol, exchange_name, side, price,
                 quantity, value_usd, is_aggressive, trade_id, raw_data)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """

            await Database.execute(
                query,
                trade['time'],
                token_id,
                exchange_id,
                trade['symbol'],
                trade['exchange'],
                trade['side'],
                Decimal(str(trade['price'])),
                Decimal(str(trade['quantity'])),
                Decimal(str(trade['value_usd'])),
                trade.get('is_aggressive', False),
                trade.get('trade_id'),
                json.dumps(trade, default=str),
            )

        except Exception as e:
            logger.error(f"Error saving whale trade: {e}")

    async def start(self):
        """Start all exchange trackers"""
        logger.info("Starting CEX Whale Tracker - Connecting to 11 exchanges")
        self._running = True

        # Create trackers for all exchanges
        binance_tracker = BinanceWhaleTracker(self._on_whale_trade)
        okx_tracker = OKXWhaleTracker(self._on_whale_trade)
        htx_tracker = HTXWhaleTracker(self._on_whale_trade)
        kucoin_tracker = KuCoinWhaleTracker(self._on_whale_trade)
        bybit_tracker = BybitWhaleTracker(self._on_whale_trade)
        gateio_tracker = GateIOWhaleTracker(self._on_whale_trade)
        mexc_tracker = MEXCWhaleTracker(self._on_whale_trade)
        mercadobitcoin_tracker = MercadoBitcoinWhaleTracker(self._on_whale_trade)

        self.trackers = [
            binance_tracker, okx_tracker, htx_tracker,
            kucoin_tracker, bybit_tracker, gateio_tracker, mexc_tracker,
            mercadobitcoin_tracker
        ]

        # Run all trackers concurrently with reconnection logic
        while self._running:
            tasks = [
                self._run_with_reconnect(binance_tracker, "Binance"),
                self._run_with_reconnect(okx_tracker, "OKX"),
                self._run_with_reconnect(htx_tracker, "HTX"),
                self._run_with_reconnect(kucoin_tracker, "KuCoin"),
                self._run_with_reconnect(bybit_tracker, "Bybit"),
                self._run_with_reconnect(gateio_tracker, "Gate.io"),
                self._run_with_reconnect(mexc_tracker, "MEXC"),
                self._run_with_reconnect(mercadobitcoin_tracker, "Mercado Bitcoin"),
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            if self._running:
                logger.info("Reconnecting to exchanges in 5 seconds...")
                await asyncio.sleep(5)

    async def _run_with_reconnect(self, tracker, name: str):
        """Run tracker with automatic reconnection"""
        while self._running:
            try:
                await tracker.connect()
            except Exception as e:
                logger.error(f"{name} tracker error: {e}")

            if self._running:
                logger.info(f"Reconnecting {name} in 5 seconds...")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop all trackers"""
        logger.info("Stopping CEX Whale Tracker")
        self._running = False

        for tracker in self.trackers:
            await tracker.disconnect()

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent whale trades from memory"""
        return self.recent_trades[:limit]


# Singleton instance
_tracker_instance: Optional[CEXWhaleTracker] = None


async def get_cex_tracker() -> CEXWhaleTracker:
    """Get or create CEX tracker instance"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = CEXWhaleTracker()
    return _tracker_instance


async def start_cex_tracking():
    """Start CEX whale tracking"""
    tracker = await get_cex_tracker()
    await tracker.start()


async def stop_cex_tracking():
    """Stop CEX whale tracking"""
    global _tracker_instance
    if _tracker_instance:
        await _tracker_instance.stop()
        _tracker_instance = None


# API helper functions
async def get_recent_whale_trades(
    limit: int = 50,
    symbol: Optional[str] = None,
    exchange: Optional[str] = None,
    min_value: float = WHALE_THRESHOLD_USD
) -> List[Dict]:
    """Get recent whale trades from database"""

    conditions = ["value_usd >= $1"]
    params = [Decimal(str(min_value))]
    param_idx = 2

    if symbol:
        conditions.append(f"symbol = ${param_idx}")
        params.append(symbol)
        param_idx += 1

    if exchange:
        conditions.append(f"exchange_name = ${param_idx}")
        params.append(exchange)
        param_idx += 1

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT
            time, symbol, exchange_name, side, price, quantity,
            value_usd, is_aggressive, trade_id
        FROM cex_whale_transactions
        WHERE {where_clause}
        ORDER BY time DESC
        LIMIT {limit}
    """

    rows = await Database.fetch(query, *params)

    return [
        {
            'time': row['time'].isoformat(),
            'symbol': row['symbol'],
            'exchange': row['exchange_name'],
            'side': row['side'],
            'price': float(row['price']),
            'quantity': float(row['quantity']),
            'value_usd': float(row['value_usd']),
            'is_aggressive': row['is_aggressive'],
            'trade_id': row['trade_id'],
        }
        for row in rows
    ]


async def get_whale_flow_summary(hours: int = 24) -> Dict:
    """Get whale flow summary for the last N hours"""

    query = """
        SELECT
            symbol,
            SUM(CASE WHEN side = 'buy' THEN value_usd ELSE 0 END) as buy_volume,
            SUM(CASE WHEN side = 'sell' THEN value_usd ELSE 0 END) as sell_volume,
            COUNT(CASE WHEN side = 'buy' THEN 1 END) as buy_count,
            COUNT(CASE WHEN side = 'sell' THEN 1 END) as sell_count
        FROM cex_whale_transactions
        WHERE time > NOW() - INTERVAL '%s hours'
        GROUP BY symbol
        ORDER BY SUM(value_usd) DESC
    """ % hours

    rows = await Database.fetch(query)

    summary = {
        'period_hours': hours,
        'tokens': []
    }

    total_buy = 0
    total_sell = 0

    for row in rows:
        buy_vol = float(row['buy_volume'] or 0)
        sell_vol = float(row['sell_volume'] or 0)
        net = buy_vol - sell_vol

        total_buy += buy_vol
        total_sell += sell_vol

        summary['tokens'].append({
            'symbol': row['symbol'],
            'buy_volume': buy_vol,
            'sell_volume': sell_vol,
            'net_flow': net,
            'buy_count': row['buy_count'] or 0,
            'sell_count': row['sell_count'] or 0,
            'signal': 'bullish' if net > 0 else 'bearish' if net < 0 else 'neutral',
        })

    summary['totals'] = {
        'buy_volume': total_buy,
        'sell_volume': total_sell,
        'net_flow': total_buy - total_sell,
    }

    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_cex_tracking())
