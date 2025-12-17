# Quantitative Trading Analytics System

**Real-time pairs trading analytics with statistical arbitrage signals**

A complete end-to-end system for ingesting live cryptocurrency tick data, computing statistical analytics, and visualizing trading opportunities through an interactive dashboard.

---

## 🎯 Project Overview

This system demonstrates production-grade quantitative trading infrastructure by:

- **Ingesting** real-time tick data from Binance WebSocket streams
- **Storing** time-series data efficiently in TimescaleDB with Redis caching
- **Computing** statistical arbitrage metrics (hedge ratio, spread, z-score, cointegration)
- **Visualizing** analytics through an interactive Streamlit dashboard
- **Alerting** on trading opportunities based on customizable rules

---

## 🏗️ Architecture

```
┌─────────────────┐
│  Binance WS     │  Live tick data (BTC, ETH, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Data Ingestion │  WebSocket client with reconnection
│    & Validation │  Data normalization & validation
└────────┬────────┘
         │
         ├──────────────────┬──────────────────┐
         ▼                  ▼                  ▼
┌─────────────┐    ┌──────────────┐   ┌──────────────┐
│ In-Memory   │    │    Redis     │   │ TimescaleDB  │
│   Buffer    │    │    Cache     │   │  (Postgres)  │
│ (Low latency)    │ (Fast access)│   │ (Persistence)│
└─────────────┘    └──────────────┘   └──────────────┘
         │                  │                  │
         └──────────────────┴──────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │   Analytics     │
                   │     Engine      │
                   │ • Hedge Ratio   │
                   │ • Spread/Z-score│
                   │ • Cointegration │
                   │ • Correlation   │
                   └────────┬────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
        ┌───────────────┐      ┌───────────────┐
        │ Alert Engine  │      │   Streamlit   │
        │ • Rule-based  │      │   Dashboard   │
        │ • Real-time   │      │ • Interactive │
        └───────────────┘      └───────────────┘
```

### Key Design Decisions

**1. TimescaleDB over Standard PostgreSQL**
- **Pro:** 10-100x faster time-series queries, automatic compression, better indexing
- **Con:** Additional dependency
- **Decision:** Essential for handling high-frequency tick data efficiently

**2. Redis Streams for Real-time Buffering**
- **Pro:** Sub-millisecond latency, persistence, simple operations
- **Con:** Less scalable than Kafka for very high throughput
- **Decision:** Perfect for prototype, easy migration path to Kafka documented

**3. Async Python Architecture**
- **Pro:** Non-blocking I/O for WebSocket + Database operations
- **Con:** Slightly more complex code
- **Decision:** Critical for handling concurrent data streams

**4. Batch Insertion Pattern**
- **Pro:** Reduces database load by 10-100x vs. individual inserts
- **Con:** Small latency (up to 5 seconds) before data appears
- **Decision:** Worth it for scalability; real-time analytics use in-memory buffer

---

## 📊 Analytics Implemented

### Core Statistical Metrics

1. **Hedge Ratio (OLS Regression)**
   - Linear regression coefficient between two price series
   - Used to calculate spread: `spread = price1 - β * price2`

2. **Spread & Z-Score**
   - Z-score = (spread - rolling_mean) / rolling_std
   - Indicates how many standard deviations from mean
   - Values > 2 or < -2 suggest mean-reversion opportunity

3. **Cointegration Test (ADF)**
   - Augmented Dickey-Fuller test for spread stationarity
   - p-value < 0.05 suggests cointegrated pair (tradeable)

4. **Rolling Correlation**
   - Pearson correlation over rolling window
   - Values < 0.7 suggest relationship breakdown

### Advanced Features

5. **Half-Life of Mean Reversion**
   - AR(1) model to estimate reversion speed
   - Helps size positions and set exit timeframes

6. **Volatility Regime Detection**
   - Classifies current volatility as low/normal/high
   - Adaptive strategy parameters based on regime

7. **Trend Detection**
   - Linear regression slope analysis
   - Distinguishes trending vs. mean-reverting markets

### Execution Analytics

8. **VWAP Tracking**
   - Volume-weighted average price
   - Execution quality metric

9. **Trade Imbalance**
   - Buy vs. sell pressure indicator
   - Range: [-1, 1]

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Docker & docker-compose
- 2GB RAM minimum
- Internet connection for WebSocket data

### Installation

```bash
# Clone or extract the project
cd quantdev-assignment

# Run setup script (installs dependencies, starts databases)
./setup.sh
```

### Running the Application

**Terminal 1: Start Backend + Data Ingestion**
```bash
python src/main.py
```

