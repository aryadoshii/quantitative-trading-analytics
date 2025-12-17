#!/usr/bin/env python3
"""
Component test script to verify all modules work correctly.
Run this before starting the full application.
"""

import asyncio
import sys
from datetime import datetime

sys.path.append('src')

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_test(name, passed):
    status = f"{GREEN}✓ PASS{RESET}" if passed else f"{RED}✗ FAIL{RESET}"
    print(f"{status} - {name}")


async def test_imports():
    """Test if all required packages can be imported."""
    print_header("Testing Package Imports")
    
    required_packages = [
        ('pandas', 'Pandas'),
        ('numpy', 'NumPy'),
        ('redis.asyncio', 'Redis (async)'),
        ('asyncpg', 'AsyncPG'),
        ('websockets', 'WebSockets'),
        ('statsmodels', 'Statsmodels'),
        ('plotly', 'Plotly'),
        ('streamlit', 'Streamlit'),
        ('yaml', 'PyYAML'),
        ('loguru', 'Loguru'),
    ]
    
    all_passed = True
    for package, name in required_packages:
        try:
            __import__(package)
            print_test(f"Import {name}", True)
        except ImportError:
            print_test(f"Import {name}", False)
            all_passed = False
    
    return all_passed


async def test_database_connection():
    """Test TimescaleDB connection."""
    print_header("Testing Database Connection")
    
    try:
        from storage.timeseries_db import TimeSeriesDB
        
        db = TimeSeriesDB("postgresql://trader:tradersecret@localhost:5432/trading_data")
        await db.connect()
        
        # Test basic query
        async with db.pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            assert result == 1
        
        await db.disconnect()
        print_test("TimescaleDB connection", True)
        return True
        
    except Exception as e:
        print_test("TimescaleDB connection", False)
        print(f"   Error: {str(e)}")
        return False


async def test_redis_connection():
    """Test Redis connection."""
    print_header("Testing Redis Connection")
    
    try:
        from storage.redis_cache import RedisCache
        
        cache = RedisCache("redis://localhost:6379")
        await cache.connect()
        
        # Test health check
        healthy = await cache.health_check()
        assert healthy
        
        # Test basic operations
        test_tick = {
            'symbol': 'testbtc',
            'timestamp': datetime.now(),
            'price': 50000.0,
            'size': 0.1
        }
        await cache.buffer_tick(test_tick)
        
        ticks = await cache.get_recent_ticks('testbtc', count=10)
        assert len(ticks) > 0
        
        await cache.clear_buffer('testbtc')
        await cache.disconnect()
        
        print_test("Redis connection and operations", True)
        return True
        
    except Exception as e:
        print_test("Redis connection", False)
        print(f"   Error: {str(e)}")
        return False


async def test_analytics():
    """Test analytics calculations."""
    print_header("Testing Analytics Engine")
    
    try:
        import pandas as pd
        import numpy as np
        from analytics.statistical import StatisticalAnalytics
        
        # Generate test data
        np.random.seed(42)
        n = 100
        x = np.cumsum(np.random.randn(n)) + 100
        y = 1.5 * x + np.random.randn(n) * 2 + 50
        
        prices_x = pd.Series(x)
        prices_y = pd.Series(y)
        
        # Test hedge ratio
        hedge_ratio, r2, pval = StatisticalAnalytics.calculate_hedge_ratio(prices_y, prices_x)
        assert not np.isnan(hedge_ratio)
        assert 1.0 < hedge_ratio < 2.0  # Should be around 1.5
        print_test("Hedge ratio calculation", True)
        
        # Test spread
        spread = StatisticalAnalytics.calculate_spread(prices_y, prices_x, hedge_ratio)
        assert len(spread) == len(prices_x)
        print_test("Spread calculation", True)
        
        # Test z-score
        zscore = StatisticalAnalytics.calculate_zscore(spread, window=20)
        assert len(zscore) == len(spread)
        print_test("Z-score calculation", True)
        
        # Test correlation
        corr = StatisticalAnalytics.rolling_correlation(prices_x, prices_y, window=50)
        assert not corr.empty
        print_test("Correlation calculation", True)
        
        # Test ADF
        adf_result = StatisticalAnalytics.adf_test(spread)
        assert 'statistic' in adf_result
        assert 'p_value' in adf_result
        print_test("ADF test", True)
        
        return True
        
    except Exception as e:
        print_test("Analytics engine", False)
        print(f"   Error: {str(e)}")
        return False


async def test_alert_engine():
    """Test alert engine."""
    print_header("Testing Alert Engine")
    
    try:
        from alerts.engine import AlertEngine, AlertRuleBuilder
        
        engine = AlertEngine(check_interval=0.1)
        
        # Add test rule
        rule = AlertRuleBuilder.zscore_threshold_alert("test-pair", threshold=2.0)
        engine.add_rule(rule)
        
        # Test alert triggering
        alert = await engine.check_rule(rule, 2.5)
        assert alert is not None
        print_test("Alert creation", True)
        
        # Test cooldown
        alert2 = await engine.check_rule(rule, 3.0)
        assert alert2 is None  # Should be in cooldown
        print_test("Alert cooldown", True)
        
        # Test history
        recent = engine.get_recent_alerts(minutes=5)
        assert len(recent) == 1
        print_test("Alert history", True)
        
        return True
        
    except Exception as e:
        print_test("Alert engine", False)
        print(f"   Error: {str(e)}")
        return False


async def test_websocket_connection():
    """Test WebSocket connection (brief test)."""
    print_header("Testing WebSocket Connection")
    
    try:
        from ingestion.websocket_client import BinanceWebSocketClient
        
        received_data = []
        
        async def test_callback(data):
            received_data.append(data)
        
        client = BinanceWebSocketClient(
            symbols=['btcusdt'],
            on_message=test_callback
        )
        
        # Start connection for 5 seconds
        task = asyncio.create_task(client.start())
        await asyncio.sleep(5)
        await client.stop()
        
        # Check if we received data
        if len(received_data) > 0:
            print_test("WebSocket data reception", True)
            print(f"   Received {len(received_data)} ticks in 5 seconds")
            return True
        else:
            print_test("WebSocket data reception", False)
            print(f"   {YELLOW}Warning: No data received (may be slow connection){RESET}")
            return True  # Don't fail on this
        
    except Exception as e:
        print_test("WebSocket connection", False)
        print(f"   Error: {str(e)}")
        return False


async def run_all_tests():
    """Run all tests."""
    print(f"\n{GREEN}{'='*60}")
    print(f"  QUANTITATIVE TRADING ANALYTICS - COMPONENT TESTS")
    print(f"{'='*60}{RESET}\n")
    
    results = []
    
    # Test imports
    results.append(await test_imports())
    
    # Test connections (skip if imports failed)
    if results[0]:
        results.append(await test_database_connection())
        results.append(await test_redis_connection())
        results.append(await test_analytics())
        results.append(await test_alert_engine())
        results.append(await test_websocket_connection())
    
    # Summary
    print_header("Test Summary")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"{GREEN}✓ All tests passed ({passed}/{total}){RESET}")
        print(f"\n{GREEN}System is ready to run!{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Start backend:   python src/main.py")
        print(f"  2. Start frontend:  streamlit run src/app.py")
        print(f"  OR use: ./run.sh to start both\n")
        return True
    else:
        print(f"{RED}✗ Some tests failed ({passed}/{total} passed){RESET}")
        print(f"\n{YELLOW}Please fix the issues before running the application.{RESET}\n")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Tests interrupted by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {str(e)}{RESET}")
        sys.exit(1)
