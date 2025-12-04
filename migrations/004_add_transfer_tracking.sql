-- Migration 004: Add transfer tracking tables
-- Tracks transfer news, rumors, and their impact on token prices

-- Transfer events table - stores individual transfer news/rumors
CREATE TABLE IF NOT EXISTS transfer_events (
    id SERIAL PRIMARY KEY,
    token_id INTEGER REFERENCES fan_tokens(id),

    -- Event details
    event_type VARCHAR(50) NOT NULL,  -- 'transfer', 'loan', 'rumor', 'signing', 'departure'
    player_name VARCHAR(200),
    from_team VARCHAR(200),
    to_team VARCHAR(200),

    -- Source info
    source_type VARCHAR(50) NOT NULL,  -- 'twitter', 'news', 'official'
    source_url TEXT,
    source_author VARCHAR(200),
    tweet_id VARCHAR(50),

    -- Content
    headline TEXT NOT NULL,
    content TEXT,

    -- Metrics
    engagement INTEGER DEFAULT 0,
    sentiment_score FLOAT,
    credibility_score FLOAT,  -- 0-1, based on source reputation
    is_verified BOOLEAN DEFAULT FALSE,
    is_official BOOLEAN DEFAULT FALSE,

    -- Impact tracking
    price_at_event FLOAT,
    price_1h_after FLOAT,
    price_24h_after FLOAT,
    volume_spike_pct FLOAT,

    -- Timestamps
    event_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_transfer_events_token ON transfer_events(token_id);
CREATE INDEX IF NOT EXISTS idx_transfer_events_time ON transfer_events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_transfer_events_type ON transfer_events(event_type);
CREATE INDEX IF NOT EXISTS idx_transfer_events_player ON transfer_events(player_name);

-- Transfer alerts - aggregated alerts for significant transfer activity
CREATE TABLE IF NOT EXISTS transfer_alerts (
    id SERIAL PRIMARY KEY,
    token_id INTEGER REFERENCES fan_tokens(id),

    alert_type VARCHAR(50) NOT NULL,  -- 'rumor_spike', 'official_transfer', 'departure_risk'
    severity VARCHAR(20) NOT NULL,     -- 'low', 'medium', 'high', 'critical'

    headline TEXT NOT NULL,
    description TEXT,

    -- Related events
    event_count INTEGER DEFAULT 1,
    total_engagement INTEGER DEFAULT 0,
    avg_sentiment FLOAT,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(200),
    acknowledged_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_transfer_alerts_active ON transfer_alerts(is_active, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transfer_alerts_token ON transfer_alerts(token_id);

-- Credible sources for transfer news
CREATE TABLE IF NOT EXISTS transfer_sources (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(200) NOT NULL UNIQUE,
    source_type VARCHAR(50) NOT NULL,  -- 'journalist', 'news_outlet', 'official_account', 'aggregator'
    twitter_handle VARCHAR(100),
    credibility_tier INTEGER DEFAULT 3,  -- 1=highest (Fabrizio Romano), 5=lowest
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed credible transfer sources
INSERT INTO transfer_sources (source_name, source_type, twitter_handle, credibility_tier, description) VALUES
    ('Fabrizio Romano', 'journalist', 'FabrizioRomano', 1, 'Most reliable transfer journalist - "Here we go"'),
    ('David Ornstein', 'journalist', 'David_Ornstein', 1, 'The Athletic, Premier League specialist'),
    ('Gianluca Di Marzio', 'journalist', 'DiMarzio', 1, 'Sky Italia, Serie A specialist'),
    ('Gerard Romero', 'journalist', 'geraboromeu', 2, 'Barcelona specialist'),
    ('Matteo Moretto', 'journalist', 'MatteMoretto', 2, 'Relevo, Serie A & La Liga'),
    ('Florian Plettenberg', 'journalist', 'Plettigoal', 2, 'Sky Germany'),
    ('The Athletic', 'news_outlet', 'TheAthletic', 1, 'Premium sports journalism'),
    ('Sky Sports', 'news_outlet', 'SkySportsNews', 2, 'UK broadcaster'),
    ('ESPN FC', 'news_outlet', 'ESPNFC', 2, 'ESPN football coverage'),
    ('MARCA', 'news_outlet', 'marca', 2, 'Spanish sports daily'),
    ('Gazzetta dello Sport', 'news_outlet', 'Gaboromag', 2, 'Italian sports daily'),
    ('L''Equipe', 'news_outlet', 'lequipe', 2, 'French sports daily'),
    ('Transfer News Live', 'aggregator', 'DeadlineDayLive', 3, 'Transfer aggregator')
ON CONFLICT (source_name) DO NOTHING;
