-- Chiliz Marketing Intelligence v3.0 - Whale Tracking Schema
-- Tracks CEX and DEX whale transactions in real-time

-- =====================================================
-- WHALE TRANSACTIONS TABLE
-- =====================================================

-- CEX Whale Transactions (from WebSocket feeds)
CREATE TABLE IF NOT EXISTS cex_whale_transactions (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    token_id INTEGER REFERENCES fan_tokens(id),
    exchange_id INTEGER REFERENCES exchanges(id),
    symbol VARCHAR(20) NOT NULL,
    exchange_name VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL, -- 'buy' or 'sell'
    price DECIMAL(20, 10) NOT NULL,
    quantity DECIMAL(30, 8) NOT NULL,
    value_usd DECIMAL(20, 2) NOT NULL,
    is_aggressive BOOLEAN DEFAULT FALSE, -- Taker order (market order)
    trade_id VARCHAR(100), -- Exchange trade ID
    raw_data JSONB -- Full trade data for debugging
);

CREATE INDEX IF NOT EXISTS idx_cwt_token_time ON cex_whale_transactions(token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_cwt_exchange_time ON cex_whale_transactions(exchange_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_cwt_time ON cex_whale_transactions(time DESC);
CREATE INDEX IF NOT EXISTS idx_cwt_value ON cex_whale_transactions(value_usd DESC);
CREATE INDEX IF NOT EXISTS idx_cwt_symbol ON cex_whale_transactions(symbol, time DESC);

-- DEX Whale Swaps (from Chiliz Chain RPC)
CREATE TABLE IF NOT EXISTS dex_whale_swaps (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    token_id INTEGER REFERENCES fan_tokens(id),
    tx_hash VARCHAR(66) NOT NULL UNIQUE, -- 0x... transaction hash
    block_number BIGINT NOT NULL,
    from_address VARCHAR(42) NOT NULL,
    to_address VARCHAR(42),
    token_in VARCHAR(20) NOT NULL,
    token_out VARCHAR(20) NOT NULL,
    amount_in DECIMAL(30, 8) NOT NULL,
    amount_out DECIMAL(30, 8) NOT NULL,
    value_usd DECIMAL(20, 2) NOT NULL,
    dex_name VARCHAR(50) DEFAULT 'FanX', -- DEX protocol name
    pool_address VARCHAR(42),
    gas_used BIGINT,
    gas_price_gwei DECIMAL(20, 2)
);

CREATE INDEX IF NOT EXISTS idx_dws_token_time ON dex_whale_swaps(token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_dws_time ON dex_whale_swaps(time DESC);
CREATE INDEX IF NOT EXISTS idx_dws_value ON dex_whale_swaps(value_usd DESC);
CREATE INDEX IF NOT EXISTS idx_dws_from ON dex_whale_swaps(from_address, time DESC);
CREATE INDEX IF NOT EXISTS idx_dws_block ON dex_whale_swaps(block_number DESC);

-- Known Whale Wallets (for labeling)
CREATE TABLE IF NOT EXISTS whale_wallets (
    id SERIAL PRIMARY KEY,
    address VARCHAR(42) UNIQUE NOT NULL,
    label VARCHAR(100), -- e.g., "Binance Hot Wallet", "FanX Team", "Whale #1"
    wallet_type VARCHAR(30), -- 'exchange', 'dex', 'whale', 'team', 'fund'
    exchange_id INTEGER REFERENCES exchanges(id), -- If it's a CEX wallet
    is_tracked BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ww_address ON whale_wallets(address);
CREATE INDEX IF NOT EXISTS idx_ww_type ON whale_wallets(wallet_type);

-- Insert known exchange wallets
INSERT INTO whale_wallets (address, label, wallet_type) VALUES
    -- Binance
    ('0x28c6c06298d514db089934071355e5743bf21d60', 'Binance Hot Wallet', 'exchange'),
    ('0x21a31ee1afc51d94c2efccaa2092ad1028285549', 'Binance Hot Wallet 2', 'exchange'),
    ('0xdfd5293d8e347dfe59e90efd55b2956a1343963d', 'Binance Hot Wallet 3', 'exchange'),
    -- OKX
    ('0x98ec059dc3adfbdd63429454aeb0c990fba4a128', 'OKX Hot Wallet', 'exchange'),
    ('0x6cc5f688a315f3dc28a7781717a9a798a59fda7b', 'OKX Hot Wallet 2', 'exchange'),
    -- Bybit
    ('0xf89d7b9c864f589bbf53a82105107622b35eaa40', 'Bybit Hot Wallet', 'exchange'),
    -- Gate
    ('0x0d0707963952f2fba59dd06f2b425ace40b492fe', 'Gate.io Hot Wallet', 'exchange'),
    -- FanX DEX
    ('0xE2918AA38088878546c1A18F2F9b1BC83297fdD3', 'FanX Factory', 'dex'),
    ('0x1918EbB39492C8b98865c5E53219c3f1AE79e76F', 'FanX Router', 'dex')
ON CONFLICT (address) DO NOTHING;

-- =====================================================
-- AGGREGATED WHALE FLOW
-- =====================================================

-- Whale Flow Summary (hourly aggregation)
CREATE TABLE IF NOT EXISTS whale_flow_hourly (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),
    venue_type VARCHAR(10) NOT NULL, -- 'cex' or 'dex'
    exchange_id INTEGER REFERENCES exchanges(id), -- NULL for DEX
    buy_volume_usd DECIMAL(20, 2) DEFAULT 0,
    sell_volume_usd DECIMAL(20, 2) DEFAULT 0,
    net_flow_usd DECIMAL(20, 2) DEFAULT 0, -- buy - sell
    buy_count INTEGER DEFAULT 0,
    sell_count INTEGER DEFAULT 0,
    avg_trade_size_usd DECIMAL(20, 2),
    largest_trade_usd DECIMAL(20, 2),
    UNIQUE (time, token_id, venue_type, exchange_id)
);

CREATE INDEX IF NOT EXISTS idx_wfh_token_time ON whale_flow_hourly(token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_wfh_time ON whale_flow_hourly(time DESC);

-- =====================================================
-- SOCIAL SIGNALS TABLE (for real-time tracking)
-- =====================================================

-- Individual tweets/signals for display
CREATE TABLE IF NOT EXISTS social_signals (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    token_id INTEGER REFERENCES fan_tokens(id),
    signal_type VARCHAR(30) NOT NULL, -- 'tweet', 'news', 'reddit', 'alert'
    source VARCHAR(50), -- '@user', 'CoinDesk', etc.
    source_url VARCHAR(500),
    title VARCHAR(300),
    content TEXT,
    sentiment VARCHAR(10), -- 'positive', 'negative', 'neutral'
    sentiment_score DECIMAL(5, 4), -- 0-1
    engagement INTEGER DEFAULT 0, -- likes + retweets + replies
    followers INTEGER DEFAULT 0, -- Author followers
    is_influencer BOOLEAN DEFAULT FALSE,
    is_high_priority BOOLEAN DEFAULT FALSE,
    categories TEXT[], -- ['crypto', 'sports', 'fantoken']
    raw_data JSONB
);

CREATE INDEX IF NOT EXISTS idx_ss_token_time ON social_signals(token_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_ss_time ON social_signals(time DESC);
CREATE INDEX IF NOT EXISTS idx_ss_type ON social_signals(signal_type, time DESC);
CREATE INDEX IF NOT EXISTS idx_ss_priority ON social_signals(is_high_priority, time DESC);
CREATE INDEX IF NOT EXISTS idx_ss_categories ON social_signals USING GIN(categories);

-- =====================================================
-- VIEWS FOR EASY QUERYING
-- =====================================================

-- Recent whale activity view
CREATE OR REPLACE VIEW recent_whale_activity AS
SELECT
    'cex' as venue,
    cwt.time,
    ft.symbol,
    e.name as exchange_name,
    cwt.side,
    cwt.price,
    cwt.quantity,
    cwt.value_usd,
    cwt.is_aggressive,
    NULL as tx_hash
FROM cex_whale_transactions cwt
JOIN fan_tokens ft ON cwt.token_id = ft.id
JOIN exchanges e ON cwt.exchange_id = e.id
WHERE cwt.time > NOW() - INTERVAL '24 hours'

UNION ALL

SELECT
    'dex' as venue,
    dws.time,
    ft.symbol,
    dws.dex_name as exchange_name,
    CASE WHEN dws.token_in = 'CHZ' THEN 'buy' ELSE 'sell' END as side,
    CASE WHEN dws.amount_out > 0 THEN dws.value_usd / dws.amount_out ELSE 0 END as price,
    COALESCE(dws.amount_out, dws.amount_in) as quantity,
    dws.value_usd,
    FALSE as is_aggressive,
    dws.tx_hash
FROM dex_whale_swaps dws
JOIN fan_tokens ft ON dws.token_id = ft.id
WHERE dws.time > NOW() - INTERVAL '24 hours'

ORDER BY time DESC;
