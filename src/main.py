"""
Main application orchestrator.
Coordinates data ingestion, storage, analytics, and alerts.
"""

import asyncio
import yaml
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from loguru import logger

# Import custom modules
import sys
sys.path.append('/home/claude/quantdev-assignment/src')

from ingestion.websocket_client import BinanceWebSocketClient, DataValidator
from storage.timeseries_db import TimeSeriesDB
from storage.redis_cache import RedisCache, TickBuffer
from analytics.statistical import StatisticalAnalytics
from analytics.pnl_tracker import PositionSimulator
from analytics.signal_quality import SignalQualityScorer
from analytics.risk import RiskAnalytics
from alerts.engine import AlertEngine, AlertRuleBuilder


class TradingAnalyticsApp:
    """
    Main application class that orchestrates all components.
    
    Architecture:
    WebSocket → Buffer → [Redis + TimescaleDB] → Analytics → Alerts → Frontend
    """
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Initialize components
        self.symbols = self.config.get('DEFAULT_SYMBOLS', ['btcusdt', 'ethusdt'])
        
        # Storage
        self.db = TimeSeriesDB(self.config['DATABASE_URL'])
        self.redis = RedisCache(self.config['REDIS_URL'])
        self.tick_buffer = TickBuffer(max_size=1000)
        
        # WebSocket client
        self.ws_client = None
        
        # Alert engine
        self.alert_engine = AlertEngine(
            check_interval=self.config['ALERTS']['check_interval']
        )
        
        # PnL Tracker / Position Simulator
        self.pnl_tracker = PositionSimulator(
            initial_capital=10000,
            entry_threshold=2.0,
            exit_threshold=0.2,
            position_size_pct=0.10,
            stop_loss_pct=0.05,
            take_profit_pct=0.10
        )
        
        # Batch buffer for efficient DB writes
        self.batch_buffer = []
        self.batch_size = self.config.get('BATCH_SIZE', 1000)
        self.last_flush_time = datetime.now()
        
        # State
        self.running = False
        
        # Setup logging
        log_file = self.config.get('LOG_FILE', 'logs/quantdev.log')
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, rotation="100 MB")
        
    async def initialize(self):
        """Initialize all components."""
        logger.info("Initializing Trading Analytics Application...")
        
        # Connect to databases
        await self.db.connect()
        await self.redis.connect()
        
        # Setup default alert rules
        self._setup_default_alerts()
        
        # Create WebSocket client
        self.ws_client = BinanceWebSocketClient(
            symbols=self.symbols,
            on_message=self.on_tick_received,
            base_url=self.config['BINANCE_WS_BASE'],
            max_reconnect_attempts=self.config['MAX_RECONNECT_ATTEMPTS']
        )
        
        logger.info(f"Application initialized for symbols: {self.symbols}")
    
    def _setup_default_alerts(self):
        """Setup default alert rules."""
        # Z-score threshold alerts for each pair
        if len(self.symbols) >= 2:
            pair = f"{self.symbols[0]}-{self.symbols[1]}"
            
            # Entry signal (z-score > 2)
            entry_rule = AlertRuleBuilder.mean_reversion_entry_alert(pair, entry_threshold=2.0)
            self.alert_engine.add_rule(entry_rule)
            
            # Correlation break
            corr_rule = AlertRuleBuilder.correlation_break_alert(pair, threshold=0.7)
            self.alert_engine.add_rule(corr_rule)
        
        # Register callback
        self.alert_engine.register_callback(self.on_alert_triggered)
        
        logger.info("Default alert rules configured")
    
    async def on_tick_received(self, tick: dict):
        """
        Callback when new tick is received from WebSocket.
        
        Processing flow:
        1. Validate tick
        2. Buffer in memory and Redis
        3. Batch for DB insertion
        4. Trigger analytics if needed
        """
        # Validate
        if not DataValidator.validate_tick(tick):
            return
        
        # Add to in-memory buffer
        self.tick_buffer.add_tick(tick)
        
        # Add to Redis buffer (async)
        await self.redis.buffer_tick(tick)
        
        # Add to batch buffer for DB
        self.batch_buffer.append(tick)
        
        # Flush batch if needed
        if len(self.batch_buffer) >= self.batch_size or \
           (datetime.now() - self.last_flush_time).total_seconds() > self.config['BUFFER_FLUSH_INTERVAL']:
            await self._flush_batch()
        
        # Trigger real-time analytics check (lightweight)
        await self._check_realtime_analytics(tick['symbol'])
    
    async def _flush_batch(self):
        """Flush batch buffer to database."""
        if not self.batch_buffer:
            return
        
        try:
            await self.db.insert_ticks_batch(self.batch_buffer)
            logger.debug(f"Flushed {len(self.batch_buffer)} ticks to database")
            self.batch_buffer = []
            self.last_flush_time = datetime.now()
        except Exception as e:
            logger.error(f"Error flushing batch: {e}")
    
    async def _check_realtime_analytics(self, symbol: str):
        """
        Check real-time analytics that need low latency.
        
        For example: z-score based on recent buffer.
        """
        # Get recent ticks from buffer
        ticks = self.tick_buffer.get_ticks(symbol, count=500)
        
        if len(ticks) < 60:  # Need minimum data
            return
        
        # Extract prices
        prices = [t['price'] for t in ticks]
        
        # Check cached analytics
        cached = await self.redis.get_cached_analytics(symbol, 'latest_price')
        
        # Update cache
        await self.redis.cache_analytics(symbol, 'latest_price', prices[-1], ttl=5)
    
    async def on_alert_triggered(self, alert):
        """Callback when alert is triggered."""
        logger.warning(f"🚨 {alert.severity.value.upper()}: {alert.message}")
        
        # Could push to notification service, webhook, etc.
        # For now, just log
    
    async def periodic_analytics_task(self):
        """
        Background task for periodic analytics computation.
        Runs every 5-10 seconds to update analytics.
        """
        while self.running:
            try:
                await self._compute_analytics()
                await asyncio.sleep(5)  # Run every 5 seconds
            except Exception as e:
                logger.error(f"Error in periodic analytics: {e}")
                await asyncio.sleep(10)
    
    async def _compute_analytics(self):
        """Compute analytics for all symbol pairs."""
        if len(self.symbols) < 2:
            return
        
        # For pairs trading, compute on first two symbols
        symbol_1, symbol_2 = self.symbols[0], self.symbols[1]
        
        # Get recent data from buffer
        ticks_1 = self.tick_buffer.get_ticks(symbol_1, count=500)
        ticks_2 = self.tick_buffer.get_ticks(symbol_2, count=500)
        
        if len(ticks_1) < 60 or len(ticks_2) < 60:
            return
        
        # Create price series
        import pandas as pd
        prices_1 = pd.Series([t['price'] for t in ticks_1])
        prices_2 = pd.Series([t['price'] for t in ticks_2])
        
        # Compute hedge ratio
        hedge_ratio, r2, pval = StatisticalAnalytics.calculate_hedge_ratio(prices_1, prices_2)
        
        if pd.isna(hedge_ratio):
            return
        
        # Compute spread
        spread = StatisticalAnalytics.calculate_spread(prices_1, prices_2, hedge_ratio)
        
        # Compute z-score
        zscore_series = StatisticalAnalytics.calculate_zscore(spread, window=60)
        current_zscore = zscore_series.iloc[-1] if not zscore_series.empty else None
        
        # Compute correlation
        corr_series = StatisticalAnalytics.rolling_correlation(prices_1, prices_2, window=100)
        current_corr = corr_series.iloc[-1] if not corr_series.empty else None
        
        # Compute ADF test and half-life for signal quality
        adf_result = StatisticalAnalytics.adf_test(spread)
        half_life = StatisticalAnalytics.calculate_half_life(spread)
        
        # Cache analytics
        pair = f"{symbol_1}-{symbol_2}"
        await self.redis.cache_analytics(pair, 'hedge_ratio', hedge_ratio, ttl=60)
        await self.redis.cache_analytics(pair, 'zscore', float(current_zscore) if pd.notna(current_zscore) else None, ttl=10)
        await self.redis.cache_analytics(pair, 'correlation', float(current_corr) if pd.notna(current_corr) else None, ttl=60)
        
        # Update PnL tracker with current data
        if pd.notna(current_zscore):
            latest_price_1 = prices_1.iloc[-1]
            latest_price_2 = prices_2.iloc[-1]
            current_spread_value = spread.iloc[-1]
            
            # Check for entry signal
            entry_msg = self.pnl_tracker.check_entry_signal(
                zscore=float(current_zscore),
                spread=float(current_spread_value),
                price_1=float(latest_price_1),
                price_2=float(latest_price_2),
                hedge_ratio=float(hedge_ratio),
                timestamp=datetime.now()
            )
            
            # Check for exit signal
            exit_msg = self.pnl_tracker.check_exit_signal(
                zscore=float(current_zscore),
                spread=float(current_spread_value),
                price_1=float(latest_price_1),
                price_2=float(latest_price_2),
                timestamp=datetime.now()
            )
            
            # Get unrealized PnL
            unrealized = self.pnl_tracker.get_unrealized_pnl(
                current_spread=float(current_spread_value),
                current_price_1=float(latest_price_1),
                current_price_2=float(latest_price_2)
            )
            
            # Convert datetime to ISO string for JSON serialization
            if unrealized.get('has_position') and 'entry_time' in unrealized:
                unrealized['entry_time'] = unrealized['entry_time'].isoformat()
            
            # Cache PnL data
            await self.redis.cache_analytics(pair, 'unrealized_pnl', unrealized, ttl=5)
            
            # Get performance metrics
            performance = self.pnl_tracker.get_performance_metrics()
            await self.redis.cache_analytics(pair, 'performance', performance, ttl=10)
            
            # Calculate Signal Quality Score
            signal_quality = SignalQualityScorer.calculate_composite_score(
                zscore=float(current_zscore),
                correlation=float(current_corr),
                spread=spread,
                adf_pvalue=adf_result.get('p_value') if adf_result else None,
                half_life=half_life,
                win_rate=performance.get('win_rate'),
                profit_factor=performance.get('profit_factor'),
                total_trades=performance.get('total_trades', 0)
            )
            
            # Cache signal quality
            await self.redis.cache_analytics(pair, 'signal_quality', signal_quality, ttl=10)
            
            # Calculate Risk Metrics
            if len(self.pnl_tracker.closed_trades) > 0:
                # Get trade returns
                trade_returns = pd.Series([t.pnl_percent for t in self.pnl_tracker.closed_trades])
                
                # Build equity curve
                cumulative_pnl = [self.pnl_tracker.initial_capital]
                for trade in self.pnl_tracker.closed_trades:
                    cumulative_pnl.append(cumulative_pnl[-1] + trade.pnl)
                equity_curve = pd.Series(cumulative_pnl)
                
                # Calculate risk metrics
                risk_metrics = RiskAnalytics.calculate_risk_metrics(
                    returns=trade_returns,
                    equity_curve=equity_curve,
                    win_rate=performance.get('win_rate'),
                    avg_win=performance.get('avg_win'),
                    avg_loss=performance.get('avg_loss'),
                    current_position_size=unrealized.get('size', 0) if unrealized.get('has_position') else 0,
                    max_position_size=self.pnl_tracker.initial_capital * 0.20  # 20% max
                )
                
                # Calculate portfolio health
                health = RiskAnalytics.calculate_portfolio_health_score(risk_metrics)
                risk_metrics['health'] = health
                
                # Cache risk metrics
                await self.redis.cache_analytics(pair, 'risk_metrics', risk_metrics, ttl=10)
        
        # Check alerts if z-score exists
        if pd.notna(current_zscore):
            for rule in self.alert_engine.rules.values():
                if rule.symbol == pair:
                    await self.alert_engine.check_rule(rule, float(current_zscore))
    
    async def periodic_resampling_task(self):
        """
        Background task for resampling tick data to OHLCV.
        Runs every 30 seconds.
        """
        while self.running:
            try:
                for symbol in self.symbols:
                    for interval in ['1s', '1m', '5m']:
                        await self.db.resample_and_store(symbol, interval)
                
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error in resampling task: {e}")
                await asyncio.sleep(60)
    
    async def start(self):
        """Start the application."""
        self.running = True
        logger.info("Starting Trading Analytics Application...")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.ws_client.start()),
            asyncio.create_task(self.periodic_analytics_task()),
            asyncio.create_task(self.periodic_resampling_task())
        ]
        
        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop the application gracefully."""
        logger.info("Stopping application...")
        self.running = False
        
        # Flush remaining ticks
        await self._flush_batch()
        
        # Stop WebSocket
        if self.ws_client:
            await self.ws_client.stop()
        
        # Disconnect from databases
        await self.db.disconnect()
        await self.redis.disconnect()
        
        logger.info("Application stopped")


async def main():
    """Main entry point."""
    app = TradingAnalyticsApp()
    
    try:
        await app.initialize()
        await app.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
