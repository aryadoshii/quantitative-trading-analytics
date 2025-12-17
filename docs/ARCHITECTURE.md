# Architecture Diagram Instructions for draw.io

## Overview
This document describes the system architecture to be visualized in draw.io.

## Main Components (Top to Bottom Layout)

### Layer 1: Data Source
```
┌──────────────────────────────────┐
│     Binance Futures API          │
│   wss://fstream.binance.com/ws   │
│                                  │
│  Symbols: BTC, ETH, BNB, SOL     │
│  Stream: @trade (tick data)      │
└──────────────────────────────────┘
```
- Color: Light Blue
- Icon: Cloud/Network
- Data format: JSON trades {symbol, price, size, timestamp}

### Layer 2: Ingestion Layer
```
┌──────────────────────────────────┐
│   WebSocket Client Manager       │
│  (src/ingestion/)                │
│                                  │
│  • Multi-symbol connections      │
│  • Auto-reconnection (exp backoff)│
│  • Data validation              │
│  • Normalization                │
│                                  │
│  Latency: <10ms per message     │
└──────────────────────────────────┘
```
- Color: Green
- Icon: Data flow
- Annotations: "Async/await pattern", "Error handling"

### Layer 3: Buffer & Cache Layer (3 components side-by-side)

**A. In-Memory Buffer**
```
┌──────────────────┐
│  TickBuffer      │
│  (Python deque)  │
│                  │
│  Max: 1000 ticks │
│  Latency: <1ms   │
└──────────────────┘
```
- Color: Yellow
- Use: Ultra-low latency analytics

**B. Redis Cache**
```
┌──────────────────┐
│   Redis Cache    │
│  (redis:7)       │
│                  │
│  • Tick buffers  │
│  • Analytics cache│
│  • Alert state   │
│                  │
│  TTL: 60s        │
│  Latency: <5ms   │
└──────────────────┘
```
- Color: Red
- Port: 6379

**C. TimescaleDB**
```
┌──────────────────┐
│   TimescaleDB    │
│  (Postgres 15)   │
│                  │
│  • Hypertables   │
│  • Compression   │
│  • OHLCV storage │
│                  │
│  Retention: 7d   │
└──────────────────┘
```
- Color: Purple
- Port: 5432

### Layer 4: Processing Engine
```
┌──────────────────────────────────┐
│      Analytics Engine            │
│   (src/analytics/)               │
│                                  │
│  Statistical Analytics:          │
│  • Hedge Ratio (OLS)             │
│  • Spread Calculation            │
│  • Z-Score (rolling)             │
│  • ADF Test (cointegration)      │
│  • Correlation (Pearson)         │
│  • Half-life (AR1)               │
│                                  │
│  Execution Analytics:            │
│  • VWAP                          │
│  • Trade Imbalance               │
│  • Volatility Regime             │
│  • Trend Detection               │
│                                  │
│  Update frequency: 5s            │
└──────────────────────────────────┘
```
- Color: Orange
- Icon: Calculator/Processor

### Layer 5: Alert Engine
```
┌──────────────────────────────────┐
│        Alert Engine              │
│     (src/alerts/)                │
│                                  │
│  Rule Types:                     │
│  • Z-score threshold             │
│  • Correlation break             │
│  • Volatility spike              │
│  • Custom conditions             │
│                                  │
│  Features:                       │
│  • Cooldown (60s)                │
│  • Rate limiting                 │
│  • Severity levels               │
│                                  │
│  Check interval: 500ms           │
└──────────────────────────────────┘
```
- Color: Red/Orange
- Icon: Bell/Alarm

### Layer 6: Presentation Layer
```
┌──────────────────────────────────┐
│    Streamlit Dashboard           │
│      (src/app.py)                │
│                                  │
│  Features:                       │
│  • Real-time charts (Plotly)     │
│  • Interactive controls          │
│  • Alert display                 │
│  • Data export (CSV)             │
│                                  │
│  Access: http://localhost:8501   │
└──────────────────────────────────┘
```
- Color: Blue
- Icon: Dashboard/Monitor

## Data Flow Arrows

### Main Flow (Top to Bottom)
1. Binance API → WebSocket Client (solid arrow, "Tick data")
2. WebSocket Client → All 3 buffers (split into 3 arrows)
3. Buffers → Analytics Engine (dotted arrows, "Read data")
4. Analytics Engine → Alert Engine (solid arrow, "Computed metrics")
5. Alert Engine → Dashboard (solid arrow, "Alerts")
6. Analytics Engine → Dashboard (solid arrow, "Analytics")

### Background Processes (Separate boxes with loop arrows)
```
┌─────────────────────┐      ┌─────────────────────┐
│ Resampling Task     │      │  Batch Flusher      │
│ (30s interval)      │      │  (5s or 1000 ticks) │
│                     │      │                     │
│ Ticks → OHLCV       │      │  Memory → Database  │
└─────────────────────┘      └─────────────────────┘
```

## Latency Annotations
Add these as small text boxes near relevant components:
- WebSocket → Buffer: "< 10ms"
- In-Memory Buffer: "< 1ms read"
- Redis: "< 5ms read/write"
- TimescaleDB: "< 50ms query"
- Analytics computation: "< 100ms"
- Alert check: "500ms cycle"
- Dashboard refresh: "5s interval"

## Failure Modes & Handling
Add small sidebar boxes:

**WebSocket Failure:**
→ Exponential backoff
→ Max 10 retries
→ Reconnect automatically

**Database Failure:**
→ Batch buffer in memory
→ Graceful degradation
→ Log errors

**Redis Failure:**
→ Use in-memory buffer
→ Skip caching layer
→ Continue operation

## Technology Stack Labels
Add small icons/labels at bottom:
- Python 3.9+
- asyncio
- TimescaleDB (PostgreSQL 15)
- Redis 7
- Streamlit 1.28
- Plotly 5.18
- statsmodels
- pandas/numpy

## Color Legend
- **Blue:** External services
- **Green:** Ingestion/Input
- **Yellow:** High-speed cache
- **Red:** Persistent storage
- **Orange:** Processing
- **Purple:** Output/UI

## Notes for draw.io
1. Use "Container" shapes for components
2. Use "Data Store" shapes for databases
3. Use solid arrows for data flow
4. Use dotted arrows for reads
5. Use curved arrows for async callbacks
6. Group related components with rectangles
7. Add shadow effects for depth
8. Export as both PNG (for README) and .drawio source

## Suggested draw.io Template
- Template: "Software Architecture"
- Layout: Vertical flow
- Grid: 10px
- Snap to grid: Enabled
- Connection style: Orthogonal
