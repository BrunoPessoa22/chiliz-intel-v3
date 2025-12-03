-- Migration 003: Add all Chiliz fan tokens (65 total)
-- This adds any missing tokens to the fan_tokens table

-- Insert tokens only if they don't already exist (using ON CONFLICT)
INSERT INTO fan_tokens (symbol, name, team, league, country, coingecko_id, is_active) VALUES
    -- Base token
    ('CHZ', 'Chiliz', 'Chiliz Chain', NULL, NULL, 'chiliz', true),

    -- La Liga (Spain)
    ('BAR', 'FC Barcelona Fan Token', 'FC Barcelona', 'La Liga', 'Spain', 'fc-barcelona-fan-token', true),
    ('ATM', 'Atletico Madrid Fan Token', 'Atlético de Madrid', 'La Liga', 'Spain', 'atletico-madrid', true),
    ('VCF', 'Valencia CF Fan Token', 'Valencia CF', 'La Liga', 'Spain', 'valencia-cf-fan-token', true),
    ('SEVILLA', 'Sevilla Fan Token', 'Sevilla FC', 'La Liga', 'Spain', 'sevilla-fan-token', true),

    -- Serie A (Italy)
    ('JUV', 'Juventus Fan Token', 'Juventus', 'Serie A', 'Italy', 'juventus-fan-token', true),
    ('ACM', 'AC Milan Fan Token', 'AC Milan', 'Serie A', 'Italy', 'ac-milan-fan-token', true),
    ('ASR', 'AS Roma Fan Token', 'AS Roma', 'Serie A', 'Italy', 'as-roma-fan-token', true),
    ('LAZIO', 'Lazio Fan Token', 'SS Lazio', 'Serie A', 'Italy', 'lazio-fan-token', true),
    ('INTER', 'Inter Milan Fan Token', 'Inter Milan', 'Serie A', 'Italy', 'inter-milan-fan-token', true),
    ('NAP', 'Napoli Fan Token', 'SSC Napoli', 'Serie A', 'Italy', 'napoli-fan-token', true),
    ('UDI', 'Udinese Calcio Fan Token', 'Udinese Calcio', 'Serie A', 'Italy', 'udinese-calcio-fan-token', true),

    -- Premier League (England)
    ('CITY', 'Manchester City Fan Token', 'Manchester City', 'Premier League', 'England', 'manchester-city-fan-token', true),
    ('AFC', 'Arsenal Fan Token', 'Arsenal FC', 'Premier League', 'England', 'arsenal-fan-token', true),
    ('SPURS', 'Tottenham Hotspur Fan Token', 'Tottenham Hotspur', 'Premier League', 'England', 'tottenham-hotspur-fc-fan-token', true),
    ('EFC', 'Everton Fan Token', 'Everton FC', 'Premier League', 'England', 'everton-fan-token', true),
    ('AVL', 'Aston Villa Fan Token', 'Aston Villa', 'Premier League', 'England', 'aston-villa-fan-token', true),

    -- Ligue 1 (France)
    ('PSG', 'Paris Saint-Germain Fan Token', 'Paris Saint-Germain', 'Ligue 1', 'France', 'paris-saint-germain-fan-token', true),
    ('ASM', 'AS Monaco Fan Token', 'AS Monaco', 'Ligue 1', 'France', 'as-monaco-fan-token', true),

    -- Primeira Liga (Portugal)
    ('PORTO', 'FC Porto Fan Token', 'FC Porto', 'Primeira Liga', 'Portugal', 'fc-porto', true),
    ('BENFICA', 'SL Benfica Fan Token', 'SL Benfica', 'Primeira Liga', 'Portugal', 'sl-benfica-fan-token', true),

    -- Süper Lig (Turkey)
    ('GAL', 'Galatasaray Fan Token', 'Galatasaray', 'Süper Lig', 'Turkey', 'galatasaray-fan-token', true),
    ('TRA', 'Trabzonspor Fan Token', 'Trabzonspor', 'Süper Lig', 'Turkey', 'trabzonspor-fan-token', true),
    ('GOZ', 'Göztepe S.K. Fan Token', 'Göztepe S.K.', 'Süper Lig', 'Turkey', 'goztepe-s-k-fan-token', true),
    ('SAM', 'Samsunspor Fan Token', 'Samsunspor', 'Süper Lig', 'Turkey', 'samsunspor-fan-token', true),
    ('ALA', 'Alanyaspor Fan Token', 'Alanyaspor', 'Süper Lig', 'Turkey', 'alanyaspor-fan-token', true),
    ('IBFK', 'İstanbul Başakşehir Fan Token', 'İstanbul Başakşehir', 'Süper Lig', 'Turkey', 'istanbul-basaksehir-fan-token', true),
    ('BJK', 'Beşiktaş Fan Token', 'Beşiktaş', 'Süper Lig', 'Turkey', 'besiktas', true),
    ('FB', 'Fenerbahçe Fan Token', 'Fenerbahçe', 'Süper Lig', 'Turkey', 'fenerbahce-token', true),

    -- Brasileirão (Brazil)
    ('SANTOS', 'Santos FC Fan Token', 'Santos FC', 'Brasileirão', 'Brazil', 'santos-fc-fan-token', true),
    ('MENGO', 'Flamengo Fan Token', 'Flamengo', 'Brasileirão', 'Brazil', 'flamengo-fan-token', true),
    ('FLU', 'Fluminense FC Fan Token', 'Fluminense', 'Brasileirão', 'Brazil', 'fluminense-fc-fan-token', true),
    ('SCCP', 'S.C. Corinthians Fan Token', 'Corinthians', 'Brasileirão', 'Brazil', 's-c-corinthians-fan-token', true),
    ('SPFC', 'Sao Paulo FC Fan Token', 'São Paulo FC', 'Brasileirão', 'Brazil', 'sao-paulo-fc-fan-token', true),
    ('GALO', 'Atlético Mineiro Fan Token', 'Atlético Mineiro', 'Brasileirão', 'Brazil', 'clube-atletico-mineiro-fan-token', true),
    ('VERDAO', 'Palmeiras Fan Token', 'Palmeiras', 'Brasileirão', 'Brazil', 'palmeiras-fan-token', true),
    ('VASCO', 'Vasco da Gama Fan Token', 'Vasco da Gama', 'Brasileirão', 'Brazil', 'vasco-da-gama-fan-token', true),
    ('BAHIA', 'Esporte Clube Bahia Fan Token', 'EC Bahia', 'Brasileirão', 'Brazil', 'esporte-clube-bahia-fan-token', true),
    ('SACI', 'SC Internacional Fan Token', 'Internacional', 'Brasileirão', 'Brazil', 'sc-internacional-fan-token', true),

    -- Argentina
    ('ARG', 'Argentine Football Association Fan Token', 'Argentina NT', 'National Team', 'Argentina', 'argentine-football-association-fan-token', true),
    ('CAI', 'Club Atletico Independiente Fan Token', 'Independiente', 'Argentine Primera', 'Argentina', 'club-atletico-independiente', true),

    -- Other Leagues
    ('LEG', 'Legia Warsaw Fan Token', 'Legia Warsaw', 'Ekstraklasa', 'Poland', 'legia-warsaw-fan-token', true),
    ('TIGRES', 'Tigres Fan Token', 'Tigres UANL', 'Liga MX', 'Mexico', 'tigres-fan-token', true),
    ('YBO', 'Young Boys Fan Token', 'BSC Young Boys', 'Swiss Super League', 'Switzerland', 'young-boys-fan-token', true),
    ('STV', 'Sint-Truidense VV Fan Token', 'Sint-Truidense VV', 'Belgian Pro League', 'Belgium', 'sint-truidense-voetbalvereniging-fan-token', true),

    -- National Teams
    ('POR', 'Portugal National Team Fan Token', 'Portugal NT', 'National Team', 'Portugal', 'portugal-national-team-fan-token', true),
    ('ITA', 'Italian National Football Team Fan Token', 'Italy NT', 'National Team', 'Italy', 'italian-national-football-team-fan-token', true),
    ('VATRENI', 'Croatian Football Federation Token', 'Croatia NT', 'National Team', 'Croatia', 'croatian-ff-fan-token', true),
    ('SNFT', 'Spain National Football Team Fan Token', 'Spain NT', 'National Team', 'Spain', 'spain-national-fan-token', true),
    ('BFT', 'Brazil National Football Team Fan Token', 'Brazil NT', 'National Team', 'Brazil', 'brazil-fan-token', true),

    -- Formula 1
    ('ALPINE', 'Alpine F1 Team Fan Token', 'Alpine F1', 'Formula 1', 'France', 'alpine-f1-team-fan-token', true),
    ('SAUBER', 'Alfa Romeo Racing ORLEN Fan Token', 'Sauber F1', 'Formula 1', 'Switzerland', 'alfa-romeo-racing-orlen-fan-token', true),
    ('AM', 'Aston Martin Cognizant Fan Token', 'Aston Martin F1', 'Formula 1', 'UK', 'aston-martin-cognizant-fan-token', true),

    -- MMA / Fighting
    ('UFC', 'UFC Fan Token', 'UFC', 'MMA', 'USA', 'ufc-fan-token', true),
    ('PFL', 'Professional Fighters League Fan Token', 'PFL', 'MMA', 'USA', 'professional-fighters-league-fan-token', true),

    -- Esports
    ('OG', 'OG Fan Token', 'OG Esports', 'Esports', NULL, 'og-fan-token', true),
    ('NAVI', 'Natus Vincere Fan Token', 'Natus Vincere', 'Esports', 'Ukraine', 'natus-vincere-fan-token', true),
    ('ALL', 'Alliance Fan Token', 'Alliance', 'Esports', 'Sweden', 'alliance-fan-token', true),
    ('TH', 'Team Heretics Fan Token', 'Team Heretics', 'Esports', 'Spain', 'team-heretics-fan-token', true),
    ('DOJO', 'Ninjas in Pyjamas Fan Token', 'Ninjas in Pyjamas', 'Esports', 'Sweden', 'ninjas-in-pyjamas', true),

    -- Individual
    ('MODRIC', 'Luka Modric Fan Token', 'Luka Modric', 'Individual', 'Croatia', 'luka-modric', true)

ON CONFLICT (symbol) DO UPDATE SET
    name = EXCLUDED.name,
    team = EXCLUDED.team,
    league = EXCLUDED.league,
    country = EXCLUDED.country,
    coingecko_id = EXCLUDED.coingecko_id,
    is_active = true;
