-- Migration 005: LunarCrush and Reddit Integration Tables
-- Created: 2024-12-04
-- Purpose: Add tables for multi-source social intelligence

-- LunarCrush metrics table (Galaxy Score, sentiment, social volume)
CREATE TABLE IF NOT EXISTS lunarcrush_metrics (
    time TIMESTAMPTZ NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),

    -- Core LunarCrush metrics
    galaxy_score DECIMAL(5,2),          -- 0-100 overall score
    alt_rank INTEGER,                    -- Rank among all altcoins
    sentiment DECIMAL(4,3),              -- Normalized 0-1

    -- Social volume metrics
    social_volume INTEGER,               -- Current social posts
    social_volume_24h INTEGER,           -- 24h social volume
    social_dominance DECIMAL(6,4),       -- % of all crypto social

    -- Engagement metrics
    social_contributors INTEGER,         -- Unique contributors
    social_interactions BIGINT,          -- Total interactions

    -- Sentiment breakdown
    bullish_sentiment DECIMAL(5,2),      -- % bullish
    bearish_sentiment DECIMAL(5,2),      -- % bearish

    -- Market data from LunarCrush
    price DECIMAL(20,8),
    price_change_24h DECIMAL(8,4),
    market_cap DECIMAL(20,2),
    volume_24h DECIMAL(20,2),

    -- Raw API response
    raw_data JSONB,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY (time, token_id)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('lunarcrush_metrics', 'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

-- Reddit signals table
CREATE TABLE IF NOT EXISTS reddit_signals (
    time TIMESTAMPTZ NOT NULL,
    token_id INTEGER REFERENCES fan_tokens(id),

    -- Post metadata
    post_id VARCHAR(50) NOT NULL,         -- Reddit post ID
    subreddit VARCHAR(100),
    title TEXT,
    content TEXT,
    url TEXT,
    author VARCHAR(100),

    -- Signal type
    signal_type VARCHAR(50) DEFAULT 'post',  -- post, comment

    -- Engagement metrics
    score INTEGER DEFAULT 0,              -- Upvotes - downvotes
    upvote_ratio DECIMAL(4,3),           -- % upvoted
    num_comments INTEGER DEFAULT 0,

    -- Analysis
    sentiment VARCHAR(20),                -- positive, negative, neutral
    sentiment_score DECIMAL(4,3),         -- 0-1 confidence
    categories TEXT[],                    -- crypto, sports, fantoken, etc.

    -- Priority flags
    is_high_priority BOOLEAN DEFAULT FALSE,
    is_trending BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Primary key includes time for hypertable partitioning
    PRIMARY KEY (time, post_id)
);

-- Convert to hypertable
SELECT create_hypertable('reddit_signals', 'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '7 days'
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_reddit_signals_token ON reddit_signals(token_id);
CREATE INDEX IF NOT EXISTS idx_reddit_signals_subreddit ON reddit_signals(subreddit);
CREATE INDEX IF NOT EXISTS idx_reddit_signals_high_priority ON reddit_signals(is_high_priority) WHERE is_high_priority = TRUE;
CREATE INDEX IF NOT EXISTS idx_reddit_signals_post_id ON reddit_signals(post_id);

-- Aggregated social metrics view (combines X, LunarCrush, Reddit)
CREATE OR REPLACE VIEW social_metrics_combined AS
SELECT
    ft.symbol,
    ft.team,

    -- Latest LunarCrush metrics
    lc.galaxy_score,
    lc.alt_rank,
    lc.sentiment as lc_sentiment,
    lc.social_volume_24h as lc_volume_24h,

    -- X signal counts (last 24h)
    COALESCE(ss_agg.signal_count, 0) as x_signal_count,
    COALESCE(ss_agg.avg_sentiment, 0.5) as x_sentiment,
    COALESCE(ss_agg.total_engagement, 0) as x_engagement,

    -- Reddit signal counts (last 24h)
    COALESCE(rs_agg.post_count, 0) as reddit_post_count,
    COALESCE(rs_agg.avg_sentiment, 0.5) as reddit_sentiment,
    COALESCE(rs_agg.total_score, 0) as reddit_score,

    -- Combined metrics
    ROUND(
        COALESCE(lc.sentiment * 100, 50) * 0.4 +
        COALESCE(ss_agg.avg_sentiment * 100, 50) * 0.35 +
        COALESCE(rs_agg.avg_sentiment * 100, 50) * 0.25
    , 1) as combined_sentiment_score,

    COALESCE(ss_agg.signal_count, 0) + COALESCE(rs_agg.post_count, 0) as total_social_signals

FROM fan_tokens ft

-- Latest LunarCrush data
LEFT JOIN LATERAL (
    SELECT * FROM lunarcrush_metrics
    WHERE token_id = ft.id
    ORDER BY time DESC
    LIMIT 1
) lc ON TRUE

-- X signals aggregation (last 24h)
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as signal_count,
        AVG(sentiment_score) as avg_sentiment,
        SUM(engagement) as total_engagement
    FROM social_signals
    WHERE token_id = ft.id
    AND time > NOW() - INTERVAL '24 hours'
) ss_agg ON TRUE

-- Reddit signals aggregation (last 24h)
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as post_count,
        AVG(sentiment_score) as avg_sentiment,
        SUM(score) as total_score
    FROM reddit_signals
    WHERE token_id = ft.id
    AND time > NOW() - INTERVAL '24 hours'
) rs_agg ON TRUE

WHERE ft.is_active = TRUE;

-- Add indexes to lunarcrush_metrics
CREATE INDEX IF NOT EXISTS idx_lunarcrush_token ON lunarcrush_metrics(token_id);
CREATE INDEX IF NOT EXISTS idx_lunarcrush_galaxy ON lunarcrush_metrics(galaxy_score DESC);

-- Retention policy: keep 90 days of detailed data
SELECT add_retention_policy('lunarcrush_metrics', INTERVAL '90 days', if_not_exists => TRUE);
SELECT add_retention_policy('reddit_signals', INTERVAL '90 days', if_not_exists => TRUE);

COMMENT ON TABLE lunarcrush_metrics IS 'LunarCrush social intelligence metrics - Galaxy Score, sentiment, social volume';
COMMENT ON TABLE reddit_signals IS 'Reddit community signals - posts and comments mentioning fan tokens';
COMMENT ON VIEW social_metrics_combined IS 'Combined view of X, LunarCrush, and Reddit social metrics';
