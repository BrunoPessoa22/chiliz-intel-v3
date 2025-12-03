-- Chiliz Marketing Intelligence v3.0 - Database Schema
-- PostgreSQL (Neon) - Initial Schema

-- =====================================================
-- CORE TABLES
-- =====================================================

-- Fan Tokens
CREATE TABLE IF NOT EXISTS fan_tokens (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    team VARCHAR(100),
    league VARCHAR(50),
    country VARCHAR(50),
    coingecko_id VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Exchanges
CREATE TABLE IF NOT EXISTS exchanges (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    coingecko_id VARCHAR(100),
    priority INTEGER DEFAULT 999,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- TIME SERIES DATA
-- =====================================================

-- Price and Volume Ticks (high frequency data)
CREATE TABLE IF NOT EXISTS price_volume_ticks (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    exchange_id INTEGER REFERENCES exchanges(id),
    price DECIMAL(20, 10),
    price_change_1h DECIMAL(10, 4),
    price_change_24h DECIMAL(10, 4),
    volume_24h DECIMAL(20, 2),
    volume_base_24h DECIMAL(20, 8),
    trade_count_24h INTEGER,
    high_price DECIMAL(20, 10),
    low_price DECIMAL(20, 10),
    PRIMARY KEY (id),
    UNIQUE (time, token_id, exchange_id)
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_pvt_token_time ON price_volume_ticks(token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_pvt_time ON price_volume_ticks(time DESC);

-- Market Prices (BTC, ETH for correlation)
CREATE TABLE IF NOT EXISTS market_prices (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    symbol VARCHAR(10) NOT NULL, -- BTC, ETH
    price DECIMAL(20, 2),
    price_change_24h DECIMAL(10, 4),
    volume_24h DECIMAL(30, 2),
    market_cap DECIMAL(30, 2),
    PRIMARY KEY (id),
    UNIQUE (time, symbol)
);

CREATE INDEX IF NOT EXISTS idx_mp_symbol_time ON market_prices(symbol, time DESC);

-- Spread Data
CREATE TABLE IF NOT EXISTS spread_snapshots (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    exchange_id INTEGER REFERENCES exchanges(id),
    bid_price DECIMAL(20, 10),
    ask_price DECIMAL(20, 10),
    spread_bps DECIMAL(10, 4), -- Basis points
    mid_price DECIMAL(20, 10),
    PRIMARY KEY (id),
    UNIQUE (time, token_id, exchange_id)
);

CREATE INDEX IF NOT EXISTS idx_ss_token_time ON spread_snapshots(token_id, time DESC);

-- Liquidity Data
CREATE TABLE IF NOT EXISTS liquidity_snapshots (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    exchange_id INTEGER REFERENCES exchanges(id),
    bid_depth_1pct DECIMAL(20, 2), -- Liquidity within 1% of mid
    ask_depth_1pct DECIMAL(20, 2),
    bid_depth_2pct DECIMAL(20, 2),
    ask_depth_2pct DECIMAL(20, 2),
    order_book_imbalance DECIMAL(10, 4),
    PRIMARY KEY (id),
    UNIQUE (time, token_id, exchange_id)
);

CREATE INDEX IF NOT EXISTS idx_ls_token_time ON liquidity_snapshots(token_id, time DESC);

-- Holder Data (on-chain)
CREATE TABLE IF NOT EXISTS holder_snapshots (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    total_holders INTEGER,
    holder_change_24h INTEGER,
    top_10_percentage DECIMAL(10, 4),
    whale_count INTEGER, -- Holders with >1% supply
    PRIMARY KEY (id),
    UNIQUE (time, token_id)
);

CREATE INDEX IF NOT EXISTS idx_hs_token_time ON holder_snapshots(token_id, time DESC);

-- =====================================================
-- SOCIAL DATA
-- =====================================================

-- Social Metrics from X/Twitter
CREATE TABLE IF NOT EXISTS social_metrics (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    tweet_count_24h INTEGER,
    mention_count_24h INTEGER,
    engagement_total INTEGER,
    sentiment_score DECIMAL(5, 4), -- 0-1 where 0.5 is neutral
    positive_count INTEGER,
    negative_count INTEGER,
    neutral_count INTEGER,
    influencer_mentions INTEGER,
    PRIMARY KEY (id),
    UNIQUE (time, token_id)
);

CREATE INDEX IF NOT EXISTS idx_sm_token_time ON social_metrics(token_id, time DESC);

-- =====================================================
-- AGGREGATED METRICS
-- =====================================================

-- Aggregated Token Metrics (5-min buckets)
CREATE TABLE IF NOT EXISTS token_metrics_aggregated (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    vwap_price DECIMAL(20, 10),
    total_volume_24h DECIMAL(20, 2),
    price_change_1h DECIMAL(10, 4),
    price_change_24h DECIMAL(10, 4),
    price_change_7d DECIMAL(10, 4),
    avg_spread_bps DECIMAL(10, 4),
    total_liquidity_1pct DECIMAL(20, 2),
    total_holders INTEGER,
    holder_change_24h INTEGER,
    active_exchanges INTEGER,
    market_cap DECIMAL(30, 2),
    PRIMARY KEY (id),
    UNIQUE (time, token_id)
);

CREATE INDEX IF NOT EXISTS idx_tma_token_time ON token_metrics_aggregated(token_id, time DESC);

-- =====================================================
-- HEALTH SCORES
-- =====================================================

-- Token Health Scores
CREATE TABLE IF NOT EXISTS token_health_scores (
    id BIGSERIAL,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    overall_score INTEGER, -- 0-100
    grade VARCHAR(1), -- A, B, C, D, F
    volume_score INTEGER,
    liquidity_score INTEGER,
    spread_score INTEGER,
    holder_score INTEGER,
    stability_score INTEGER,
    trend VARCHAR(20), -- improving, stable, declining
    PRIMARY KEY (id),
    UNIQUE (time, token_id)
);

CREATE INDEX IF NOT EXISTS idx_ths_token_time ON token_health_scores(token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ths_grade ON token_health_scores(grade, time DESC);

-- =====================================================
-- CORRELATION ANALYSIS
-- =====================================================

-- Correlation Analysis Results
CREATE TABLE IF NOT EXISTS correlation_analysis (
    id BIGSERIAL,
    token_id INTEGER REFERENCES fan_tokens(id),
    analysis_date DATE NOT NULL,
    lookback_days INTEGER NOT NULL,
    price_volume_corr DECIMAL(6, 4),
    price_volume_lag INTEGER, -- Days
    price_holders_corr DECIMAL(6, 4),
    price_holders_lag INTEGER,
    volume_holders_corr DECIMAL(6, 4),
    spread_price_corr DECIMAL(6, 4),
    liquidity_volume_corr DECIMAL(6, 4),
    btc_correlation DECIMAL(6, 4),
    eth_correlation DECIMAL(6, 4),
    social_price_corr DECIMAL(6, 4), -- Twitter sentiment vs price
    market_regime VARCHAR(20), -- bullish, bearish, ranging
    PRIMARY KEY (id),
    UNIQUE (token_id, analysis_date, lookback_days)
);

CREATE INDEX IF NOT EXISTS idx_ca_token_date ON correlation_analysis(token_id, analysis_date DESC);

-- =====================================================
-- ALERTS & SIGNALS
-- =====================================================

-- Market Signals
CREATE TABLE IF NOT EXISTS market_signals (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    token_id INTEGER REFERENCES fan_tokens(id),
    signal_type VARCHAR(50) NOT NULL, -- volume_spike, price_breakout, whale_accumulation, social_surge
    priority VARCHAR(20), -- critical, high, medium, low
    title VARCHAR(200),
    description TEXT,
    metrics JSONB, -- Additional signal data
    is_active BOOLEAN DEFAULT TRUE,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_ms_token_active ON market_signals(token_id, is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ms_type_active ON market_signals(signal_type, is_active, created_at DESC);

-- =====================================================
-- SPORTS DATA
-- =====================================================

-- Match Fixtures
CREATE TABLE IF NOT EXISTS match_fixtures (
    id BIGSERIAL PRIMARY KEY,
    external_id VARCHAR(50), -- ID from API-Football
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    home_token_id INTEGER REFERENCES fan_tokens(id),
    away_token_id INTEGER REFERENCES fan_tokens(id),
    league VARCHAR(100),
    match_date TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20), -- scheduled, live, finished
    home_score INTEGER,
    away_score INTEGER,
    is_high_impact BOOLEAN DEFAULT FALSE, -- Derby, final, etc.
    impact_description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (external_id)
);

CREATE INDEX IF NOT EXISTS idx_mf_date ON match_fixtures(match_date);
CREATE INDEX IF NOT EXISTS idx_mf_tokens ON match_fixtures(home_token_id, away_token_id);

-- =====================================================
-- INITIAL SEED DATA
-- =====================================================

-- Seed exchanges
INSERT INTO exchanges (code, name, coingecko_id, priority) VALUES
    ('binance', 'Binance', 'binance', 1),
    ('okx', 'OKX', 'okx', 2),
    ('upbit', 'Upbit', 'upbit', 3),
    ('paribu', 'Paribu', 'paribu', 4),
    ('bithumb', 'Bithumb', 'bithumb', 5),
    ('coinbase', 'Coinbase', 'gdax', 6),
    ('kraken', 'Kraken', 'kraken', 7),
    ('kucoin', 'KuCoin', 'kucoin', 8),
    ('bybit', 'Bybit', 'bybit_spot', 9),
    ('gate', 'Gate.io', 'gate', 10),
    ('htx', 'HTX (Huobi)', 'huobi', 11),
    ('bitfinex', 'Bitfinex', 'bitfinex', 12),
    ('mexc', 'MEXC', 'mxc', 13)
ON CONFLICT (code) DO NOTHING;

-- Seed fan tokens (complete 2025 list)
INSERT INTO fan_tokens (symbol, name, team, league, country, coingecko_id) VALUES
    -- Native
    ('CHZ', 'Chiliz', 'Chiliz', NULL, NULL, 'chiliz'),
    -- Esports
    ('OG', 'OG Fan Token', 'OG Esports', 'Esports', NULL, 'og-fan-token'),
    ('NAVI', 'Natus Vincere Fan Token', 'Natus Vincere', 'Esports', NULL, 'natus-vincere-fan-token'),
    ('ALL', 'Alliance Fan Token', 'Alliance', 'Esports', NULL, 'alliance-fan-token'),
    ('TH', 'Team Heretics Fan Token', 'Team Heretics', 'Esports', NULL, 'team-heretics-fan-token'),
    -- La Liga
    ('BAR', 'FC Barcelona Fan Token', 'FC Barcelona', 'La Liga', 'Spain', 'fc-barcelona-fan-token'),
    ('ATM', 'Atlético de Madrid Fan Token', 'Atlético de Madrid', 'La Liga', 'Spain', 'atletico-madrid'),
    ('VCF', 'Valencia CF Fan Token', 'Valencia CF', 'La Liga', 'Spain', 'valencia-cf-fan-token'),
    ('SEVILLA', 'Sevilla Fan Token', 'Sevilla FC', 'La Liga', 'Spain', 'sevilla-fan-token'),
    -- Premier League
    ('CITY', 'Manchester City Fan Token', 'Manchester City', 'Premier League', 'England', 'manchester-city-fan-token'),
    ('AFC', 'Arsenal Fan Token', 'Arsenal FC', 'Premier League', 'England', 'arsenal-fan-token'),
    ('SPURS', 'Tottenham Hotspur Fan Token', 'Tottenham Hotspur', 'Premier League', 'England', 'tottenham-hotspur-fc-fan-token'),
    ('EFC', 'Everton Fan Token', 'Everton FC', 'Premier League', 'England', 'everton-fan-token'),
    ('AVL', 'Aston Villa Fan Token', 'Aston Villa', 'Premier League', 'England', 'aston-villa-fan-token'),
    -- Serie A
    ('JUV', 'Juventus Fan Token', 'Juventus', 'Serie A', 'Italy', 'juventus-fan-token'),
    ('ACM', 'AC Milan Fan Token', 'AC Milan', 'Serie A', 'Italy', 'ac-milan-fan-token'),
    ('ASR', 'AS Roma Fan Token', 'AS Roma', 'Serie A', 'Italy', 'as-roma-fan-token'),
    ('INTER', 'Inter Milan Fan Token', 'Inter Milan', 'Serie A', 'Italy', 'inter-milan-fan-token'),
    ('NAP', 'Napoli Fan Token', 'SSC Napoli', 'Serie A', 'Italy', 'napoli-fan-token'),
    -- Ligue 1
    ('PSG', 'Paris Saint-Germain Fan Token', 'Paris Saint-Germain', 'Ligue 1', 'France', 'paris-saint-germain-fan-token'),
    ('ASM', 'AS Monaco Fan Token', 'AS Monaco', 'Ligue 1', 'France', 'as-monaco-fan-token'),
    -- Portugal
    ('BENFICA', 'SL Benfica Fan Token', 'SL Benfica', 'Primeira Liga', 'Portugal', 'sl-benfica-fan-token'),
    -- Turkey
    ('GAL', 'Galatasaray Fan Token', 'Galatasaray', 'Super Lig', 'Turkey', 'galatasaray-fan-token'),
    ('TRA', 'Trabzonspor Fan Token', 'Trabzonspor', 'Super Lig', 'Turkey', 'trabzonspor-fan-token'),
    ('GOZ', 'Göztepe Fan Token', 'Göztepe S.K.', 'Super Lig', 'Turkey', 'goztepe-s-k-fan-token'),
    ('SAM', 'Samsunspor Fan Token', 'Samsunspor', 'Super Lig', 'Turkey', 'samsunspor-fan-token'),
    ('ALA', 'Alanyaspor Fan Token', 'Alanyaspor', 'Super Lig', 'Turkey', 'alanyaspor-fan-token'),
    ('IBFK', 'İstanbul Başakşehir Fan Token', 'İstanbul Başakşehir', 'Super Lig', 'Turkey', 'istanbul-basaksehir-fan-token'),
    -- Brazil
    ('MENGO', 'Flamengo Fan Token', 'Flamengo', 'Serie A Brazil', 'Brazil', 'flamengo-fan-token'),
    ('SCCP', 'Corinthians Fan Token', 'S.C. Corinthians', 'Serie A Brazil', 'Brazil', 's-c-corinthians-fan-token'),
    ('GALO', 'Atlético Mineiro Fan Token', 'Atlético Mineiro', 'Serie A Brazil', 'Brazil', 'clube-atletico-mineiro-fan-token'),
    ('SPFC', 'São Paulo FC Fan Token', 'São Paulo FC', 'Serie A Brazil', 'Brazil', 'sao-paulo-fc-fan-token'),
    ('VERDAO', 'Palmeiras Fan Token', 'SE Palmeiras', 'Serie A Brazil', 'Brazil', 'palmeiras-fan-token'),
    ('FLU', 'Fluminense Fan Token', 'Fluminense FC', 'Serie A Brazil', 'Brazil', 'fluminense-fc-fan-token'),
    ('VASCO', 'Vasco da Gama Fan Token', 'Vasco da Gama', 'Serie A Brazil', 'Brazil', 'vasco-da-gama-fan-token'),
    ('SACI', 'Internacional Fan Token', 'SC Internacional', 'Serie A Brazil', 'Brazil', 'sc-internacional-fan-token'),
    ('BAHIA', 'EC Bahia Fan Token', 'EC Bahia', 'Serie A Brazil', 'Brazil', 'esporte-clube-bahia-fan-token'),
    -- Argentina
    ('CAI', 'Independiente Fan Token', 'Club Atlético Independiente', 'Primera Division', 'Argentina', 'club-atletico-independiente'),
    -- National Teams
    ('ARG', 'Argentina Fan Token', 'Argentina', 'National Team', 'Argentina', 'argentine-football-association-fan-token'),
    ('POR', 'Portugal Fan Token', 'Portugal', 'National Team', 'Portugal', 'portugal-national-team-fan-token'),
    ('ITA', 'Italy Fan Token', 'Italy', 'National Team', 'Italy', 'italian-national-football-team-fan-token'),
    -- Formula 1
    ('SAUBER', 'Alfa Romeo Racing Fan Token', 'Alfa Romeo Racing ORLEN', 'Formula 1', NULL, 'alfa-romeo-racing-orlen-fan-token'),
    ('AM', 'Aston Martin F1 Fan Token', 'Aston Martin Cognizant', 'Formula 1', NULL, 'aston-martin-cognizant-fan-token'),
    -- MMA
    ('UFC', 'UFC Fan Token', 'UFC', 'MMA', NULL, 'ufc-fan-token'),
    ('PFL', 'PFL Fan Token', 'Professional Fighters League', 'MMA', NULL, 'professional-fighters-league-fan-token'),
    -- Other
    ('LEG', 'Legia Warsaw Fan Token', 'Legia Warsaw', 'Ekstraklasa', 'Poland', 'legia-warsaw-fan-token'),
    ('YBO', 'Young Boys Fan Token', 'BSC Young Boys', 'Swiss Super League', 'Switzerland', 'young-boys-fan-token'),
    ('STV', 'Sint-Truidense Fan Token', 'Sint-Truidense VV', 'Belgian Pro League', 'Belgium', 'sint-truidense-voetbalvereniging-fan-token'),
    ('TIGRES', 'Tigres Fan Token', 'Tigres UANL', 'Liga MX', 'Mexico', 'tigres-fan-token'),
    ('UDI', 'Udinese Fan Token', 'Udinese Calcio', 'Serie A', 'Italy', 'udinese-calcio-fan-token')
ON CONFLICT (symbol) DO UPDATE SET
    coingecko_id = EXCLUDED.coingecko_id,
    team = EXCLUDED.team,
    league = EXCLUDED.league;