**Terminal 2: Start Frontend Dashboard**
```bash
streamlit run src/app.py
```

The dashboard will be available at **http://localhost:8501**

### Expected Startup Sequence

1. **0-10 seconds:** Backend connects to databases, initializes schemas
2. **10-30 seconds:** WebSocket connects, tick data starts flowing
3. **30-60 seconds:** First resampled bars (1s, 1m) become available
4. **60-120 seconds:** Analytics become reliable (hedge ratio, z-score)
5. **5+ minutes:** Advanced analytics fully functional (cointegration test)

---

## 🎛️ Configuration

Edit `config/settings.yaml` to customize:

```yaml
# Change symbols
DEFAULT_SYMBOLS: ["btcusdt", "ethusdt", "bnbusdt"]

# Adjust analytics parameters
ANALYTICS:
  rolling_window_minutes: 60
  zscore_threshold: 2.0
  
# Alert settings
ALERTS:
  check_interval: 0.5  # 500ms
  max_alerts_per_minute: 10
```

---

## 📈 Using the Dashboard

### Main Features

1. **Symbol Selection** (sidebar)
   - Choose any two cryptocurrency pairs
   - Supports: BTC, ETH, BNB, SOL, ADA

2. **Timeframe Selection**
   - 1 second bars (high-frequency)
   - 1 minute bars (standard)
   - 5 minute bars (lower frequency)

3. **Interactive Charts**
   - **Prices Tab:** Compare two price series with volume
   - **Spread & Z-Score Tab:** Monitor trading signals
   - **Correlation Tab:** Track pairs relationship strength
   - **Summary Tab:** View all metrics + download data

4. **Real-time Alerts**
   - Configure z-score thresholds
   - Visual alerts for trading opportunities
   - Alert history tracking

### Trading Signals Interpretation

| Z-Score | Action | Rationale |
|---------|--------|-----------|
| > +2.0  | **SELL SPREAD** | Spread overextended, expect reversion down |
| < -2.0  | **BUY SPREAD** | Spread underextended, expect reversion up |
| [-2, +2] | **HOLD** | Within normal range |
| → 0     | **EXIT** | Mean reversion complete |

**Note:** These are statistical signals, not trading advice. Always consider:
- Cointegration strength (ADF test)
- Correlation stability (> 0.7)
- Volatility regime
- Transaction costs

---

## 🧪 Testing

```bash
# Test individual components
python src/ingestion/websocket_client.py
python src/storage/timeseries_db.py
python src/storage/redis_cache.py
python src/analytics/statistical.py
python src/alerts/engine.py

# Run unit tests (if implemented)
pytest tests/
```

---

## 📁 Project Structure

```
quantdev-assignment/
├── src/
│   ├── ingestion/
│   │   └── websocket_client.py      # Binance WebSocket client
│   ├── storage/
│   │   ├── timeseries_db.py         # TimescaleDB manager
│   │   └── redis_cache.py           # Redis caching layer
│   ├── analytics/
│   │   └── statistical.py           # Analytics engine
│   ├── alerts/
│   │   └── engine.py                # Alert system
│   ├── main.py                      # Application orchestrator
│   └── app.py                       # Streamlit dashboard
├── config/
│   └── settings.yaml                # Configuration
├── logs/                            # Application logs
├── docker-compose.yml               # Database containers
├── requirements.txt                 # Python dependencies
├── setup.sh                         # Setup script
└── README.md                        # This file
```

---

## 🔧 Troubleshooting

### "No data available yet"

- Ensure `python src/main.py` is running in another terminal
- Wait 30-60 seconds for data accumulation
- Check logs in `logs/quantdev.log`

### Database Connection Errors

```bash
# Restart Docker containers
docker-compose down
docker-compose up -d

# Wait 10 seconds then retry
```

### WebSocket Connection Issues

- Check internet connection
- Binance may have rate limits (unlikely for 2 symbols)
- Check logs for specific error messages

### High Memory Usage

- Reduce `MAX_BUFFER_SIZE` in config
- Reduce `BATCH_SIZE` for more frequent flushes
- Clear Redis periodically: `redis-cli FLUSHALL`

---

## 🎓 Methodology

### Statistical Arbitrage Strategy

This system implements a **pairs trading** approach based on mean-reversion:

1. **Pair Selection:** Choose two historically correlated assets
2. **Cointegration Test:** Verify long-term relationship (ADF test)
3. **Spread Construction:** `spread = price1 - β * price2`
4. **Signal Generation:** Enter when |z-score| > 2, exit when z-score → 0
5. **Risk Management:** Monitor correlation, adjust for volatility

### Hedge Ratio Calculation

