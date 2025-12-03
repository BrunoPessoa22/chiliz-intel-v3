"""
Chiliz Marketing Intelligence v3.0 - Configuration Settings
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL/TimescaleDB connection configuration"""
    # Railway provides DATABASE_URL directly
    database_url: str = os.getenv("DATABASE_URL", "")

    # Fallback to individual vars if DATABASE_URL not set
    host: str = os.getenv("PGHOST", os.getenv("TIMESCALE_HOST", "localhost"))
    port: int = int(os.getenv("PGPORT", os.getenv("TIMESCALE_PORT", "5432")))
    database: str = os.getenv("PGDATABASE", os.getenv("TIMESCALE_DB", "railway"))
    user: str = os.getenv("PGUSER", os.getenv("TIMESCALE_USER", "postgres"))
    password: str = os.getenv("PGPASSWORD", os.getenv("TIMESCALE_PASSWORD", ""))

    @property
    def connection_string(self) -> str:
        if self.database_url:
            return self.database_url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def async_connection_string(self) -> str:
        if self.database_url:
            # Convert postgres:// to postgresql+asyncpg://
            url = self.database_url.replace("postgres://", "postgresql://")
            return url
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class CoinGeckoConfig:
    """CoinGecko Pro API configuration ($129/mo tier)"""
    api_key: str = os.getenv("COINGECKO_API_KEY", "")
    base_url: str = "https://pro-api.coingecko.com/api/v3"

    # Rate limits for Pro tier
    requests_per_minute: int = 500

    # Endpoints we use
    endpoints: Dict[str, str] = field(default_factory=lambda: {
        "coins_markets": "/coins/markets",
        "coin_tickers": "/coins/{id}/tickers",
        "exchanges_tickers": "/exchanges/{id}/tickers",
        "coin_ohlc": "/coins/{id}/ohlc",
        "coin_market_chart": "/coins/{id}/market_chart",
    })


@dataclass
class XAPIConfig:
    """X (Twitter) API configuration - Basic tier compatible"""
    bearer_token: str = os.getenv("X_BEARER_TOKEN", "")
    base_url: str = "https://api.twitter.com/2"

    # Rate limits for Basic tier
    search_requests_per_15min: int = 180

    # Search queries for fan tokens (Basic tier - no cashtag operator)
    # Covers all major Chiliz fan tokens
    search_queries: Dict[str, str] = field(default_factory=lambda: {
        # Major tokens
        "CHZ": "chiliz OR #Chiliz OR CHZ token OR socios",
        "BAR": "barcelona fan token OR #BarcaToken OR BAR token chiliz",
        "PSG": "PSG fan token OR #PSGToken OR paris saint germain token",
        "JUV": "juventus fan token OR #JuventusToken OR JUV token",
        "ATM": "atletico madrid fan token OR #AtletiToken",
        "ACM": "AC milan fan token OR #ACMilanToken",
        "ASR": "AS roma fan token OR #ASRomaToken",
        "CITY": "man city fan token OR #ManCityToken",
        # Italian clubs
        "INTER": "inter milan fan token OR #InterToken",
        "NAP": "napoli fan token OR #NapoliToken",
        "LAZIO": "lazio fan token OR #LazioToken",
        # Portuguese clubs
        "POR": "porto fan token OR #PortoToken",
        "BENFICA": "benfica fan token OR #BenficaToken",
        # Spanish clubs
        "VCF": "valencia fan token OR #ValenciaToken",
        "SEVILLA": "sevilla fan token OR #SevillaToken",
        "LEV": "levante fan token OR #LevanteToken",
        # Turkish clubs
        "GAL": "galatasaray fan token OR #GalatasarayToken",
        "TRA": "trabzonspor fan token OR #TrabzonsporToken",
        # English clubs
        "SPURS": "tottenham fan token OR #SpursToken",
        "EFC": "everton fan token OR #EvertonToken",
        "AVL": "aston villa fan token OR #AVLToken",
        "CPFC": "crystal palace fan token",
        "LUFC": "leeds united fan token",
        # French clubs
        "ASM": "AS monaco fan token OR #ASMToken",
        # Argentine clubs
        "ARG": "argentina fan token OR #ARGToken OR AFA",
        "RACING": "racing club fan token OR #RacingToken",
        "CAI": "independiente fan token",
        # Brazilian clubs
        "SANTOS": "santos fan token OR #SantosToken",
        "MENGO": "flamengo fan token OR #MengoToken",
        "SPFC": "sao paulo fan token OR #SPFCToken",
        "SCCP": "corinthians fan token OR #SCCPToken",
        "GALO": "atletico mineiro fan token OR #GaloToken",
        "VERDAO": "palmeiras fan token OR #VerdaoToken",
        "FLU": "fluminense fan token OR #FluToken",
        "VASCO": "vasco fan token OR #VascoToken",
        "BAHIA": "bahia fan token",
        # Esports
        "OG": "OG esports fan token OR #OGToken",
        "NAVI": "navi esports fan token OR #NaviToken",
        "ALL": "alliance esports fan token",
        # Formula 1
        "ALPINE": "alpine f1 fan token OR #AlpineToken",
        "SAUBER": "sauber f1 fan token OR #SauberToken",
        "AM": "aston martin f1 fan token",
        # UFC/MMA
        "UFC": "UFC fan token OR #UFCToken",
        "PFL": "PFL fan token",
        # National teams
        "ITA": "italy national team fan token",
    })


