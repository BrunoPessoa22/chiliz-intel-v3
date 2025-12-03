"""
Live API Routes - Real-time data from CoinGecko
No database dependency
"""
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import aiohttp
from fastapi import APIRouter
from pydantic import BaseModel

from services.live_data import get_live_service

# API-Football configuration
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "2808882760c4bb262f1bbf3fe09861cb")
API_FOOTBALL_URL = "https://v3.football.api-sports.io"

# Team ID mappings for fan token teams (API-Football team IDs)
TEAM_IDS = {
    # Spain - La Liga
    "BAR": {"id": 529, "name": "Barcelona", "league": 140},
    "ATM": {"id": 530, "name": "Atletico Madrid", "league": 140},
    "VCF": {"id": 532, "name": "Valencia", "league": 140},
    "SEVILLA": {"id": 536, "name": "Sevilla", "league": 140},
    "RSO": {"id": 548, "name": "Real Sociedad", "league": 140},
    "LEV": {"id": 538, "name": "Levante", "league": 140},
    # England - Premier League
    "CITY": {"id": 50, "name": "Manchester City", "league": 39},
    "AFC": {"id": 42, "name": "Arsenal", "league": 39},
    "SPURS": {"id": 47, "name": "Tottenham", "league": 39},
    "EFC": {"id": 45, "name": "Everton", "league": 39},
    "AVL": {"id": 66, "name": "Aston Villa", "league": 39},
    "LUFC": {"id": 63, "name": "Leeds", "league": 39},
    "CPFC": {"id": 52, "name": "Crystal Palace", "league": 39},
    # Italy - Serie A
    "JUV": {"id": 496, "name": "Juventus", "league": 135},
    "ACM": {"id": 489, "name": "AC Milan", "league": 135},
    "ASR": {"id": 497, "name": "AS Roma", "league": 135},
    "INTER": {"id": 505, "name": "Inter", "league": 135},
    "NAP": {"id": 492, "name": "Napoli", "league": 135},
    "BFC": {"id": 500, "name": "Bologna", "league": 135},
    "UDI": {"id": 494, "name": "Udinese", "league": 135},
    # France - Ligue 1
    "PSG": {"id": 85, "name": "Paris Saint Germain", "league": 61},
    "ASM": {"id": 91, "name": "Monaco", "league": 61},
    # Portugal
    "BENFICA": {"id": 211, "name": "Benfica", "league": 94},
    # Turkey
    "GAL": {"id": 645, "name": "Galatasaray", "league": 203},
    "TRA": {"id": 611, "name": "Trabzonspor", "league": 203},
    # Brazil
    "MENGO": {"id": 127, "name": "Flamengo", "league": 71},
    "SCCP": {"id": 131, "name": "Corinthians", "league": 71},
    "GALO": {"id": 1062, "name": "Atletico Mineiro", "league": 71},
    "SPFC": {"id": 126, "name": "Sao Paulo", "league": 71},
    "VERDAO": {"id": 121, "name": "Palmeiras", "league": 71},
    "FLU": {"id": 124, "name": "Fluminense", "league": 71},
    "VASCO": {"id": 133, "name": "Vasco DA Gama", "league": 71},
    "SACI": {"id": 119, "name": "Internacional", "league": 71},
    "BAHIA": {"id": 118, "name": "Bahia", "league": 71},
    # Argentina
    "CAI": {"id": 463, "name": "Independiente", "league": 128},
    "RACING": {"id": 456, "name": "Racing Club", "league": 128},
}

router = APIRouter()


class TokenData(BaseModel):
    """Token data model"""
    symbol: str
    name: str
    team: str
    league: Optional[str]
    price: float
    price_change_1h: float
    price_change_24h: float
    price_change_7d: float
    volume_24h: float
    market_cap: float
    health_score: int
    health_grade: str


