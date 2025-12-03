-- Campaigns table for tracking marketing initiatives and measuring impact
-- PoC Core Feature: Do our marketing campaigns create measurable noise and impact?

CREATE TABLE IF NOT EXISTS campaigns (
    id SERIAL PRIMARY KEY,
    token_id INTEGER REFERENCES fan_tokens(id),
    name VARCHAR(200) NOT NULL,
    campaign_type VARCHAR(50) NOT NULL, -- social_push, partnership, airdrop, match_day, announcement
    start_date TIMESTAMP WITH TIME ZONE NOT NULL,
    end_date TIMESTAMP WITH TIME ZONE,
    description TEXT,
    budget_usd DECIMAL(12, 2),
    target_reach INTEGER,
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, active, completed, cancelled
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_token ON campaigns(token_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_dates ON campaigns(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);

-- Add social_price_corr column to correlation_analysis if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'correlation_analysis' AND column_name = 'social_price_corr'
    ) THEN
        ALTER TABLE correlation_analysis ADD COLUMN social_price_corr DECIMAL(6, 4);
    END IF;
END $$;