@dataclass
class OpenRouterConfig:
    """OpenRouter AI configuration for Management Assistant"""
    api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "anthropic/claude-3.5-sonnet"  # Best for analysis

    # Model parameters
    max_tokens: int = 4096
    temperature: float = 0.3  # Lower for more factual responses


@dataclass
class SlackConfig:
    """Slack integration for alerts and reports"""
    webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    access_token: str = os.getenv("SLACK_ACCESS_TOKEN", "")

    # Channel mappings
    channels: Dict[str, str] = field(default_factory=lambda: {
        "alerts": "#chiliz-alerts",
        "reports": "#chiliz-reports",
        "signals": "#chiliz-signals",
    })


@dataclass
class ChilizChainConfig:
    """Chiliz Chain RPC configuration for on-chain data"""
    rpc_url: str = os.getenv("CHILIZ_RPC_URL", "https://rpc.chiliz.com")
    chain_id: int = 88888

    # Fan token contract addresses on Chiliz Chain
    token_contracts: Dict[str, str] = field(default_factory=lambda: {
        "CHZ": "0x0000000000000000000000000000000000000000",  # Native
        "BAR": "0x...",  # To be filled with actual addresses
        "PSG": "0x...",
        # Add more as needed
    })


# Fan token definitions with all metadata
FAN_TOKENS = [
    {"symbol": "CHZ", "name": "Chiliz", "team": "Chiliz Chain", "coingecko_id": "chiliz", "league": None, "country": None},
    {"symbol": "BAR", "name": "FC Barcelona Fan Token", "team": "FC Barcelona", "coingecko_id": "fc-barcelona-fan-token", "league": "La Liga", "country": "Spain"},
    {"symbol": "PSG", "name": "Paris Saint-Germain Fan Token", "team": "Paris Saint-Germain", "coingecko_id": "paris-saint-germain-fan-token", "league": "Ligue 1", "country": "France"},
    {"symbol": "JUV", "name": "Juventus Fan Token", "team": "Juventus", "coingecko_id": "juventus-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "ATM", "name": "Atlético de Madrid Fan Token", "team": "Atlético de Madrid", "coingecko_id": "atletico-madrid", "league": "La Liga", "country": "Spain"},
    {"symbol": "ACM", "name": "AC Milan Fan Token", "team": "AC Milan", "coingecko_id": "ac-milan-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "ASR", "name": "AS Roma Fan Token", "team": "AS Roma", "coingecko_id": "as-roma-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "CITY", "name": "Manchester City Fan Token", "team": "Manchester City", "coingecko_id": "manchester-city-fan-token", "league": "Premier League", "country": "England"},
    {"symbol": "LAZIO", "name": "Lazio Fan Token", "team": "SS Lazio", "coingecko_id": "lazio-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "PORTO", "name": "FC Porto Fan Token", "team": "FC Porto", "coingecko_id": "fc-porto", "league": "Primeira Liga", "country": "Portugal"},
    {"symbol": "GAL", "name": "Galatasaray Fan Token", "team": "Galatasaray", "coingecko_id": "galatasaray-fan-token", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "INTER", "name": "Inter Milan Fan Token", "team": "Inter Milan", "coingecko_id": "inter-milan-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "NAP", "name": "Napoli Fan Token", "team": "SSC Napoli", "coingecko_id": "napoli-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "OG", "name": "OG Fan Token", "team": "OG Esports", "coingecko_id": "og-fan-token", "league": "Esports", "country": None},
    {"symbol": "SANTOS", "name": "Santos FC Fan Token", "team": "Santos FC", "coingecko_id": "santos-fc-fan-token", "league": "Série A", "country": "Brazil"},
    {"symbol": "ALPINE", "name": "Alpine F1 Team Fan Token", "team": "Alpine F1", "coingecko_id": "alpine-f1-team-fan-token", "league": "Formula 1", "country": "France"},
]

# Exchange definitions
EXCHANGES = [
    {"code": "binance", "name": "Binance", "coingecko_id": "binance", "priority": 1},
    {"code": "okx", "name": "OKX", "coingecko_id": "okx", "priority": 2},
    {"code": "upbit", "name": "Upbit", "coingecko_id": "upbit", "priority": 3},
    {"code": "paribu", "name": "Paribu", "coingecko_id": "paribu", "priority": 4},
    {"code": "bithumb", "name": "Bithumb", "coingecko_id": "bithumb", "priority": 5},
    {"code": "coinbase", "name": "Coinbase", "coingecko_id": "gdax", "priority": 6},
    {"code": "kraken", "name": "Kraken", "coingecko_id": "kraken", "priority": 7},
    {"code": "kucoin", "name": "KuCoin", "coingecko_id": "kucoin", "priority": 8},
    {"code": "bybit", "name": "Bybit", "coingecko_id": "bybit_spot", "priority": 9},
    {"code": "gate", "name": "Gate.io", "coingecko_id": "gate", "priority": 10},
    {"code": "htx", "name": "HTX (Huobi)", "coingecko_id": "huobi", "priority": 11},
    {"code": "bitfinex", "name": "Bitfinex", "coingecko_id": "bitfinex", "priority": 12},
    {"code": "mexc", "name": "MEXC", "coingecko_id": "mxc", "priority": 13},
    {"code": "mercadobitcoin", "name": "Mercado Bitcoin", "coingecko_id": "mercado_bitcoin", "priority": 14},
]

# Health score thresholds
HEALTH_SCORE_CONFIG = {
    "weights": {
        "volume": 0.25,
        "liquidity": 0.25,
        "spread": 0.20,
        "holders": 0.15,
        "price_stability": 0.15,
    },
    "grades": {
        "A": (90, 100),
        "B": (75, 89),
        "C": (60, 74),
        "D": (40, 59),
        "F": (0, 39),
    },
    "thresholds": {
        "volume_24h_excellent": 1_000_000,
        "volume_24h_good": 500_000,
        "volume_24h_fair": 100_000,
        "liquidity_1pct_excellent": 100_000,
        "liquidity_1pct_good": 50_000,
        "liquidity_1pct_fair": 10_000,
        "spread_excellent_bps": 20,
        "spread_good_bps": 50,
        "spread_fair_bps": 100,
        "holder_growth_excellent": 100,
        "holder_growth_good": 50,
        "holder_growth_fair": 0,
    }
}

# Collection intervals (in seconds)
COLLECTION_INTERVALS = {
    "price_volume": 60,       # Every minute
    "spread": 60,             # Every minute
    "liquidity": 300,         # Every 5 minutes
    "holders": 3600,          # Every hour
    "social": 900,            # Every 15 minutes
    "aggregation": 300,       # Every 5 minutes
    "correlation": 86400,     # Daily
    "health_score": 300,      # Every 5 minutes
}


# Create singleton instances
db_config = DatabaseConfig()
coingecko_config = CoinGeckoConfig()
x_api_config = XAPIConfig()
openrouter_config = OpenRouterConfig()
slack_config = SlackConfig()
chiliz_chain_config = ChilizChainConfig()
