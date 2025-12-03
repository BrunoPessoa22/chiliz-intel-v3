-- Update fan tokens to 2025 complete list

-- First, deactivate tokens that are no longer tracked
UPDATE fan_tokens SET is_active = FALSE
WHERE symbol IN ('SANTOS', 'ALPINE', 'LAZIO', 'PORTO');

-- Insert/Update all current tokens
INSERT INTO fan_tokens (symbol, name, team, league, country, coingecko_id, is_active) VALUES
    -- Native
    ('CHZ', 'Chiliz', 'Chiliz', NULL, NULL, 'chiliz', TRUE),
    -- Esports
    ('OG', 'OG Fan Token', 'OG Esports', 'Esports', NULL, 'og-fan-token', TRUE),
    ('NAVI', 'Natus Vincere Fan Token', 'Natus Vincere', 'Esports', NULL, 'natus-vincere-fan-token', TRUE),
    ('ALL', 'Alliance Fan Token', 'Alliance', 'Esports', NULL, 'alliance-fan-token', TRUE),
    ('TH', 'Team Heretics Fan Token', 'Team Heretics', 'Esports', NULL, 'team-heretics-fan-token', TRUE),
    ('VIT', 'Team Vitality Fan Token', 'Team Vitality', 'Esports', NULL, 'team-vitality-fan-token', TRUE),
    ('DOJO', 'Ninjas in Pyjamas Fan Token', 'Ninjas in Pyjamas', 'Esports', NULL, 'ninjas-in-pyjamas', TRUE),
    ('MIBR', 'MIBR Fan Token', 'MIBR', 'Esports', NULL, 'mibr-fan-token', TRUE),
    -- La Liga
    ('BAR', 'FC Barcelona Fan Token', 'FC Barcelona', 'La Liga', 'Spain', 'fc-barcelona-fan-token', TRUE),
    ('ATM', 'Atlético de Madrid Fan Token', 'Atlético de Madrid', 'La Liga', 'Spain', 'atletico-madrid', TRUE),
    ('VCF', 'Valencia CF Fan Token', 'Valencia CF', 'La Liga', 'Spain', 'valencia-cf-fan-token', TRUE),
    ('SEVILLA', 'Sevilla Fan Token', 'Sevilla FC', 'La Liga', 'Spain', 'sevilla-fan-token', TRUE),
    ('LEV', 'Levante Fan Token', 'Levante U.D.', 'La Liga', 'Spain', 'levante-ud-fan-token', TRUE),
    ('RSO', 'Real Sociedad Fan Token', 'Real Sociedad', 'La Liga', 'Spain', 'real-sociedad-fan-token', TRUE),
    -- Premier League
    ('CITY', 'Manchester City Fan Token', 'Manchester City', 'Premier League', 'England', 'manchester-city-fan-token', TRUE),
    ('AFC', 'Arsenal Fan Token', 'Arsenal FC', 'Premier League', 'England', 'arsenal-fan-token', TRUE),
    ('SPURS', 'Tottenham Hotspur Fan Token', 'Tottenham Hotspur', 'Premier League', 'England', 'tottenham-hotspur-fc-fan-token', TRUE),
    ('EFC', 'Everton Fan Token', 'Everton FC', 'Premier League', 'England', 'everton-fan-token', TRUE),
    ('AVL', 'Aston Villa Fan Token', 'Aston Villa', 'Premier League', 'England', 'aston-villa-fan-token', TRUE),
    ('LUFC', 'Leeds United Fan Token', 'Leeds United', 'Premier League', 'England', 'leeds-united-fan-token', TRUE),
    ('CPFC', 'Crystal Palace Fan Token', 'Crystal Palace', 'Premier League', 'England', 'crystal-palace-fc-fan-token', TRUE),
    -- Serie A
    ('JUV', 'Juventus Fan Token', 'Juventus', 'Serie A', 'Italy', 'juventus-fan-token', TRUE),
    ('ACM', 'AC Milan Fan Token', 'AC Milan', 'Serie A', 'Italy', 'ac-milan-fan-token', TRUE),
    ('ASR', 'AS Roma Fan Token', 'AS Roma', 'Serie A', 'Italy', 'as-roma-fan-token', TRUE),
    ('INTER', 'Inter Milan Fan Token', 'Inter Milan', 'Serie A', 'Italy', 'inter-milan-fan-token', TRUE),
    ('NAP', 'Napoli Fan Token', 'SSC Napoli', 'Serie A', 'Italy', 'napoli-fan-token', TRUE),
    ('BFC', 'Bologna FC Fan Token', 'Bologna FC', 'Serie A', 'Italy', 'bologna-fc-fan-token', TRUE),
    ('UDI', 'Udinese Fan Token', 'Udinese Calcio', 'Serie A', 'Italy', 'udinese-calcio-fan-token', TRUE),
    -- Ligue 1
    ('PSG', 'Paris Saint-Germain Fan Token', 'Paris Saint-Germain', 'Ligue 1', 'France', 'paris-saint-germain-fan-token', TRUE),
    ('ASM', 'AS Monaco Fan Token', 'AS Monaco', 'Ligue 1', 'France', 'as-monaco-fan-token', TRUE),
    -- Portugal
    ('BENFICA', 'SL Benfica Fan Token', 'SL Benfica', 'Primeira Liga', 'Portugal', 'sl-benfica-fan-token', TRUE),
    -- Turkey
    ('GAL', 'Galatasaray Fan Token', 'Galatasaray', 'Super Lig', 'Turkey', 'galatasaray-fan-token', TRUE),
    ('TRA', 'Trabzonspor Fan Token', 'Trabzonspor', 'Super Lig', 'Turkey', 'trabzonspor-fan-token', TRUE),
    ('GOZ', 'Göztepe Fan Token', 'Göztepe S.K.', 'Super Lig', 'Turkey', 'goztepe-s-k-fan-token', TRUE),
    ('SAM', 'Samsunspor Fan Token', 'Samsunspor', 'Super Lig', 'Turkey', 'samsunspor-fan-token', TRUE),
    ('ALA', 'Alanyaspor Fan Token', 'Alanyaspor', 'Super Lig', 'Turkey', 'alanyaspor-fan-token', TRUE),
    ('IBFK', 'İstanbul Başakşehir Fan Token', 'İstanbul Başakşehir', 'Super Lig', 'Turkey', 'istanbul-basaksehir-fan-token', TRUE),
    ('GFK', 'Gaziantep FK Fan Token', 'Gaziantep FK', 'Super Lig', 'Turkey', 'gaziantep-fk-fan-token', TRUE),
    -- Brazil
    ('MENGO', 'Flamengo Fan Token', 'Flamengo', 'Serie A Brazil', 'Brazil', 'flamengo-fan-token', TRUE),
    ('SCCP', 'Corinthians Fan Token', 'S.C. Corinthians', 'Serie A Brazil', 'Brazil', 's-c-corinthians-fan-token', TRUE),
    ('GALO', 'Atlético Mineiro Fan Token', 'Atlético Mineiro', 'Serie A Brazil', 'Brazil', 'clube-atletico-mineiro-fan-token', TRUE),
    ('SPFC', 'São Paulo FC Fan Token', 'São Paulo FC', 'Serie A Brazil', 'Brazil', 'sao-paulo-fc-fan-token', TRUE),
    ('VERDAO', 'Palmeiras Fan Token', 'SE Palmeiras', 'Serie A Brazil', 'Brazil', 'palmeiras-fan-token', TRUE),
    ('FLU', 'Fluminense Fan Token', 'Fluminense FC', 'Serie A Brazil', 'Brazil', 'fluminense-fc-fan-token', TRUE),
    ('VASCO', 'Vasco da Gama Fan Token', 'Vasco da Gama', 'Serie A Brazil', 'Brazil', 'vasco-da-gama-fan-token', TRUE),
    ('SACI', 'Internacional Fan Token', 'SC Internacional', 'Serie A Brazil', 'Brazil', 'sc-internacional-fan-token', TRUE),
    ('BAHIA', 'EC Bahia Fan Token', 'EC Bahia', 'Serie A Brazil', 'Brazil', 'esporte-clube-bahia-fan-token', TRUE),
    -- Argentina
    ('CAI', 'Independiente Fan Token', 'Club Atlético Independiente', 'Primera Division', 'Argentina', 'club-atletico-independiente', TRUE),
    ('RACING', 'Racing Club Fan Token', 'Racing Club', 'Primera Division', 'Argentina', 'racing-club-fan-token', TRUE),
    -- National Teams
    ('ARG', 'Argentina Fan Token', 'Argentina', 'National Team', 'Argentina', 'argentine-football-association-fan-token', TRUE),
    ('POR', 'Portugal Fan Token', 'Portugal', 'National Team', 'Portugal', 'portugal-national-team-fan-token', TRUE),
    ('ITA', 'Italy Fan Token', 'Italy', 'National Team', 'Italy', 'italian-national-football-team-fan-token', TRUE),
    -- Formula 1
    ('SAUBER', 'Alfa Romeo Racing Fan Token', 'Alfa Romeo Racing ORLEN', 'Formula 1', NULL, 'alfa-romeo-racing-orlen-fan-token', TRUE),
    ('AM', 'Aston Martin F1 Fan Token', 'Aston Martin Cognizant', 'Formula 1', NULL, 'aston-martin-cognizant-fan-token', TRUE),
    -- MMA
    ('UFC', 'UFC Fan Token', 'UFC', 'MMA', NULL, 'ufc-fan-token', TRUE),
    ('PFL', 'PFL Fan Token', 'Professional Fighters League', 'MMA', NULL, 'professional-fighters-league-fan-token', TRUE),
    -- Other Football
    ('LEG', 'Legia Warsaw Fan Token', 'Legia Warsaw', 'Ekstraklasa', 'Poland', 'legia-warsaw-fan-token', TRUE),
    ('YBO', 'Young Boys Fan Token', 'BSC Young Boys', 'Swiss Super League', 'Switzerland', 'young-boys-fan-token', TRUE),
    ('STV', 'Sint-Truidense Fan Token', 'Sint-Truidense VV', 'Belgian Pro League', 'Belgium', 'sint-truidense-voetbalvereniging-fan-token', TRUE),
    ('TIGRES', 'Tigres Fan Token', 'Tigres UANL', 'Liga MX', 'Mexico', 'tigres-fan-token', TRUE),
    ('MFC', 'Millonarios FC Fan Token', 'Millonarios FC', 'Categoria Primera A', 'Colombia', 'millonarios-fc-fan-token', TRUE),
    ('DZG', 'Dinamo Zagreb Fan Token', 'Dinamo Zagreb', 'HNL', 'Croatia', 'dinamo-zagreb-fan-token', TRUE),
    ('APL', 'Apollon Limassol Fan Token', 'Apollon Limassol', 'First Division', 'Cyprus', 'apollon-limassol-fan-token', TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    coingecko_id = EXCLUDED.coingecko_id,
    team = EXCLUDED.team,
    league = EXCLUDED.league,
    country = EXCLUDED.country,
    is_active = EXCLUDED.is_active;

-- Add BTC and ETH for correlation tracking (not fan tokens, but needed for correlation)
INSERT INTO fan_tokens (symbol, name, team, league, country, coingecko_id, is_active) VALUES
    ('BTC', 'Bitcoin', 'Market Reference', 'Crypto', NULL, 'bitcoin', TRUE),
    ('ETH', 'Ethereum', 'Market Reference', 'Crypto', NULL, 'ethereum', TRUE)
ON CONFLICT (symbol) DO UPDATE SET
    coingecko_id = EXCLUDED.coingecko_id,
    is_active = EXCLUDED.is_active;
