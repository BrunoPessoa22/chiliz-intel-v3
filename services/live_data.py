"""
Live Data Service
Fetches real-time data from CoinGecko free API on-demand
No database dependency - calculates health scores on-the-fly
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Chiliz Chain Fan Tokens - Complete 2025 list from fantokens.com
# All official Socios.com fan tokens on Chiliz Chain
COINGECKO_IDS = {
    # ===== ESPORTS =====
    "og-fan-token": {"symbol": "OG", "team": "OG Esports", "league": "Esports"},
    "natus-vincere-fan-token": {"symbol": "NAVI", "team": "Natus Vincere", "league": "Esports"},
    "alliance-fan-token": {"symbol": "ALL", "team": "Alliance", "league": "Esports"},
    "team-heretics-fan-token": {"symbol": "TH", "team": "Team Heretics", "league": "Esports"},
    "team-vitality-fan-token": {"symbol": "VIT", "team": "Team Vitality", "league": "Esports"},
    "ninjas-in-pyjamas": {"symbol": "DOJO", "team": "Ninjas in Pyjamas", "league": "Esports"},
    "mibr-fan-token": {"symbol": "MIBR", "team": "MIBR", "league": "Esports"},
    "endpoint-cex-fan-token": {"symbol": "ENDCEX", "team": "Endpoint CeX", "league": "Esports"},

    # ===== FOOTBALL - LA LIGA (Spain) =====
    "fc-barcelona-fan-token": {"symbol": "BAR", "team": "FC Barcelona", "league": "La Liga"},
    "atletico-madrid": {"symbol": "ATM", "team": "Atletico de Madrid", "league": "La Liga"},
    "valencia-cf-fan-token": {"symbol": "VCF", "team": "Valencia CF", "league": "La Liga"},
    "sevilla-fan-token": {"symbol": "SEVILLA", "team": "Sevilla FC", "league": "La Liga"},
    "levante-ud-fan-token": {"symbol": "LEV", "team": "Levante U.D.", "league": "La Liga"},
    "real-sociedad-fan-token": {"symbol": "RSO", "team": "Real Sociedad", "league": "La Liga"},

    # ===== FOOTBALL - PREMIER LEAGUE (England) =====
    "manchester-city-fan-token": {"symbol": "CITY", "team": "Manchester City", "league": "Premier League"},
    "arsenal-fan-token": {"symbol": "AFC", "team": "Arsenal FC", "league": "Premier League"},
    "tottenham-hotspur-fc-fan-token": {"symbol": "SPURS", "team": "Tottenham Hotspur", "league": "Premier League"},
    "everton-fan-token": {"symbol": "EFC", "team": "Everton FC", "league": "Premier League"},
    "aston-villa-fan-token": {"symbol": "AVL", "team": "Aston Villa", "league": "Premier League"},
    "leeds-united-fan-token": {"symbol": "LUFC", "team": "Leeds United", "league": "Premier League"},
    "crystal-palace-fc-fan-token": {"symbol": "CPFC", "team": "Crystal Palace", "league": "Premier League"},

    # ===== FOOTBALL - SERIE A (Italy) =====
    "juventus-fan-token": {"symbol": "JUV", "team": "Juventus", "league": "Serie A"},
    "ac-milan-fan-token": {"symbol": "ACM", "team": "AC Milan", "league": "Serie A"},
    "as-roma-fan-token": {"symbol": "ASR", "team": "AS Roma", "league": "Serie A"},
    "inter-milan-fan-token": {"symbol": "INTER", "team": "Inter Milan", "league": "Serie A"},
    "napoli-fan-token": {"symbol": "NAP", "team": "SSC Napoli", "league": "Serie A"},
    "bologna-fc-fan-token": {"symbol": "BFC", "team": "Bologna FC", "league": "Serie A"},
    "udinese-calcio-fan-token": {"symbol": "UDI", "team": "Udinese Calcio", "league": "Serie A"},
    "novara-calcio-fan-token": {"symbol": "NOV", "team": "Novara Calcio", "league": "Serie A"},

    # ===== FOOTBALL - LIGUE 1 (France) =====
    "paris-saint-germain-fan-token": {"symbol": "PSG", "team": "Paris Saint-Germain", "league": "Ligue 1"},
    "as-monaco-fan-token": {"symbol": "ASM", "team": "AS Monaco", "league": "Ligue 1"},

    # ===== FOOTBALL - PRIMEIRA LIGA (Portugal) =====
    "sl-benfica-fan-token": {"symbol": "BENFICA", "team": "SL Benfica", "league": "Primeira Liga"},

    # ===== FOOTBALL - SUPER LIG (Turkey) =====
    "galatasaray-fan-token": {"symbol": "GAL", "team": "Galatasaray", "league": "Super Lig"},
    "trabzonspor-fan-token": {"symbol": "TRA", "team": "Trabzonspor", "league": "Super Lig"},
    "goztepe-s-k-fan-token": {"symbol": "GOZ", "team": "Göztepe S.K.", "league": "Super Lig"},
    "samsunspor-fan-token": {"symbol": "SAM", "team": "Samsunspor", "league": "Super Lig"},
    "alanyaspor-fan-token": {"symbol": "ALA", "team": "Alanyaspor", "league": "Super Lig"},
    "istanbul-basaksehir-fan-token": {"symbol": "IBFK", "team": "İstanbul Başakşehir", "league": "Super Lig"},
    "gaziantep-fk-fan-token": {"symbol": "GFK", "team": "Gaziantep FK", "league": "Super Lig"},

    # ===== FOOTBALL - BRAZIL =====
    "flamengo-fan-token": {"symbol": "MENGO", "team": "Flamengo", "league": "Serie A Brazil"},
    "s-c-corinthians-fan-token": {"symbol": "SCCP", "team": "S.C. Corinthians", "league": "Serie A Brazil"},
    "clube-atletico-mineiro-fan-token": {"symbol": "GALO", "team": "Atlético Mineiro", "league": "Serie A Brazil"},
    "sao-paulo-fc-fan-token": {"symbol": "SPFC", "team": "São Paulo FC", "league": "Serie A Brazil"},
    "palmeiras-fan-token": {"symbol": "VERDAO", "team": "SE Palmeiras", "league": "Serie A Brazil"},
    "fluminense-fc-fan-token": {"symbol": "FLU", "team": "Fluminense FC", "league": "Serie A Brazil"},
    "vasco-da-gama-fan-token": {"symbol": "VASCO", "team": "Vasco da Gama", "league": "Serie A Brazil"},
    "sc-internacional-fan-token": {"symbol": "SACI", "team": "SC Internacional", "league": "Serie A Brazil"},
    "esporte-clube-bahia-fan-token": {"symbol": "BAHIA", "team": "EC Bahia", "league": "Serie A Brazil"},

    # ===== FOOTBALL - ARGENTINA =====
    "club-atletico-independiente": {"symbol": "CAI", "team": "Club Atlético Independiente", "league": "Primera Division Argentina"},
    "racing-club-fan-token": {"symbol": "RACING", "team": "Racing Club", "league": "Primera Division Argentina"},

    # ===== FOOTBALL - COLOMBIA =====
    "millonarios-fc-fan-token": {"symbol": "MFC", "team": "Millonarios FC", "league": "Categoria Primera A"},

    # ===== FOOTBALL - CHILE =====
    "universidad-de-chile-fan-token": {"symbol": "UCH", "team": "Universidad de Chile", "league": "Primera Division Chile"},

    # ===== FOOTBALL - MEXICO =====
    "tigres-fan-token": {"symbol": "TIGRES", "team": "Tigres UANL", "league": "Liga MX"},
    "club-santos-laguna-fan-token": {"symbol": "SAN", "team": "Club Santos Laguna", "league": "Liga MX"},
    "chivas-fan-token": {"symbol": "CHVS", "team": "Chivas", "league": "Liga MX"},
    "atlas-fc-fan-token": {"symbol": "ATLAS", "team": "Atlas FC", "league": "Liga MX"},

    # ===== FOOTBALL - POLAND =====
    "legia-warsaw-fan-token": {"symbol": "LEG", "team": "Legia Warsaw", "league": "Ekstraklasa"},

    # ===== FOOTBALL - SWITZERLAND =====
    "young-boys-fan-token": {"symbol": "YBO", "team": "BSC Young Boys", "league": "Swiss Super League"},

    # ===== FOOTBALL - BELGIUM =====
    "sint-truidense-voetbalvereniging-fan-token": {"symbol": "STV", "team": "Sint-Truidense VV", "league": "Belgian Pro League"},

    # ===== FOOTBALL - NETHERLANDS =====
    "fortuna-sittard-fan-token": {"symbol": "FOR", "team": "Fortuna Sittard", "league": "Eredivisie"},

    # ===== FOOTBALL - CROATIA =====
    "dinamo-zagreb-fan-token": {"symbol": "DZG", "team": "Dinamo Zagreb", "league": "HNL"},

    # ===== FOOTBALL - CYPRUS =====
    "apollon-limassol-fan-token": {"symbol": "APL", "team": "Apollon Limassol", "league": "First Division Cyprus"},

    # ===== FOOTBALL - INDONESIA =====
    "bali-united-fan-token": {"symbol": "BUFC", "team": "Bali United", "league": "Liga 1 Indonesia"},
    "persib-fan-token": {"symbol": "PERSIB", "team": "PERSIB", "league": "Liga 1 Indonesia"},

    # ===== FOOTBALL - MALAYSIA =====
    "johor-darul-tazim-fc-fan-token": {"symbol": "JDT", "team": "Johor Darul Ta'zim FC", "league": "Super Liga Malaysia"},

    # ===== FOOTBALL - OTHER =====
    "hashtag-united-fc-fan-token": {"symbol": "HASHTAG", "team": "Hashtag United FC", "league": "National League"},

    # ===== NATIONAL TEAMS =====
    "argentine-football-association-fan-token": {"symbol": "ARG", "team": "Argentina", "league": "National Team"},
    "portugal-national-team-fan-token": {"symbol": "POR", "team": "Portugal", "league": "National Team"},
    "italian-national-football-team-fan-token": {"symbol": "ITA", "team": "Italy", "league": "National Team"},

    # ===== FORMULA 1 =====
    "alfa-romeo-racing-orlen-fan-token": {"symbol": "SAUBER", "team": "Alfa Romeo Racing ORLEN", "league": "Formula 1"},
    "aston-martin-cognizant-fan-token": {"symbol": "AM", "team": "Aston Martin Cognizant", "league": "Formula 1"},

    # ===== NASCAR =====
    "roush-fenway-racing-fan-token": {"symbol": "ROUSH", "team": "Roush Fenway Racing", "league": "NASCAR"},

    # ===== MMA / FIGHTING =====
    "ufc-fan-token": {"symbol": "UFC", "team": "UFC", "league": "MMA"},
    "professional-fighters-league-fan-token": {"symbol": "PFL", "team": "Professional Fighters League", "league": "MMA"},

    # ===== RUGBY =====
    "leicester-tigers-fan-token": {"symbol": "TIGERS", "team": "Leicester Tigers", "league": "Premiership Rugby"},
    "saracens-fan-token": {"symbol": "SARRIES", "team": "Saracens", "league": "Premiership Rugby"},
    "harlequins-fan-token": {"symbol": "QUINS", "team": "Harlequins", "league": "Premiership Rugby"},
    "stade-francais-paris-fan-token": {"symbol": "SFP", "team": "Stade Français Paris", "league": "Top 14"},
    "the-sharks-fan-token": {"symbol": "SHARKS", "team": "The Sharks", "league": "United Rugby Championship"},

    # ===== TENNIS =====
    "davis-cup-fan-token": {"symbol": "DAVIS", "team": "Davis Cup", "league": "Tennis"},

    # ===== MARKET REFERENCES (for correlation analysis) =====
    "bitcoin": {"symbol": "BTC", "team": "Bitcoin", "league": "Crypto"},
    "ethereum": {"symbol": "ETH", "team": "Ethereum", "league": "Crypto"},
    "chiliz": {"symbol": "CHZ", "team": "Chiliz", "league": "Crypto"},
}


class LiveDataService:
    """Fetches live data from CoinGecko free API"""

    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 60  # 60 seconds cache

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _is_cache_valid(self) -> bool:
        if not self._cache_time:
            return False
        elapsed = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
        return elapsed < self._cache_ttl

    async def fetch_all_tokens(self) -> List[Dict[str, Any]]:
        """Fetch all fan token data from CoinGecko"""

        # Return cached data if valid
        if self._is_cache_valid() and self._cache.get("tokens"):
            return self._cache["tokens"]

        ids = ",".join(COINGECKO_IDS.keys())
        url = f"{self.base_url}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ids,
            "order": "market_cap_desc",
            "per_page": 50,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "1h,24h,7d"
        }

        try:
            async with self.session.get(url, params=params, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tokens = self._process_tokens(data)
                    self._cache["tokens"] = tokens
                    self._cache_time = datetime.now(timezone.utc)
                    return tokens
                elif resp.status == 429:
                    logger.warning("CoinGecko rate limit hit, returning cached data")
                    return self._cache.get("tokens", [])
                else:
                    logger.error(f"CoinGecko API error: {resp.status}")
                    return self._cache.get("tokens", [])
        except Exception as e:
            logger.error(f"Error fetching tokens: {e}")
            return self._cache.get("tokens", [])

    def _process_tokens(self, data: List[Dict]) -> List[Dict[str, Any]]:
        """Process CoinGecko data into our format with health scores"""
        tokens = []

        for coin in data:
            cg_id = coin.get("id")
            if cg_id not in COINGECKO_IDS:
                continue

            meta = COINGECKO_IDS[cg_id]

            # Extract data
            price = float(coin.get("current_price") or 0)
            volume_24h = float(coin.get("total_volume") or 0)
            market_cap = float(coin.get("market_cap") or 0)
            price_change_1h = float(coin.get("price_change_percentage_1h_in_currency") or 0)
            price_change_24h = float(coin.get("price_change_percentage_24h") or 0)
            price_change_7d = float(coin.get("price_change_percentage_7d") or 0)

            # Calculate health score
            health_score, health_grade = self._calculate_health_score(
                volume_24h=volume_24h,
                market_cap=market_cap,
                price_change_24h=price_change_24h,
                price_change_7d=price_change_7d,
            )

            tokens.append({
                "symbol": meta["symbol"],
                "name": coin.get("name", ""),
                "team": meta["team"],
                "league": meta["league"],
                "price": price,
                "price_change_1h": price_change_1h,
                "price_change_24h": price_change_24h,
                "price_change_7d": price_change_7d,
                "volume_24h": volume_24h,
                "market_cap": market_cap,
                "health_score": health_score,
                "health_grade": health_grade,
                "image": coin.get("image"),
                "last_updated": coin.get("last_updated"),
            })

        # Sort by market cap
        tokens.sort(key=lambda x: x["market_cap"], reverse=True)
        return tokens

    def _calculate_health_score(
        self,
        volume_24h: float,
        market_cap: float,
        price_change_24h: float,
        price_change_7d: float,
    ) -> tuple:
        """Calculate health score (0-100) and grade (A-F)"""

        # Volume score (0-35)
        if volume_24h >= 2_000_000:
            volume_score = 35
        elif volume_24h >= 1_000_000:
            volume_score = 30
        elif volume_24h >= 500_000:
            volume_score = 25
        elif volume_24h >= 100_000:
            volume_score = 15
        elif volume_24h >= 50_000:
            volume_score = 10
        else:
            volume_score = 5

        # Volume/Market Cap ratio score (0-25) - healthy is 1-5%
        if market_cap > 0:
            vol_ratio = (volume_24h / market_cap) * 100
            if 1 <= vol_ratio <= 10:
                ratio_score = 25
            elif 0.5 <= vol_ratio < 1 or 10 < vol_ratio <= 20:
                ratio_score = 20
            elif 0.1 <= vol_ratio < 0.5:
                ratio_score = 10
            else:
                ratio_score = 5
        else:
            ratio_score = 0

        # Price stability score (0-25) - moderate moves are healthy
        abs_change_24h = abs(price_change_24h)
        abs_change_7d = abs(price_change_7d)

        if abs_change_24h <= 3:
            stability_24h = 15
        elif abs_change_24h <= 5:
            stability_24h = 12
        elif abs_change_24h <= 10:
            stability_24h = 8
        else:
            stability_24h = 3

        if abs_change_7d <= 10:
            stability_7d = 10
        elif abs_change_7d <= 20:
            stability_7d = 7
        else:
            stability_7d = 3

        stability_score = stability_24h + stability_7d

        # Market cap score (0-15) - larger cap = more stable
        if market_cap >= 50_000_000:
            cap_score = 15
        elif market_cap >= 20_000_000:
            cap_score = 12
        elif market_cap >= 10_000_000:
            cap_score = 10
        elif market_cap >= 5_000_000:
            cap_score = 7
        else:
            cap_score = 3

        # Total score
        total_score = volume_score + ratio_score + stability_score + cap_score
        total_score = min(100, max(0, total_score))

        # Grade
        if total_score >= 80:
            grade = "A"
        elif total_score >= 65:
            grade = "B"
        elif total_score >= 50:
            grade = "C"
        elif total_score >= 35:
            grade = "D"
        else:
            grade = "F"

        return total_score, grade

    async def get_portfolio_overview(self) -> Dict[str, Any]:
        """Get portfolio overview with aggregated metrics (fan tokens only, excludes BTC/ETH/CHZ)"""
        all_tokens = await self.fetch_all_tokens()

        # Filter out market references (BTC, ETH, CHZ)
        tokens = [t for t in all_tokens if t.get("league") != "Crypto"]

        if not tokens:
            return {
                "total_market_cap": 0,
                "total_volume_24h": 0,
                "avg_health_score": 0,
                "tokens_count": 0,
                "tokens_grade_a": 0,
                "tokens_grade_b": 0,
                "tokens_grade_c": 0,
                "tokens_grade_d": 0,
                "tokens_grade_f": 0,
                "top_performer": None,
                "top_performer_change": None,
                "worst_performer": None,
                "worst_performer_change": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Calculate aggregates
        total_market_cap = sum(t["market_cap"] for t in tokens)
        total_volume_24h = sum(t["volume_24h"] for t in tokens)
        avg_health_score = sum(t["health_score"] for t in tokens) / len(tokens)

        # Grade counts
        grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for t in tokens:
            grade = t.get("health_grade", "F")
            grades[grade] = grades.get(grade, 0) + 1

        # Top/worst performers
        sorted_by_change = sorted(tokens, key=lambda x: x["price_change_24h"], reverse=True)
        top = sorted_by_change[0] if sorted_by_change else None
        worst = sorted_by_change[-1] if sorted_by_change else None

        return {
            "total_market_cap": total_market_cap,
            "total_volume_24h": total_volume_24h,
            "avg_health_score": round(avg_health_score, 1),
            "tokens_count": len(tokens),
            "tokens_grade_a": grades["A"],
            "tokens_grade_b": grades["B"],
            "tokens_grade_c": grades["C"],
            "tokens_grade_d": grades["D"],
            "tokens_grade_f": grades["F"],
            "top_performer": top["symbol"] if top else None,
            "top_performer_change": top["price_change_24h"] if top else None,
            "worst_performer": worst["symbol"] if worst else None,
            "worst_performer_change": worst["price_change_24h"] if worst else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_health_matrix(self) -> Dict[str, Any]:
        """Get health matrix grouped by grade (fan tokens only, excludes BTC/ETH/CHZ)"""
        tokens = await self.fetch_all_tokens()

        matrix = {"A": [], "B": [], "C": [], "D": [], "F": []}

        for t in tokens:
            # Skip market references (BTC, ETH, CHZ)
            if t.get("league") == "Crypto":
                continue

            grade = t.get("health_grade", "F")
            matrix[grade].append({
                "symbol": t["symbol"],
                "team": t["team"],
                "league": t["league"],
                "health_score": t["health_score"],
                "price_change_24h": t["price_change_24h"],
                "volume_24h": t["volume_24h"],
            })

        return {
            "matrix": matrix,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton instance
_live_service: Optional[LiveDataService] = None


async def get_live_service() -> LiveDataService:
    """Get or create singleton LiveDataService"""
    global _live_service
    if _live_service is None:
        _live_service = LiveDataService()
        _live_service.session = aiohttp.ClientSession()
    return _live_service


async def cleanup_live_service():
    """Cleanup the singleton service"""
    global _live_service
    if _live_service and _live_service.session:
        await _live_service.session.close()
        _live_service = None
