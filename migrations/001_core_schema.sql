-- ============================================================================
-- CHILIZ MARKETING INTELLIGENCE v3.0 - CORE DATABASE SCHEMA
-- PostgreSQL (Railway compatible)
-- ============================================================================

-- ============================================================================
-- REFERENCE TABLES
-- ============================================================================

-- Fan tokens master list
CREATE TABLE IF NOT EXISTS fan_tokens (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    team VARCHAR(100) NOT NULL,
    league VARCHAR(100),
    country VARCHAR(50),

    -- Contract addresses
    chiliz_chain_address VARCHAR(66),

    -- External IDs
    coingecko_id VARCHAR(50),

    -- Supply info
    total_supply DECIMAL(24,8),
    circulating_supply DECIMAL(24,8),

    -- Metadata
    launch_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert all fan tokens
INSERT INTO fan_tokens (symbol, name, team, league, country, coingecko_id) VALUES
('CHZ', 'Chiliz', 'Chiliz', NULL, NULL, 'chiliz'),
('BAR', 'FC Barcelona Fan Token', 'FC Barcelona', 'La Liga', 'Spain', 'fc-barcelona-fan-token'),
('PSG', 'Paris Saint-Germain Fan Token', 'Paris Saint-Germain', 'Ligue 1', 'France', 'paris-saint-germain-fan-token'),
('JUV', 'Juventus Fan Token', 'Juventus', 'Serie A', 'Italy', 'juventus-fan-token'),
('ATM', 'Atlético de Madrid Fan Token', 'Atlético de Madrid', 'La Liga', 'Spain', 'atletico-madrid'),
('ACM', 'AC Milan Fan Token', 'AC Milan', 'Serie A', 'Italy', 'ac-milan-fan-token'),
('ASR', 'AS Roma Fan Token', 'AS Roma', 'Serie A', 'Italy', 'as-roma-fan-token'),
('CITY', 'Manchester City Fan Token', 'Manchester City', 'Premier League', 'England', 'manchester-city-fan-token'),
('LAZIO', 'Lazio Fan Token', 'SS Lazio', 'Serie A', 'Italy', 'lazio-fan-token'),
('PORTO', 'FC Porto Fan Token', 'FC Porto', 'Primeira Liga', 'Portugal', 'fc-porto'),
('GAL', 'Galatasaray Fan Token', 'Galatasaray', 'Süper Lig', 'Turkey', 'galatasaray-fan-token'),
('INTER', 'Inter Milan Fan Token', 'Inter Milan', 'Serie A', 'Italy', 'inter-milan-fan-token'),
('NAP', 'Napoli Fan Token', 'SSC Napoli', 'Serie A', 'Italy', 'napoli-fan-token'),
('OG', 'OG Fan Token', 'OG Esports', 'Esports', NULL, 'og-fan-token'),
('SANTOS', 'Santos FC Fan Token', 'Santos FC', 'Série A', 'Brazil', 'santos-fc-fan-token'),
('ALPINE', 'Alpine F1 Team Fan Token', 'Alpine F1', 'Formula 1', 'France', 'alpine-f1-team-fan-token')
ON CONFLICT (symbol) DO NOTHING;

-- Exchanges we track
CREATE TABLE IF NOT EXISTS exchanges (
    id SERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50),
    exchange_type VARCHAR(20) DEFAULT 'CEX',

    -- CoinGecko ID for data aggregation
    coingecko_id VARCHAR(50),

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    priority INT DEFAULT 10,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert exchanges (ordered by fan token volume importance)
INSERT INTO exchanges (code, name, country, coingecko_id, priority) VALUES
('binance', 'Binance', 'Global', 'binance', 1),
('okx', 'OKX', 'Seychelles', 'okx', 2),
('upbit', 'Upbit', 'South Korea', 'upbit', 3),
('paribu', 'Paribu', 'Turkey', 'paribu', 4),
('bithumb', 'Bithumb', 'South Korea', 'bithumb', 5),
('coinbase', 'Coinbase', 'USA', 'gdax', 6),
('kraken', 'Kraken', 'USA', 'kraken', 7),
('kucoin', 'KuCoin', 'Seychelles', 'kucoin', 8),
('bybit', 'Bybit', 'Dubai', 'bybit_spot', 9),
('gate', 'Gate.io', 'Cayman Islands', 'gate', 10),
('htx', 'HTX (Huobi)', 'Seychelles', 'huobi', 11),
('bitfinex', 'Bitfinex', 'Hong Kong', 'bitfinex', 12),
('mexc', 'MEXC', 'Seychelles', 'mxc', 13),
('chiliz_dex', 'Kayen Swap (Chiliz DEX)', 'Chiliz Chain', NULL, 14)
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- TIME-SERIES TABLES (FIVE PILLARS)
-- ============================================================================

-- PILLAR 1 & 2: Price and Volume (per exchange)
CREATE TABLE IF NOT EXISTS price_volume_ticks (
    time TIMESTAMPTZ NOT NULL,
    token_id INT NOT NULL REFERENCES fan_tokens(id),
    exchange_id INT NOT NULL REFERENCES exchanges(id),

    -- Price data
    price DECIMAL(18,8) NOT NULL,
    price_change_1h DECIMAL(10,4),
    price_change_24h DECIMAL(10,4),

    -- Volume data
    volume_24h DECIMAL(18,2),
    volume_base_24h DECIMAL(18,8),
    trade_count_24h INT,

    -- OHLC for the period
    high_price DECIMAL(18,8),
    low_price DECIMAL(18,8),

    PRIMARY KEY (time, token_id, exchange_id)
);

-- PILLAR 3: Holder data (on-chain, Chiliz Chain)
CREATE TABLE IF NOT EXISTS holder_snapshots (
    time TIMESTAMPTZ NOT NULL,
    token_id INT NOT NULL REFERENCES fan_tokens(id),

    -- Core holder metrics
    total_holders INT NOT NULL,
    holder_change_24h INT,
    holder_change_7d INT,

    -- Distribution metrics
    top_10_percentage DECIMAL(6,4),
    top_50_percentage DECIMAL(6,4),
    top_100_percentage DECIMAL(6,4),

    -- Wallet size distribution
    wallets_micro INT,
    wallets_small INT,
    wallets_medium INT,
    wallets_large INT,
    wallets_whale INT,

    -- Concentration metrics
    gini_coefficient DECIMAL(6,4),

    PRIMARY KEY (time, token_id)
);

-- PILLAR 4: Spread data (per exchange)
CREATE TABLE IF NOT EXISTS spread_ticks (
    time TIMESTAMPTZ NOT NULL,
    token_id INT NOT NULL REFERENCES fan_tokens(id),
    exchange_id INT NOT NULL REFERENCES exchanges(id),

    -- Best bid/ask
    best_bid DECIMAL(18,8),
    best_ask DECIMAL(18,8),

    -- Spread calculations
    spread_absolute DECIMAL(18,8),
    spread_percentage DECIMAL(10,6),
    spread_bps DECIMAL(10,4),

    -- Mid price
    mid_price DECIMAL(18,8),

    PRIMARY KEY (time, token_id, exchange_id)
);

-- PILLAR 5: Liquidity/Order book depth (per exchange)
CREATE TABLE IF NOT EXISTS liquidity_snapshots (
    time TIMESTAMPTZ NOT NULL,
    token_id INT NOT NULL REFERENCES fan_tokens(id),
    exchange_id INT NOT NULL REFERENCES exchanges(id),

    -- Depth at various levels (USD value)
    bid_depth_1pct DECIMAL(18,2),
    ask_depth_1pct DECIMAL(18,2),
    bid_depth_2pct DECIMAL(18,2),
    ask_depth_2pct DECIMAL(18,2),
    bid_depth_5pct DECIMAL(18,2),
    ask_depth_5pct DECIMAL(18,2),

    -- Total visible liquidity
    total_bid_depth DECIMAL(18,2),
    total_ask_depth DECIMAL(18,2),

    -- Slippage estimates
    slippage_buy_1k DECIMAL(10,4),
    slippage_buy_10k DECIMAL(10,4),
    slippage_buy_50k DECIMAL(10,4),
    slippage_sell_1k DECIMAL(10,4),
    slippage_sell_10k DECIMAL(10,4),
    slippage_sell_50k DECIMAL(10,4),

    -- Order book imbalance
    book_imbalance DECIMAL(6,4),

    PRIMARY KEY (time, token_id, exchange_id)
);

-- ============================================================================
-- AGGREGATED TABLES
-- ============================================================================

-- Aggregated metrics across all exchanges
CREATE TABLE IF NOT EXISTS token_metrics_aggregated (
    time TIMESTAMPTZ NOT NULL,
    token_id INT NOT NULL REFERENCES fan_tokens(id),

    -- Price (volume-weighted across exchanges)
    vwap_price DECIMAL(18,8),
    price_change_1h DECIMAL(10,4),
    price_change_24h DECIMAL(10,4),
    price_change_7d DECIMAL(10,4),

    -- Volume (sum across exchanges)
    total_volume_24h DECIMAL(18,2),
    total_trade_count_24h INT,

    -- Market cap
    market_cap DECIMAL(18,2),

    -- Holders
    total_holders INT,
    holder_change_24h INT,

    -- Liquidity (sum across exchanges)
    total_liquidity_1pct DECIMAL(18,2),

    -- Average spread (weighted by volume)
    avg_spread_bps DECIMAL(10,4),

    -- Health score
    health_score INT,
    health_grade VARCHAR(2),

    -- Number of active exchanges
    active_exchanges INT,

    PRIMARY KEY (time, token_id)
);

-- ============================================================================
-- SOCIAL & SIGNALS TABLES
-- ============================================================================

-- X/Twitter social data
CREATE TABLE IF NOT EXISTS social_metrics (
    time TIMESTAMPTZ NOT NULL,
    token_id INT NOT NULL REFERENCES fan_tokens(id),

    -- Twitter/X metrics
    tweet_count_24h INT,
    mention_count_24h INT,
    engagement_total INT,
    sentiment_score DECIMAL(5,4),
    positive_count INT,
    negative_count INT,
    neutral_count INT,

    -- Top influencers engagement
    influencer_mentions INT,

    PRIMARY KEY (time, token_id)
);

-- Correlation analysis results
CREATE TABLE IF NOT EXISTS correlation_analysis (
    id SERIAL PRIMARY KEY,
    token_id INT NOT NULL REFERENCES fan_tokens(id),
    analysis_date DATE NOT NULL,
    lookback_days INT NOT NULL,

    -- Price-Volume correlation
    price_volume_corr DECIMAL(6,4),
    price_volume_lag INT,

    -- Price-Holders correlation
    price_holders_corr DECIMAL(6,4),
    price_holders_lag INT,

    -- Volume-Holders correlation
    volume_holders_corr DECIMAL(6,4),

    -- Spread-Price correlation
    spread_price_corr DECIMAL(6,4),

    -- Liquidity-Volume correlation
    liquidity_volume_corr DECIMAL(6,4),

    -- BTC correlation
    btc_correlation DECIMAL(6,4),

    -- Market regime at time of analysis
    market_regime VARCHAR(20),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(token_id, analysis_date, lookback_days)
);

-- Predictive signals
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    token_id INT NOT NULL REFERENCES fan_tokens(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    signal_type VARCHAR(50) NOT NULL,
    direction VARCHAR(10),
    confidence DECIMAL(4,2),

    -- Signal details
    title VARCHAR(200),
    description TEXT,
    factors JSONB,

    -- Time horizon
    time_horizon VARCHAR(20),

    -- Outcome tracking
    is_resolved BOOLEAN DEFAULT FALSE,
    actual_outcome VARCHAR(20),
    resolved_at TIMESTAMPTZ,

    -- Management relevance
    management_priority VARCHAR(10),
    suggested_action TEXT
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_price_volume_token_time ON price_volume_ticks (token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_price_volume_exchange ON price_volume_ticks (exchange_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_holders_token_time ON holder_snapshots (token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_spread_token_time ON spread_ticks (token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_liquidity_token_time ON liquidity_snapshots (token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_aggregated_token_time ON token_metrics_aggregated (token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_token_created ON signals (token_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_token_time ON social_metrics (token_id, time DESC);

-- ============================================================================
-- AI MANAGEMENT ASSISTANT TABLES
-- ============================================================================

-- Scheduled reports configuration
CREATE TABLE IF NOT EXISTS scheduled_reports (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Schedule (cron-style)
    schedule_cron VARCHAR(50) NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',

    -- Report configuration
    report_type VARCHAR(50) NOT NULL,
    parameters JSONB DEFAULT '{}',

    -- Delivery
    delivery_channel VARCHAR(20) NOT NULL, -- 'slack', 'email', 'dashboard'
    delivery_config JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Saved queries for quick access
CREATE TABLE IF NOT EXISTS saved_queries (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Query configuration
    query_type VARCHAR(50) NOT NULL,
    natural_language_query TEXT NOT NULL,
    sql_template TEXT,
    parameters JSONB DEFAULT '{}',

    -- Usage tracking
    use_count INT DEFAULT 0,
    last_used_at TIMESTAMPTZ,

    -- Access
    is_public BOOLEAN DEFAULT TRUE,
    created_by VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert rules configuration
CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Trigger conditions
    metric VARCHAR(50) NOT NULL,
    condition VARCHAR(20) NOT NULL, -- 'gt', 'lt', 'eq', 'change_pct'
    threshold DECIMAL(18,4) NOT NULL,
    token_filter JSONB, -- null = all tokens, or specific token IDs

    -- Alert configuration
    severity VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    cooldown_minutes INT DEFAULT 60,

    -- Delivery
    delivery_channel VARCHAR(20) NOT NULL,
    delivery_config JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered_at TIMESTAMPTZ,
    trigger_count INT DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI assistant conversation history
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,

    -- Message
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,

    -- Metadata
    tokens_used INT,
    model_used VARCHAR(50),
    response_time_ms INT,

    -- Context used
    context_queries JSONB, -- SQL queries executed
    context_data JSONB, -- Data retrieved

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Query analytics for improving the assistant
CREATE TABLE IF NOT EXISTS query_analytics (
    id SERIAL PRIMARY KEY,

    -- Query info
    natural_language_query TEXT NOT NULL,
    interpreted_intent VARCHAR(100),
    sql_generated TEXT,

    -- Execution
    execution_time_ms INT,
    rows_returned INT,
    was_successful BOOLEAN,
    error_message TEXT,

    -- User feedback
    user_rating INT, -- 1-5
    user_feedback TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-built management queries
CREATE TABLE IF NOT EXISTS prebuilt_queries (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Natural language patterns that trigger this query
    trigger_patterns TEXT[] NOT NULL,

    -- SQL template
    sql_template TEXT NOT NULL,

    -- Response formatting
    response_template TEXT,
    chart_type VARCHAR(30),

    -- Ordering
    display_order INT DEFAULT 0,

    is_active BOOLEAN DEFAULT TRUE
);

-- Insert pre-built management queries
INSERT INTO prebuilt_queries (category, name, description, trigger_patterns, sql_template, response_template, chart_type) VALUES
('overview', 'Portfolio Performance', 'Overall fan token portfolio performance',
 ARRAY['how is the portfolio', 'portfolio performance', 'overall performance', 'how are we doing'],
 'SELECT symbol, vwap_price, price_change_24h, total_volume_24h, health_score FROM token_metrics_aggregated tma JOIN fan_tokens ft ON tma.token_id = ft.id WHERE time = (SELECT MAX(time) FROM token_metrics_aggregated) ORDER BY total_volume_24h DESC',
 'Here''s the current portfolio performance across all fan tokens:',
 'table'),

('performance', 'Top Performers', 'Best performing tokens by price change',
 ARRAY['top performers', 'best performers', 'which tokens are up', 'winners today'],
 'SELECT symbol, team, price_change_24h, total_volume_24h FROM token_metrics_aggregated tma JOIN fan_tokens ft ON tma.token_id = ft.id WHERE time = (SELECT MAX(time) FROM token_metrics_aggregated) ORDER BY price_change_24h DESC LIMIT 5',
 'Top performing fan tokens in the last 24 hours:',
 'bar'),

('performance', 'Worst Performers', 'Worst performing tokens by price change',
 ARRAY['worst performers', 'losers', 'which tokens are down', 'underperformers'],
 'SELECT symbol, team, price_change_24h, total_volume_24h FROM token_metrics_aggregated tma JOIN fan_tokens ft ON tma.token_id = ft.id WHERE time = (SELECT MAX(time) FROM token_metrics_aggregated) ORDER BY price_change_24h ASC LIMIT 5',
 'Tokens that need attention (worst 24h performance):',
 'bar'),

('liquidity', 'Liquidity Health', 'Current liquidity across all tokens',
 ARRAY['liquidity health', 'market depth', 'how is liquidity', 'can we execute large trades'],
 'SELECT symbol, total_liquidity_1pct, avg_spread_bps, active_exchanges FROM token_metrics_aggregated tma JOIN fan_tokens ft ON tma.token_id = ft.id WHERE time = (SELECT MAX(time) FROM token_metrics_aggregated) ORDER BY total_liquidity_1pct DESC',
 'Liquidity overview across fan tokens:',
 'table'),

('holders', 'Holder Growth', 'Holder count changes',
 ARRAY['holder growth', 'new holders', 'holder changes', 'community growth'],
 'SELECT symbol, total_holders, holder_change_24h, holder_change_7d FROM holder_snapshots hs JOIN fan_tokens ft ON hs.token_id = ft.id WHERE time = (SELECT MAX(time) FROM holder_snapshots) ORDER BY holder_change_24h DESC',
 'Holder growth across fan tokens:',
 'bar'),

('alerts', 'Active Alerts', 'Current alerts and signals',
 ARRAY['any alerts', 'active signals', 'what should I know', 'urgent items'],
 'SELECT ft.symbol, s.signal_type, s.title, s.confidence, s.management_priority FROM signals s JOIN fan_tokens ft ON s.token_id = ft.id WHERE s.is_resolved = FALSE AND s.created_at > NOW() - INTERVAL ''24 hours'' ORDER BY s.created_at DESC',
 'Active alerts requiring attention:',
 'table')
ON CONFLICT DO NOTHING;

-- Indexes for assistant tables
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations (session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_query_analytics_created ON query_analytics (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_rules_active ON alert_rules (is_active, metric);
CREATE INDEX IF NOT EXISTS idx_prebuilt_queries_category ON prebuilt_queries (category, is_active);