@router.get("/tokens")
async def get_live_tokens():
    """
    Get all fan tokens with live data from CoinGecko.
    Separates market references (BTC, ETH, CHZ) from actual fan tokens.
    Data is cached for 60 seconds.
    """
    service = await get_live_service()
    all_tokens = await service.fetch_all_tokens()

    # Separate market references from fan tokens
    market_references = []
    fan_tokens = []

    for token in all_tokens:
        if token.get("league") == "Crypto":
            market_references.append(token)
        else:
            fan_tokens.append(token)

    return {
        "fan_tokens": fan_tokens,
        "market_references": market_references,
        "count": len(fan_tokens),
        "market_ref_count": len(market_references),
    }


@router.get("/overview")
async def get_live_overview():
    """
    Get portfolio overview with aggregated metrics.
    Live data from CoinGecko.
    """
    service = await get_live_service()
    return await service.get_portfolio_overview()


@router.get("/health-matrix")
async def get_live_health_matrix():
    """
    Get health matrix with tokens grouped by grade.
    Live data from CoinGecko.
    """
    service = await get_live_service()
    return await service.get_health_matrix()


@router.get("/daily-brief")
async def get_live_daily_brief():
    """
    Get daily brief with key insights.
    Live data from CoinGecko.
    """
    service = await get_live_service()
    tokens = await service.fetch_all_tokens()
    overview = await service.get_portfolio_overview()

    # Sort by different metrics
    sorted_by_change = sorted(tokens, key=lambda x: abs(x["price_change_24h"]), reverse=True)
    sorted_by_volume = sorted(tokens, key=lambda x: x["volume_24h"], reverse=True)

    # Generate key points
    key_points = []

    if overview["top_performer"]:
        key_points.append(
            f"Top performer: {overview['top_performer']} ({overview['top_performer_change']:+.2f}%)"
        )

    if overview["worst_performer"]:
        key_points.append(
            f"Worst performer: {overview['worst_performer']} ({overview['worst_performer_change']:+.2f}%)"
        )

    key_points.append(f"Total market cap: ${overview['total_market_cap']:,.0f}")
    key_points.append(f"24h volume: ${overview['total_volume_24h']:,.0f}")
    key_points.append(f"Average health score: {overview['avg_health_score']:.1f}")
    key_points.append(f"Grade A tokens: {overview['tokens_grade_a']}")

    if overview['tokens_grade_d'] + overview['tokens_grade_f'] > 0:
        key_points.append(
            f"Tokens needing attention (D/F): {overview['tokens_grade_d'] + overview['tokens_grade_f']}"
        )

    return {
        "brief": {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "portfolio_summary": {
                "total_market_cap": overview["total_market_cap"],
                "total_volume_24h": overview["total_volume_24h"],
                "avg_health_score": overview["avg_health_score"],
            },
            "key_points": [p for p in key_points if p],
            "active_signals": [],  # No database, no signals yet
            "biggest_movers": [
                {
                    "symbol": t["symbol"],
                    "change_24h": t["price_change_24h"],
                    "volume_24h": t["volume_24h"],
                }
                for t in sorted_by_change[:5]
            ],
            "top_volume": [
                {
                    "symbol": t["symbol"],
                    "volume_24h": t["volume_24h"],
                    "price_change_24h": t["price_change_24h"],
                }
                for t in sorted_by_volume[:5]
            ],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/token/{symbol}")
async def get_live_token(symbol: str):
    """
    Get detailed data for a single token.
    """
    service = await get_live_service()
    tokens = await service.fetch_all_tokens()

    # Find token by symbol
    for t in tokens:
        if t["symbol"].upper() == symbol.upper():
            return {
                "token": t,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    return {
        "error": f"Token {symbol} not found",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/correlation")
async def get_live_correlation():
    """
    Get correlation analysis between fan tokens and market references (BTC, ETH, CHZ).
    Uses current price changes as proxy for correlation.
    """
    service = await get_live_service()
    tokens = await service.fetch_all_tokens()

    # Separate market references from fan tokens
    btc = next((t for t in tokens if t["symbol"] == "BTC"), None)
    eth = next((t for t in tokens if t["symbol"] == "ETH"), None)
    chz = next((t for t in tokens if t["symbol"] == "CHZ"), None)
    fan_tokens = [t for t in tokens if t["league"] != "Crypto"]

    correlations = []
    for token in fan_tokens:
        token_change = token["price_change_24h"]

        # Calculate correlation proxy (same direction = positive correlation)
        btc_corr = _calculate_correlation_proxy(token_change, btc["price_change_24h"] if btc else 0)
        eth_corr = _calculate_correlation_proxy(token_change, eth["price_change_24h"] if eth else 0)
        chz_corr = _calculate_correlation_proxy(token_change, chz["price_change_24h"] if chz else 0)

        # Determine market regime
        regime = "bullish" if token_change > 2 else "bearish" if token_change < -2 else "ranging"

        correlations.append({
            "symbol": token["symbol"],
            "team": token["team"],
            "price_change_24h": token_change,
            "correlations": {
                "btc": round(btc_corr, 2),
                "eth": round(eth_corr, 2),
                "chz": round(chz_corr, 2),
            },
            "market_regime": regime,
            "volume_spike": token["volume_24h"] > 500000,  # High volume flag
        })

    return {
        "market_references": {
            "btc": {
                "price": btc["price"] if btc else 0,
                "change_24h": btc["price_change_24h"] if btc else 0,
            },
            "eth": {
                "price": eth["price"] if eth else 0,
                "change_24h": eth["price_change_24h"] if eth else 0,
            },
            "chz": {
                "price": chz["price"] if chz else 0,
                "change_24h": chz["price_change_24h"] if chz else 0,
            },
        },
        "correlations": sorted(correlations, key=lambda x: abs(x["correlations"]["btc"]), reverse=True),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _calculate_correlation_proxy(change1: float, change2: float) -> float:
    """
    Calculate correlation proxy based on price changes.
    Same direction and magnitude = higher correlation.
    """
    if change2 == 0:
        return 0

    # Same direction
    same_direction = (change1 > 0 and change2 > 0) or (change1 < 0 and change2 < 0)

    # Magnitude similarity (0 to 1)
    ratio = min(abs(change1), abs(change2)) / max(abs(change1), abs(change2)) if max(abs(change1), abs(change2)) > 0 else 0

    # Correlation proxy: 0.5 base for same direction, scaled by ratio
    if same_direction:
        return 0.5 + (ratio * 0.5)
    else:
        return -0.5 - (ratio * 0.5)


@router.get("/whale-activity")
async def get_live_whale_activity():
    """
    Get whale activity signals based on volume and price movements.
    Detects potential large player activity.
    """
    service = await get_live_service()
    tokens = await service.fetch_all_tokens()

    whale_signals = []

    for token in tokens:
        if token["league"] == "Crypto":
            continue  # Skip market references

        volume = token["volume_24h"]
        market_cap = token["market_cap"]
        price_change = token["price_change_24h"]

        # Volume to market cap ratio (whale activity indicator)
        vol_ratio = (volume / market_cap * 100) if market_cap > 0 else 0

        # Detect potential whale activity
        signals = []

        if vol_ratio > 20:
            signals.append({
                "type": "extreme_volume",
                "description": f"Volume is {vol_ratio:.1f}% of market cap",
                "severity": "high",
            })
        elif vol_ratio > 10:
            signals.append({
                "type": "high_volume",
                "description": f"Volume is {vol_ratio:.1f}% of market cap",
                "severity": "medium",
            })

        if abs(price_change) > 10:
            signals.append({
                "type": "large_price_move",
                "description": f"Price moved {price_change:+.1f}% in 24h",
                "severity": "high" if abs(price_change) > 20 else "medium",
            })

        # Only include tokens with signals
        if signals:
            whale_signals.append({
                "symbol": token["symbol"],
                "team": token["team"],
                "price": token["price"],
                "price_change_24h": price_change,
                "volume_24h": volume,
                "market_cap": market_cap,
                "vol_mc_ratio": round(vol_ratio, 2),
                "signals": signals,
            })

    return {
        "whale_activity": sorted(whale_signals, key=lambda x: x["vol_mc_ratio"], reverse=True),
        "count": len(whale_signals),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/signals")
async def get_live_signals():
    """
    Get predictive signals based on current market data.
    Identifies opportunities and risks in real-time.
    """
    service = await get_live_service()
    tokens = await service.fetch_all_tokens()

    signals = []

    # Get market references
    btc = next((t for t in tokens if t["symbol"] == "BTC"), None)
    eth = next((t for t in tokens if t["symbol"] == "ETH"), None)
    chz = next((t for t in tokens if t["symbol"] == "CHZ"), None)

    btc_change = btc["price_change_24h"] if btc else 0
    chz_change = chz["price_change_24h"] if chz else 0

    for token in tokens:
        if token["league"] == "Crypto":
            continue

        token_signals = []

        # OPPORTUNITY SIGNALS

        # 1. Underperformer in bullish market (potential catch-up)
        if btc_change > 3 and token["price_change_24h"] < -2:
            token_signals.append({
                "type": "opportunity",
                "signal": "underperformer_in_bull",
                "title": "Lagging Behind Bull Market",
                "description": f"BTC +{btc_change:.1f}% but {token['symbol']} -{abs(token['price_change_24h']):.1f}%. Potential catch-up opportunity.",
                "confidence": 65,
                "priority": "medium",
            })

        # 2. High volume + positive momentum
        if token["volume_24h"] > 1000000 and token["price_change_24h"] > 5:
            token_signals.append({
                "type": "opportunity",
                "signal": "momentum_breakout",
                "title": "Momentum Breakout",
                "description": f"High volume (${token['volume_24h']/1000000:.1f}M) with +{token['price_change_24h']:.1f}% gain.",
                "confidence": 75,
                "priority": "high",
            })

        # 3. Outperforming CHZ (ecosystem strength)
        if chz_change < 0 and token["price_change_24h"] > 5:
            token_signals.append({
                "type": "opportunity",
                "signal": "ecosystem_outperformer",
                "title": "Outperforming Ecosystem",
                "description": f"Gaining while CHZ down. Strong individual momentum.",
                "confidence": 70,
                "priority": "medium",
            })

        # RISK SIGNALS

        # 1. Heavy sell pressure
        if token["price_change_24h"] < -10:
            token_signals.append({
                "type": "risk",
                "signal": "sell_pressure",
                "title": "Heavy Sell Pressure",
                "description": f"Down {abs(token['price_change_24h']):.1f}% in 24h. Monitor for recovery.",
                "confidence": 80,
                "priority": "high",
            })

        # 2. Low volume decline (weak support)
        if token["volume_24h"] < 50000 and token["price_change_24h"] < -5:
            token_signals.append({
                "type": "risk",
                "signal": "weak_support",
                "title": "Weak Support Level",
                "description": f"Declining on low volume. Limited buyer interest.",
                "confidence": 70,
                "priority": "medium",
            })

        # 3. Poor health score
        if token["health_score"] < 35:
            token_signals.append({
                "type": "risk",
                "signal": "poor_health",
                "title": "Poor Health Metrics",
                "description": f"Health score {token['health_score']}/100 (Grade {token['health_grade']}). Needs attention.",
                "confidence": 85,
                "priority": "high" if token["health_score"] < 25 else "medium",
            })

        # CATALYST SIGNALS (for high volume tokens)
        if token["volume_24h"] > 500000 and abs(token["price_change_1h"]) > 3:
            token_signals.append({
                "type": "catalyst",
                "signal": "recent_catalyst",
                "title": "Recent Price Catalyst",
                "description": f"Significant 1h move ({token['price_change_1h']:+.1f}%). Possible news event.",
                "confidence": 60,
                "priority": "high",
            })

        for sig in token_signals:
            signals.append({
                "symbol": token["symbol"],
                "team": token["team"],
                "league": token["league"],
                "price": token["price"],
                "price_change_24h": token["price_change_24h"],
                **sig,
            })

    # Sort by confidence and priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda x: (priority_order.get(x["priority"], 2), -x["confidence"]))

    return {
        "signals": signals,
        "summary": {
            "opportunities": len([s for s in signals if s["type"] == "opportunity"]),
            "risks": len([s for s in signals if s["type"] == "risk"]),
            "catalysts": len([s for s in signals if s["type"] == "catalyst"]),
            "total": len(signals),
        },
        "market_context": {
            "btc_24h": btc_change,
            "eth_24h": eth["price_change_24h"] if eth else 0,
            "chz_24h": chz_change,
            "market_sentiment": "bullish" if btc_change > 2 else "bearish" if btc_change < -2 else "neutral",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/fixtures")
async def get_live_fixtures():
    """
    Get upcoming fixtures for fan token teams.
    Uses API-Football for real match data.
    """
    fixtures = []

    # Get fixtures for next 7 days
    today = datetime.now(timezone.utc)
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

    headers = {
        "x-rapidapi-key": API_FOOTBALL_KEY,
        "x-rapidapi-host": "v3.football.api-sports.io"
    }

    # Group teams by league to minimize API calls
    leagues = {}
    for symbol, team_info in TEAM_IDS.items():
        league_id = team_info["league"]
        if league_id not in leagues:
            leagues[league_id] = []
        leagues[league_id].append({"symbol": symbol, **team_info})

    # Determine current season (European leagues use year of season start, e.g. 2025 for 2025-2026)
    # South American leagues use calendar year
    current_year = today.year
    current_month = today.month

    # European leagues (start in Aug/Sep) - if we're in Jan-Jun, use previous year
    european_season = current_year if current_month >= 7 else current_year - 1

    # South American leagues (calendar year)
    south_american_season = current_year

    # Map league IDs to their season format
    EUROPEAN_LEAGUES = {39, 140, 135, 61, 94, 203}  # PL, La Liga, Serie A, Ligue 1, Primeira Liga, Super Lig
    SOUTH_AMERICAN_LEAGUES = {71, 128}  # Brazil, Argentina

    try:
        async with aiohttp.ClientSession() as session:
            for league_id, teams in leagues.items():
                # Determine correct season for this league
                if league_id in SOUTH_AMERICAN_LEAGUES:
                    season = south_american_season
                else:
                    season = european_season

                # Fetch fixtures for this league
                url = f"{API_FOOTBALL_URL}/fixtures"
                params = {
                    "league": league_id,
                    "season": season,
                    "from": from_date,
                    "to": to_date,
                }

                try:
                    async with session.get(url, headers=headers, params=params, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            # Process each fixture
                            for fixture in data.get("response", []):
                                home_id = fixture["teams"]["home"]["id"]
                                away_id = fixture["teams"]["away"]["id"]

                                # Check if any of our teams is playing
                                for team in teams:
                                    if team["id"] == home_id or team["id"] == away_id:
                                        fixture_date = fixture["fixture"]["date"]
                                        fixture_dt = datetime.fromisoformat(fixture_date.replace("Z", "+00:00"))

                                        # Calculate catalyst potential (days until match)
                                        days_until = (fixture_dt - today).days
                                        catalyst_window = days_until <= 3

                                        fixtures.append({
                                            "id": fixture["fixture"]["id"],
                                            "token_symbol": team["symbol"],
                                            "team_name": team["name"],
                                            "home": {
                                                "name": fixture["teams"]["home"]["name"],
                                                "logo": fixture["teams"]["home"]["logo"],
                                                "is_token_team": team["id"] == home_id,
                                            },
                                            "away": {
                                                "name": fixture["teams"]["away"]["name"],
                                                "logo": fixture["teams"]["away"]["logo"],
                                                "is_token_team": team["id"] == away_id,
                                            },
                                            "date": fixture_date,
                                            "venue": fixture["fixture"]["venue"]["name"] if fixture["fixture"]["venue"] else None,
                                            "league": fixture["league"]["name"],
                                            "league_logo": fixture["league"]["logo"],
                                            "round": fixture["league"]["round"],
                                            "status": fixture["fixture"]["status"]["short"],
                                            "days_until": days_until,
                                            "catalyst_window": catalyst_window,
                                            "importance": _calculate_match_importance(fixture, team),
                                        })
                                        break  # Don't duplicate if both teams have tokens
                except Exception as e:
                    print(f"Error fetching fixtures for league {league_id}: {e}")
                    continue

    except Exception as e:
        print(f"Error in fixtures API: {e}")

    # Sort by date and importance
    fixtures.sort(key=lambda x: (x["date"], -x["importance"]))

    return {
        "fixtures": fixtures,
        "count": len(fixtures),
        "catalyst_matches": len([f for f in fixtures if f["catalyst_window"]]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _calculate_match_importance(fixture: dict, team: dict) -> int:
    """
    Calculate match importance for catalyst potential.
    Returns 1-10 score.
    """
    importance = 5  # Base importance

    league_round = fixture["league"]["round"] or ""

    # High importance matches
    if "Final" in league_round:
        importance += 4
    elif "Semi" in league_round:
        importance += 3
    elif "Quarter" in league_round:
        importance += 2
    elif "Champions" in fixture["league"]["name"]:
        importance += 3
    elif "Europa" in fixture["league"]["name"]:
        importance += 2

    # Derby or rivalry (detected by both teams in same league with tokens)
    home_id = fixture["teams"]["home"]["id"]
    away_id = fixture["teams"]["away"]["id"]

    # Check if opponent also has a fan token
    opponent_has_token = False
    for symbol, info in TEAM_IDS.items():
        if symbol != team["symbol"]:
            if info["id"] == home_id or info["id"] == away_id:
                opponent_has_token = True
                importance += 2  # Token vs Token match
                break

    return min(10, importance)


@router.get("/social-correlation")
async def get_social_correlation():
    """
    Get social → price correlation analysis.
    This is the CORE PoC endpoint: does social noise predict price?
    """
    from services.correlation_engine import CorrelationEngine

    try:
        engine = CorrelationEngine()
        return await engine.get_social_correlation_summary()
    except Exception as e:
        print(f"Social correlation error: {e}")
        return {
            "error": str(e),
            "tokens": [],
            "summary": {"analyzed": 0, "predictive": 0},
            "poc_answer": "Error running correlation analysis. Ensure data collection is running.",
        }


@router.get("/social-correlation/{symbol}")
async def get_token_social_correlation(symbol: str):
    """
    Get detailed social → price correlation for a specific token.
    """
    from services.correlation_engine import CorrelationEngine
    from services.database import Database

    try:
        token = await Database.fetchrow(
            "SELECT id, symbol, team FROM fan_tokens WHERE UPPER(symbol) = UPPER($1)",
            symbol
        )
        if not token:
            return {"error": f"Token {symbol} not found"}

        engine = CorrelationEngine()
        result = await engine.analyze_social_price_correlation(
            token["id"], token["symbol"], lookback_days=30
        )

        if not result:
            return {"error": "Insufficient data for correlation analysis", "symbol": symbol}

        return {
            "symbol": token["symbol"],
            "team": token["team"],
            "analysis": result,
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


@router.get("/catalysts")
async def get_live_catalysts():
    """
    Get upcoming catalysts (fixtures in the next 3 days).
    These are high-priority events that could impact token prices.
    """
    # Get all fixtures
    fixtures_data = await get_live_fixtures()

    # Filter to catalyst window only
    catalysts = [f for f in fixtures_data["fixtures"] if f["catalyst_window"]]

    # Add token data if available
    try:
        service = await get_live_service()
        tokens = await service.fetch_all_tokens()
        token_map = {t["symbol"]: t for t in tokens}

        for catalyst in catalysts:
            symbol = catalyst["token_symbol"]
            if symbol in token_map:
                token = token_map[symbol]
                catalyst["token_price"] = token["price"]
                catalyst["token_change_24h"] = token["price_change_24h"]
                catalyst["token_health"] = token["health_grade"]
    except Exception as e:
        print(f"Error enriching catalysts with token data: {e}")

    return {
        "catalysts": catalysts,
        "count": len(catalysts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
