# Chiliz Marketing Intelligence v3.0

**Executive-focused analytics platform for fan token market intelligence**

## Overview

This is a complete rebuild of the Chiliz Marketing Intelligence platform with a focus on:
- **Five Pillars Model**: Price, Volume, Holders, Spread, Liquidity
- **TimescaleDB**: Time-series optimized database
- **Multi-Exchange Coverage**: 14+ exchanges via CoinGecko Pro
- **AI Management Assistant**: Natural language Q&A using Claude
- **Health Scoring System**: 0-100 scores with A-F grades
- **Executive Dashboard**: C-level focused visualizations

## Architecture

```
v3/
├── api/                    # FastAPI Backend
│   ├── main.py            # Application entry point
│   └── routes/
│       ├── tokens.py      # Token endpoints
│       ├── executive.py   # Executive dashboard endpoints
│       ├── assistant.py   # AI Assistant chat
│       └── alerts.py      # Signals and alerts
│
├── services/              # Data Collection Services
│   ├── database.py        # TimescaleDB connection
│   ├── price_collector.py # Price & Volume (Pillars 1&2)
│   ├── spread_monitor.py  # Spread tracking (Pillar 4)
│   ├── liquidity_analyzer.py # Order book depth (Pillar 5)
│   ├── holder_tracker.py  # On-chain holders (Pillar 3)
│   ├── social_tracker.py  # X/Twitter sentiment
│   ├── aggregator.py      # Cross-exchange aggregation
│   ├── correlation_engine.py # Cross-pillar analysis
│   └── health_scorer.py   # Health score calculation
│
├── config/
│   └── settings.py        # Configuration and API keys
│
├── migrations/
│   └── 001_core_schema.sql # TimescaleDB schema
│
├── dashboard/             # Next.js Executive Dashboard
│   ├── app/
│   │   ├── page.tsx       # Main dashboard
│   │   ├── tokens/        # Token list
│   │   └── assistant/     # AI Chat
│   └── components/
│       └── executive/     # Dashboard components
│
├── run.py                 # Main service runner
├── requirements.txt       # Python dependencies
├── railway.toml          # Railway deployment config
└── Procfile              # Process definitions
```

## Five Pillars Model

1. **Price**: Real-time prices from 14+ exchanges, VWAP calculation
2. **Volume**: 24h trading volume, trade counts, exchange breakdown
3. **Holders**: On-chain holder counts, distribution analysis, Gini coefficient
4. **Spread**: Bid-ask spreads in basis points, market efficiency
5. **Liquidity**: Order book depth at 1%/2%/5% levels, slippage estimation

## Health Scoring System

Each token receives a health score (0-100) based on:
- **Volume** (25%): Trading activity vs benchmarks
- **Liquidity** (25%): Ability to absorb large trades
- **Spread** (20%): Market efficiency
- **Holders** (15%): Community growth and distribution
- **Price Stability** (15%): Volatility and price action

Grades:
- **A** (90-100): Excellent health
- **B** (75-89): Good health
- **C** (60-74): Fair health
- **D** (40-59): Poor health
- **F** (0-39): Critical

## API Endpoints

### Token Data
- `GET /api/tokens` - All tokens with latest metrics
- `GET /api/tokens/{symbol}` - Detailed token info
- `GET /api/tokens/{symbol}/history` - Historical data
- `GET /api/tokens/{symbol}/exchanges` - Exchange breakdown

### Executive Dashboard
- `GET /api/executive/overview` - Portfolio summary
- `GET /api/executive/health-matrix` - Health grades matrix
- `GET /api/executive/liquidity-report` - Liquidity analysis
- `GET /api/executive/holder-insights` - Community metrics
- `GET /api/executive/correlation-summary` - Cross-pillar correlations
- `GET /api/executive/daily-brief` - Daily management brief

### AI Assistant
- `POST /api/assistant/chat` - Chat with AI
- `GET /api/assistant/suggested-questions` - Question suggestions
- `GET /api/assistant/history/{session_id}` - Chat history

### Alerts
- `GET /api/alerts/active` - Active signals
- `GET /api/alerts/history` - Signal history
- `POST /api/alerts/resolve/{id}` - Resolve alert
- `GET /api/alerts/rules` - Alert rules
- `POST /api/alerts/rules` - Create rule

## Environment Variables

```bash
# TimescaleDB
TIMESCALE_HOST=your-host
TIMESCALE_PORT=5432
TIMESCALE_DB=chiliz_intel
TIMESCALE_USER=postgres
TIMESCALE_PASSWORD=your-password

# CoinGecko Pro ($129/mo)
COINGECKO_API_KEY=your-key

# X Premium ($200/mo)
X_BEARER_TOKEN=your-token

# OpenRouter (AI)
OPENROUTER_API_KEY=your-key

# Slack
SLACK_WEBHOOK_URL=your-webhook
```

## Running Locally

### Backend Services

```bash
cd v3

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run data collection services
python run.py
```

### API Server

```bash
cd v3
uvicorn api.main:app --reload --port 8000
```

### Dashboard

```bash
cd v3/dashboard
npm install
npm run dev
```

## Deployment to Railway

1. Create a new Railway project
2. Add TimescaleDB from the marketplace
3. Deploy the API service:
   ```bash
   railway up
   ```
4. Set environment variables in Railway dashboard
5. Deploy dashboard separately or as part of monorepo

## Data Collection Intervals

| Service | Interval |
|---------|----------|
| Price/Volume | 60s |
| Spread | 60s |
| Liquidity | 5min |
| Holders | 1hr |
| Social | 15min |
| Aggregation | 5min |
| Correlation | Daily |
| Health Score | 5min |

## API Costs

- **CoinGecko Pro**: $129/month (500 req/min)
- **X Premium**: $200/month (450 req/15min)
- **OpenRouter**: ~$0.03/query (Claude 3.5 Sonnet)

## Contributing

This is an internal Chiliz platform. Contact the dev team for access.

## License

Proprietary - Chiliz Internal Use Only
