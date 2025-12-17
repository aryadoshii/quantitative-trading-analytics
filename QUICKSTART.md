# Quick Start Guide

**Get the system running in under 5 minutes!**

---

## Prerequisites Check

Before starting, ensure you have:
- [ ] Python 3.9 or higher: `python3 --version`
- [ ] Docker installed: `docker --version`
- [ ] docker-compose installed: `docker-compose --version`
- [ ] 2GB free RAM
- [ ] Internet connection (for WebSocket data)

---

## Installation (2 minutes)

### Step 1: Run Setup Script

```bash
./setup.sh
```

This will:
- Start TimescaleDB and Redis in Docker
- Install Python dependencies
- Create necessary directories

**Expected output:**
```
✓ Docker is installed
✓ docker-compose is installed
Starting Docker services...
Installing Python dependencies...
Setup Complete! ✅
```

---

## Testing (1 minute) - RECOMMENDED

Before running the full system, verify everything works:

```bash
python test_system.py
```

**Expected output:**
```
✓ PASS - Import Pandas
✓ PASS - Import NumPy
✓ PASS - TimescaleDB connection
✓ PASS - Redis connection
✓ PASS - Hedge ratio calculation
✓ PASS - WebSocket data reception

✓ All tests passed (6/6)
System is ready to run!
```

If any tests fail, check the troubleshooting section in README.md.

---

## Running the Application (2 minutes)

### Option 1: One-Command Start (Recommended)

```bash
./run.sh
```

This starts both backend and frontend automatically.

### Option 2: Manual Start (Two Terminals)

**Terminal 1 - Backend:**
```bash
python src/main.py
```

Wait for:
```
INFO | Database connection pool created
INFO | Connected to Redis
INFO | Starting WebSocket client for symbols: ['btcusdt', 'ethusdt']
INFO | Connected to btcusdt stream
INFO | Connected to ethusdt stream
```

**Terminal 2 - Frontend:**
```bash
streamlit run src/app.py
```

The dashboard will open automatically at: **http://localhost:8501**

---

## First Steps in Dashboard

### Minute 1: Wait for Data
- The system needs 30-60 seconds to accumulate enough data
- You'll see: "⚠️ No data available yet. Waiting for data ingestion..."
- This is normal!

### Minute 2: Explore Prices Tab
- Once data loads, you'll see BTC and ETH price charts
- Zoom, pan, and hover on charts

### Minute 3: Check Spread & Z-Score
- Switch to "Spread & Z-Score" tab
- Look for trading signals (z-score > ±2)
- Green box = signal detected

### Minute 4: Analyze Correlation
- View "Correlation" tab
- Check if correlation stays above 0.7
- Orange line = threshold

### Minute 5: Review Summary
- Go to "Summary" tab
- See all computed metrics
- Download data as CSV

---

## Configuration

### Change Symbols

Edit `config/settings.yaml`:
```yaml
DEFAULT_SYMBOLS: ["btcusdt", "ethusdt", "bnbusdt"]  # Add more symbols
```

Restart the application.

### Adjust Analytics Parameters

In the dashboard sidebar:
- **Rolling Window:** 20-200 (default: 60)
- **Z-Score Threshold:** 1.0-3.0 (default: 2.0)
- **Lookback Period:** 5-60 minutes (default: 30)

Changes apply immediately (no restart needed).

### Enable Alerts

Dashboard sidebar → Alerts section:
- ✓ Enable Alerts
- Set Z-Score Alert threshold
- Set Correlation Alert threshold

---

## Expected Behavior

### Normal Operation

```
[Backend logs]
INFO | Flushed 947 ticks to database
INFO | Resampled 56 1m bars for btcusdt
INFO | Z-score for btcusdt-ethusdt = 1.23

[Dashboard]
Current Z-Score: 🟢 1.23
Correlation: 0.892
ADF Test: ✅ Stationary
```

### Alert Triggered

```
[Backend]
WARNING | 🚨 ALERT: Z-score for btcusdt-ethusdt = 2.15

[Dashboard]
🚨 CRITICAL ALERT: Z-Score = 2.15 exceeds threshold 2.00!
🎯 SELL SPREAD - Spread is overextended, expect mean reversion
```

---

## Common Issues & Quick Fixes

### "No data available yet"
**Solution:** Wait 30-60 seconds. Backend needs time to collect data.

### "Connection refused" (Database)
```bash
docker-compose restart
sleep 10
python src/main.py
```

### WebSocket keeps disconnecting
**Cause:** Binance rate limits or network issues
**Solution:** Reduce number of symbols or wait a few minutes

### Dashboard is slow
**Cause:** Too much data in charts
**Solution:** 
- Reduce lookback period to 15-20 minutes
- Use 5m timeframe instead of 1s

---

## Stopping the Application

### If using run.sh:
Press `Ctrl+C` once (waits for graceful shutdown)

### If using manual terminals:
Press `Ctrl+C` in each terminal

### Stop Docker services:
```bash
docker-compose down
```

**Data persistence:** Your data is saved in Docker volumes and will be available when you restart.

---

## Next Steps

1. **Explore Features:**
   - Try different symbol pairs
   - Adjust analytics parameters
   - Set up custom alerts

2. **Understand Analytics:**
   - Read methodology in README.md
   - Experiment with different rolling windows
   - Observe z-score patterns

3. **Extend System:**
   - Add new analytics (see README.md "Extensibility")
   - Integrate more data sources
   - Build custom visualizations

4. **Read Documentation:**
   - Full README: `README.md`
   - Architecture: `docs/ARCHITECTURE.md`
   - AI usage: `docs/AI_USAGE.md`

---

## Video Demonstration

When creating your 2-minute video:

**0:00-0:15** Show the setup process
```bash
./setup.sh
python test_system.py  # Show all tests passing
```

**0:15-0:30** Start the application
```bash
./run.sh
```

**0:30-1:00** Explore dashboard features
- Switch between tabs
- Adjust parameters in sidebar
- Point out key metrics

**1:00-1:30** Demonstrate trading signal
- Show z-score exceeding threshold
- Explain interpretation
- Show alert triggering

**1:30-2:00** Highlight technical features
- Mention architecture (show diagram briefly)
- Point out data pipeline (backend logs)
- Emphasize extensibility

---

## Help & Support

If you encounter issues:

1. Check `logs/quantdev.log` for detailed errors
2. Review README.md troubleshooting section
3. Run `python test_system.py` to identify failing components
4. Verify Docker services: `docker ps`

---

**You're ready to go! Start with `./run.sh` and explore the dashboard.**

Good luck! 🚀