Using Ordinary Least Squares (OLS) regression:
```
price1 = β * price2 + α + ε
```

The hedge ratio β minimizes the variance of the spread, making it suitable for mean-reversion.

### Z-Score Interpretation

The z-score normalizes the spread relative to its historical distribution:
```
z = (spread - μ) / σ
```

- **|z| < 1:** ~68% of observations (normal)
- **|z| < 2:** ~95% of observations (rare)
- **|z| > 2:** ~2.5% of observations (extreme, tradeable)

### Mean Reversion Half-Life

Estimated using AR(1) model:
```
Δspread_t = λ * spread_{t-1} + ε
half_life = -log(2) / log(1 + λ)
```

Typical half-lives: 5-50 bars. Longer = slower reversion.

---

## 🚀 Extensibility & Scaling

### Adding New Data Sources

The modular design makes it easy to add new data sources:

```python
# Example: Add CME futures data
class CMEWebSocketClient(BaseClient):
    def __init__(self, symbols, on_message):
        # Implement CME-specific connection logic
        pass
    
    def _normalize_trade(self, raw_data):
        # Normalize to standard format
        return {
            'symbol': ...,
            'timestamp': ...,
            'price': ...,
            'size': ...
        }
```

Just swap in `CMEWebSocketClient` in `main.py` - analytics remain unchanged.

### Horizontal Scaling

**Current:** Single instance, 2-5 symbols
**Scale to:** Multiple instances, 100+ symbols

```
Load Balancer
    ├── Ingestor 1 (BTC, ETH, BNB)
    ├── Ingestor 2 (SOL, ADA, DOT)
    └── Ingestor 3 (AVAX, MATIC, LINK)
           ↓
    Shared TimescaleDB + Redis
           ↓
   Distributed Analytics Workers
```

### Adding New Analytics

```python
# In src/analytics/statistical.py
class StatisticalAnalytics:
    @staticmethod
    def calculate_new_metric(prices, window):
        # Implement new metric
        return result

# In src/app.py
new_metric = StatisticalAnalytics.calculate_new_metric(prices, 60)
st.metric("New Metric", new_metric)
```

### Production Considerations

**Not implemented (out of scope for assignment):**
- Authentication & authorization
- HTTPS/WSS encryption
- High availability / failover
- Backtesting framework
- Order execution integration
- Position management
- PnL tracking

**Implementation would require:**
- FastAPI JWT authentication
- Load balancers (nginx/HAProxy)
- Database replication (TimescaleDB primary-replica)
- Message queue (Kafka) for event sourcing
- Monitoring (Prometheus + Grafana)

---

## 🤖 AI Tool Usage

This project was developed with assistance from Claude AI (Anthropic) for:

### Code Generation (~40% of total code)

1. **Database Schema Design (30 min)**
   - Prompt: "Design TimescaleDB schema optimized for tick data with hypertables"
   - Used: Table structure, indexing strategies
   - Modified: Adjusted retention policies, added custom columns

2. **Statistical Tests Implementation (45 min)**
   - Prompt: "Implement ADF test, half-life calculation, hedge ratio with statsmodels"
   - Used: Core statsmodels API calls
   - Modified: Added error handling, edge case handling, vectorization

3. **Streamlit Dashboard Layout (60 min)**
   - Prompt: "Create Streamlit dashboard with tabs, metrics, Plotly charts"
   - Used: Basic layout structure
   - Modified: Custom CSS, interactive controls, alert system

4. **Async Patterns & Error Handling (30 min)**
   - Prompt: "Async WebSocket client with reconnection and backoff"
   - Used: Reconnection logic skeleton
   - Modified: Custom backoff strategy, graceful shutdown

### Architecture & Design (~60% human)

- Overall system architecture
- Component interaction design
- Analytics engine logic
- Trading signal interpretation
- Documentation structure

### Code Written Independently

- All analytics methodology
- Alert engine design
- Data pipeline optimization
- Frontend state management
- Test scenarios

---

## 📝 License

This project was created for the Gemscap Quantitative Developer Intern evaluation.

---

## 👤 Author

**Arya Doshi**
- Email: arya.doshi22@vit.edu
- LinkedIn: [linkedin.com/in/aryadoshii](https://linkedin.com/in/aryadoshii)
- GitHub: [github.com/aryadoshii](https://github.com/aryadoshii)

---

## 🙏 Acknowledgments

- Gemscap Global Analyst Pvt. Ltd. for the assignment opportunity
- Binance for providing free WebSocket data access
- TimescaleDB & PostgreSQL communities
- Streamlit & Plotly for visualization tools

---

**Last Updated:** December 2024
