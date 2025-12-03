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
    # Covers all Chiliz fan tokens - 65 tokens total
    search_queries: Dict[str, str] = field(default_factory=lambda: {
        # Base token
        "CHZ": "chiliz OR #Chiliz OR CHZ token OR socios",

        # La Liga (Spain)
        "BAR": "barcelona fan token OR #BarcaToken OR BAR token chiliz",
        "ATM": "atletico madrid fan token OR #AtletiToken",
        "VCF": "valencia fan token OR #ValenciaToken",
        "SEVILLA": "sevilla fan token OR #SevillaToken",

        # Serie A (Italy)
        "JUV": "juventus fan token OR #JuventusToken OR JUV token",
        "ACM": "AC milan fan token OR #ACMilanToken",
        "ASR": "AS roma fan token OR #ASRomaToken",
        "LAZIO": "lazio fan token OR #LazioToken",
        "INTER": "inter milan fan token OR #InterToken",
        "NAP": "napoli fan token OR #NapoliToken",
        "UDI": "udinese fan token OR #UdineseToken",

        # Premier League (England)
        "CITY": "man city fan token OR #ManCityToken",
        "AFC": "arsenal fan token OR #ArsenalToken OR AFC token",
        "SPURS": "tottenham fan token OR #SpursToken",
        "EFC": "everton fan token OR #EvertonToken",
        "AVL": "aston villa fan token OR #AVLToken",

        # Ligue 1 (France)
        "PSG": "PSG fan token OR #PSGToken OR paris saint germain token",
        "ASM": "AS monaco fan token OR #ASMToken",

        # Primeira Liga (Portugal)
        "PORTO": "porto fan token OR #PortoToken OR FC Porto token",
        "BENFICA": "benfica fan token OR #BenficaToken",

        # Süper Lig (Turkey)
        "GAL": "galatasaray fan token OR #GalatasarayToken",
        "TRA": "trabzonspor fan token OR #TrabzonsporToken",
        "GOZ": "goztepe fan token OR #GoztepeToken",
        "SAM": "samsunspor fan token OR #SamsunToken",
        "ALA": "alanyaspor fan token OR #AlanyasporToken",
        "IBFK": "basaksehir fan token OR #BasaksehirToken",
        "BJK": "besiktas fan token OR #BesiktasToken",
        "FB": "fenerbahce fan token OR #FenerbahceToken",

        # Brasileirão (Brazil)
        "SANTOS": "santos fan token OR #SantosToken",
        "MENGO": "flamengo fan token OR #MengoToken OR #Flamengo",
        "FLU": "fluminense fan token OR #FluToken OR #Fluminense",
        "SCCP": "corinthians fan token OR #SCCPToken OR #Corinthians",
        "SPFC": "sao paulo fan token OR #SPFCToken",
        "GALO": "atletico mineiro fan token OR #GaloToken",
        "VERDAO": "palmeiras fan token OR #VerdaoToken OR #Palmeiras",
        "VASCO": "vasco fan token OR #VascoToken",
        "BAHIA": "bahia fan token OR #BahiaToken",
        "SACI": "internacional fan token OR #InterToken OR SC Internacional",

        # Argentina
        "ARG": "argentina fan token OR #ARGToken OR AFA token",
        "CAI": "independiente fan token OR #IndependienteToken",

        # Other Leagues
        "LEG": "legia warsaw fan token OR #LegiaToken",
        "TIGRES": "tigres fan token OR #TigresToken",
        "YBO": "young boys fan token OR #YoungBoysToken",
        "STV": "sint truiden fan token OR STVV token",

        # National Teams
        "POR": "portugal national team fan token OR #PortugalToken",
        "ITA": "italy national team fan token OR #ItalyToken",
        "VATRENI": "croatia fan token OR #VatreniToken OR #CroatiaToken",
        "SNFT": "spain national team fan token OR #SpainToken",
        "BFT": "brazil national team fan token OR #BrazilToken",

        # Formula 1
        "ALPINE": "alpine f1 fan token OR #AlpineToken",
        "SAUBER": "sauber f1 fan token OR #SauberToken OR alfa romeo f1",
        "AM": "aston martin f1 fan token OR #AMF1Token",

        # MMA / Fighting
        "UFC": "UFC fan token OR #UFCToken",
        "PFL": "PFL fan token OR #PFLToken",

        # Esports
        "OG": "OG esports fan token OR #OGToken",
        "NAVI": "navi esports fan token OR #NaviToken OR natus vincere",
        "ALL": "alliance esports fan token OR #AllianceToken",
        "TH": "team heretics fan token OR #HereticsToken",
        "DOJO": "ninjas pyjamas fan token OR #NIPToken",

        # Individual
        "MODRIC": "luka modric fan token OR #ModricToken",
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


# Fan token definitions with all metadata - 65 tokens total
FAN_TOKENS = [
    # Base token
    {"symbol": "CHZ", "name": "Chiliz", "team": "Chiliz Chain", "coingecko_id": "chiliz", "league": None, "country": None},

    # Football - La Liga (Spain)
    {"symbol": "BAR", "name": "FC Barcelona Fan Token", "team": "FC Barcelona", "coingecko_id": "fc-barcelona-fan-token", "league": "La Liga", "country": "Spain"},
    {"symbol": "ATM", "name": "Atletico Madrid Fan Token", "team": "Atlético de Madrid", "coingecko_id": "atletico-madrid", "league": "La Liga", "country": "Spain"},
    {"symbol": "VCF", "name": "Valencia CF Fan Token", "team": "Valencia CF", "coingecko_id": "valencia-cf-fan-token", "league": "La Liga", "country": "Spain"},
    {"symbol": "SEVILLA", "name": "Sevilla Fan Token", "team": "Sevilla FC", "coingecko_id": "sevilla-fan-token", "league": "La Liga", "country": "Spain"},

    # Football - Serie A (Italy)
    {"symbol": "JUV", "name": "Juventus Fan Token", "team": "Juventus", "coingecko_id": "juventus-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "ACM", "name": "AC Milan Fan Token", "team": "AC Milan", "coingecko_id": "ac-milan-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "ASR", "name": "AS Roma Fan Token", "team": "AS Roma", "coingecko_id": "as-roma-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "LAZIO", "name": "Lazio Fan Token", "team": "SS Lazio", "coingecko_id": "lazio-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "INTER", "name": "Inter Milan Fan Token", "team": "Inter Milan", "coingecko_id": "inter-milan-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "NAP", "name": "Napoli Fan Token", "team": "SSC Napoli", "coingecko_id": "napoli-fan-token", "league": "Serie A", "country": "Italy"},
    {"symbol": "UDI", "name": "Udinese Calcio Fan Token", "team": "Udinese Calcio", "coingecko_id": "udinese-calcio-fan-token", "league": "Serie A", "country": "Italy"},

    # Football - Premier League (England)
    {"symbol": "CITY", "name": "Manchester City Fan Token", "team": "Manchester City", "coingecko_id": "manchester-city-fan-token", "league": "Premier League", "country": "England"},
    {"symbol": "AFC", "name": "Arsenal Fan Token", "team": "Arsenal FC", "coingecko_id": "arsenal-fan-token", "league": "Premier League", "country": "England"},
    {"symbol": "SPURS", "name": "Tottenham Hotspur Fan Token", "team": "Tottenham Hotspur", "coingecko_id": "tottenham-hotspur-fc-fan-token", "league": "Premier League", "country": "England"},
    {"symbol": "EFC", "name": "Everton Fan Token", "team": "Everton FC", "coingecko_id": "everton-fan-token", "league": "Premier League", "country": "England"},
    {"symbol": "AVL", "name": "Aston Villa Fan Token", "team": "Aston Villa", "coingecko_id": "aston-villa-fan-token", "league": "Premier League", "country": "England"},

    # Football - Ligue 1 (France)
    {"symbol": "PSG", "name": "Paris Saint-Germain Fan Token", "team": "Paris Saint-Germain", "coingecko_id": "paris-saint-germain-fan-token", "league": "Ligue 1", "country": "France"},
    {"symbol": "ASM", "name": "AS Monaco Fan Token", "team": "AS Monaco", "coingecko_id": "as-monaco-fan-token", "league": "Ligue 1", "country": "France"},

    # Football - Primeira Liga (Portugal)
    {"symbol": "PORTO", "name": "FC Porto Fan Token", "team": "FC Porto", "coingecko_id": "fc-porto", "league": "Primeira Liga", "country": "Portugal"},
    {"symbol": "BENFICA", "name": "SL Benfica Fan Token", "team": "SL Benfica", "coingecko_id": "sl-benfica-fan-token", "league": "Primeira Liga", "country": "Portugal"},

    # Football - Süper Lig (Turkey)
    {"symbol": "GAL", "name": "Galatasaray Fan Token", "team": "Galatasaray", "coingecko_id": "galatasaray-fan-token", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "TRA", "name": "Trabzonspor Fan Token", "team": "Trabzonspor", "coingecko_id": "trabzonspor-fan-token", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "GOZ", "name": "Göztepe S.K. Fan Token", "team": "Göztepe S.K.", "coingecko_id": "goztepe-s-k-fan-token", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "SAM", "name": "Samsunspor Fan Token", "team": "Samsunspor", "coingecko_id": "samsunspor-fan-token", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "ALA", "name": "Alanyaspor Fan Token", "team": "Alanyaspor", "coingecko_id": "alanyaspor-fan-token", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "IBFK", "name": "İstanbul Başakşehir Fan Token", "team": "İstanbul Başakşehir", "coingecko_id": "istanbul-basaksehir-fan-token", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "BJK", "name": "Beşiktaş Fan Token", "team": "Beşiktaş", "coingecko_id": "besiktas", "league": "Süper Lig", "country": "Turkey"},
    {"symbol": "FB", "name": "Fenerbahçe Fan Token", "team": "Fenerbahçe", "coingecko_id": "fenerbahce-token", "league": "Süper Lig", "country": "Turkey"},

    # Football - Brasileirão (Brazil)
    {"symbol": "SANTOS", "name": "Santos FC Fan Token", "team": "Santos FC", "coingecko_id": "santos-fc-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "MENGO", "name": "Flamengo Fan Token", "team": "Flamengo", "coingecko_id": "flamengo-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "FLU", "name": "Fluminense FC Fan Token", "team": "Fluminense", "coingecko_id": "fluminense-fc-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "SCCP", "name": "S.C. Corinthians Fan Token", "team": "Corinthians", "coingecko_id": "s-c-corinthians-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "SPFC", "name": "Sao Paulo FC Fan Token", "team": "São Paulo FC", "coingecko_id": "sao-paulo-fc-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "GALO", "name": "Atlético Mineiro Fan Token", "team": "Atlético Mineiro", "coingecko_id": "clube-atletico-mineiro-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "VERDAO", "name": "Palmeiras Fan Token", "team": "Palmeiras", "coingecko_id": "palmeiras-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "VASCO", "name": "Vasco da Gama Fan Token", "team": "Vasco da Gama", "coingecko_id": "vasco-da-gama-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "BAHIA", "name": "Esporte Clube Bahia Fan Token", "team": "EC Bahia", "coingecko_id": "esporte-clube-bahia-fan-token", "league": "Brasileirão", "country": "Brazil"},
    {"symbol": "SACI", "name": "SC Internacional Fan Token", "team": "Internacional", "coingecko_id": "sc-internacional-fan-token", "league": "Brasileirão", "country": "Brazil"},

    # Football - Argentina
    {"symbol": "ARG", "name": "Argentine Football Association Fan Token", "team": "Argentina NT", "coingecko_id": "argentine-football-association-fan-token", "league": "National Team", "country": "Argentina"},
    {"symbol": "CAI", "name": "Club Atletico Independiente Fan Token", "team": "Independiente", "coingecko_id": "club-atletico-independiente", "league": "Argentine Primera", "country": "Argentina"},

    # Football - Other Leagues
    {"symbol": "LEG", "name": "Legia Warsaw Fan Token", "team": "Legia Warsaw", "coingecko_id": "legia-warsaw-fan-token", "league": "Ekstraklasa", "country": "Poland"},
    {"symbol": "TIGRES", "name": "Tigres Fan Token", "team": "Tigres UANL", "coingecko_id": "tigres-fan-token", "league": "Liga MX", "country": "Mexico"},
    {"symbol": "YBO", "name": "Young Boys Fan Token", "team": "BSC Young Boys", "coingecko_id": "young-boys-fan-token", "league": "Swiss Super League", "country": "Switzerland"},
    {"symbol": "STV", "name": "Sint-Truidense VV Fan Token", "team": "Sint-Truidense VV", "coingecko_id": "sint-truidense-voetbalvereniging-fan-token", "league": "Belgian Pro League", "country": "Belgium"},

    # Football - National Teams
    {"symbol": "POR", "name": "Portugal National Team Fan Token", "team": "Portugal NT", "coingecko_id": "portugal-national-team-fan-token", "league": "National Team", "country": "Portugal"},
    {"symbol": "ITA", "name": "Italian National Football Team Fan Token", "team": "Italy NT", "coingecko_id": "italian-national-football-team-fan-token", "league": "National Team", "country": "Italy"},
    {"symbol": "VATRENI", "name": "Croatian Football Federation Token", "team": "Croatia NT", "coingecko_id": "croatian-ff-fan-token", "league": "National Team", "country": "Croatia"},
    {"symbol": "SNFT", "name": "Spain National Football Team Fan Token", "team": "Spain NT", "coingecko_id": "spain-national-fan-token", "league": "National Team", "country": "Spain"},
    {"symbol": "BFT", "name": "Brazil National Football Team Fan Token", "team": "Brazil NT", "coingecko_id": "brazil-fan-token", "league": "National Team", "country": "Brazil"},

    # Formula 1
    {"symbol": "ALPINE", "name": "Alpine F1 Team Fan Token", "team": "Alpine F1", "coingecko_id": "alpine-f1-team-fan-token", "league": "Formula 1", "country": "France"},
    {"symbol": "SAUBER", "name": "Alfa Romeo Racing ORLEN Fan Token", "team": "Sauber F1", "coingecko_id": "alfa-romeo-racing-orlen-fan-token", "league": "Formula 1", "country": "Switzerland"},
    {"symbol": "AM", "name": "Aston Martin Cognizant Fan Token", "team": "Aston Martin F1", "coingecko_id": "aston-martin-cognizant-fan-token", "league": "Formula 1", "country": "UK"},

    # MMA / Fighting
    {"symbol": "UFC", "name": "UFC Fan Token", "team": "UFC", "coingecko_id": "ufc-fan-token", "league": "MMA", "country": "USA"},
    {"symbol": "PFL", "name": "Professional Fighters League Fan Token", "team": "PFL", "coingecko_id": "professional-fighters-league-fan-token", "league": "MMA", "country": "USA"},

    # Esports
    {"symbol": "OG", "name": "OG Fan Token", "team": "OG Esports", "coingecko_id": "og-fan-token", "league": "Esports", "country": None},
    {"symbol": "NAVI", "name": "Natus Vincere Fan Token", "team": "Natus Vincere", "coingecko_id": "natus-vincere-fan-token", "league": "Esports", "country": "Ukraine"},
    {"symbol": "ALL", "name": "Alliance Fan Token", "team": "Alliance", "coingecko_id": "alliance-fan-token", "league": "Esports", "country": "Sweden"},
    {"symbol": "TH", "name": "Team Heretics Fan Token", "team": "Team Heretics", "coingecko_id": "team-heretics-fan-token", "league": "Esports", "country": "Spain"},
    {"symbol": "DOJO", "name": "Ninjas in Pyjamas Fan Token", "team": "Ninjas in Pyjamas", "coingecko_id": "ninjas-in-pyjamas", "league": "Esports", "country": "Sweden"},

    # Other/Individual
    {"symbol": "MODRIC", "name": "Luka Modric Fan Token", "team": "Luka Modric", "coingecko_id": "luka-modric", "league": "Individual", "country": "Croatia"},
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
