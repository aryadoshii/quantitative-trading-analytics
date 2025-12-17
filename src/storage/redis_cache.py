"""
Redis cache manager for real-time data buffering and fast access.
Used for: recent ticks buffer, alert state, computed analytics cache.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import redis.asyncio as redis
from loguru import logger


class RedisCache:
    """
    Async Redis client for caching and buffering real-time data.
    
    Key patterns:
    - ticks:{symbol}:buffer -> List of recent ticks (FIFO)
    - analytics:{symbol}:{metric} -> Cached analytics values
    - alerts:{alert_id} -> Alert state and history
    """
    
    def __init__(self, redis_url: str, max_buffer_size: int = 10000):
        self.redis_url = redis_url
        self.max_buffer_size = max_buffer_size
        self.client: Optional[redis.Redis] = None
        
    async def connect(self):
        """Connect to Redis."""
        self.client = await redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("Connected to Redis")
        
    async def disconnect(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")
    
    async def buffer_tick(self, tick: dict):
        """
        Buffer a tick in Redis for fast access.
        Maintains a sliding window of recent ticks.
        """
        symbol = tick['symbol']
        key = f"ticks:{symbol}:buffer"
        
        # Serialize tick with timestamp
        tick_data = {
            'timestamp': tick['timestamp'].isoformat(),
            'price': tick['price'],
            'size': tick['size'],
            'is_buyer_maker': tick.get('is_buyer_maker', False)
        }
        
        # Push to list (right side = newest)
        await self.client.rpush(key, json.dumps(tick_data))
        
        # Trim to maintain max size (keep most recent)
        await self.client.ltrim(key, -self.max_buffer_size, -1)
        
        # Set expiry to 1 hour
        await self.client.expire(key, 3600)
    
    async def get_recent_ticks(self, symbol: str, count: int = 1000) -> List[dict]:
        """Get recent ticks from buffer."""
        key = f"ticks:{symbol}:buffer"
        
        # Get most recent 'count' ticks
        tick_strings = await self.client.lrange(key, -count, -1)
        
        ticks = []
        for tick_str in tick_strings:
            tick = json.loads(tick_str)
            tick['timestamp'] = datetime.fromisoformat(tick['timestamp'])
            ticks.append(tick)
        
        return ticks
    
    async def cache_analytics(
        self, 
        symbol: str, 
        metric: str, 
        value: any, 
        ttl: int = 60
    ):
        """
        Cache computed analytics with TTL.
        
        Args:
            symbol: Trading symbol
            metric: Metric name (e.g., 'zscore', 'spread', 'hedge_ratio')
            value: Computed value (will be JSON serialized)
            ttl: Time to live in seconds
        """
        key = f"analytics:{symbol}:{metric}"
        
        data = {
            'value': value,
            'timestamp': datetime.now().isoformat()
        }
        
        await self.client.setex(key, ttl, json.dumps(data))
    
    async def get_cached_analytics(
        self, 
        symbol: str, 
        metric: str
    ) -> Optional[dict]:
        """Retrieve cached analytics."""
        key = f"analytics:{symbol}:{metric}"
        data = await self.client.get(key)
        
        if data:
            parsed = json.loads(data)
            parsed['timestamp'] = datetime.fromisoformat(parsed['timestamp'])
            return parsed
        
        return None
    
    async def store_alert_state(self, alert_id: str, state: dict):
        """Store alert state (last triggered time, count, etc.)."""
        key = f"alerts:{alert_id}"
        state['last_updated'] = datetime.now().isoformat()
        await self.client.setex(key, 3600, json.dumps(state))
    
    async def get_alert_state(self, alert_id: str) -> Optional[dict]:
        """Get alert state."""
        key = f"alerts:{alert_id}"
        data = await self.client.get(key)
        
        if data:
            state = json.loads(data)
            state['last_updated'] = datetime.fromisoformat(state['last_updated'])
            return state
        
        return None
    
    async def increment_alert_count(self, alert_id: str) -> int:
        """Increment and return alert trigger count."""
        key = f"alerts:{alert_id}:count"
        count = await self.client.incr(key)
        await self.client.expire(key, 3600)  # Reset hourly
        return count
    
    async def get_buffer_size(self, symbol: str) -> int:
        """Get current buffer size for a symbol."""
        key = f"ticks:{symbol}:buffer"
        return await self.client.llen(key)
    
    async def clear_buffer(self, symbol: str):
        """Clear tick buffer for a symbol."""
        key = f"ticks:{symbol}:buffer"
        await self.client.delete(key)
        logger.info(f"Cleared buffer for {symbol}")
    
    async def get_all_symbols(self) -> List[str]:
        """Get list of all symbols currently in cache."""
        keys = await self.client.keys("ticks:*:buffer")
        symbols = [key.split(':')[1] for key in keys]
        return list(set(symbols))
    
    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


class TickBuffer:
    """
    In-memory tick buffer for ultra-low latency access.
    Complements Redis for immediate analytics computation.
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.buffers: Dict[str, List[dict]] = {}
    
    def add_tick(self, tick: dict):
        """Add tick to in-memory buffer."""
        symbol = tick['symbol']
        
        if symbol not in self.buffers:
            self.buffers[symbol] = []
        
        self.buffers[symbol].append(tick)
        
        # Trim if needed
        if len(self.buffers[symbol]) > self.max_size:
            self.buffers[symbol] = self.buffers[symbol][-self.max_size:]
    
    def get_ticks(self, symbol: str, count: Optional[int] = None) -> List[dict]:
        """Get recent ticks from buffer."""
        if symbol not in self.buffers:
            return []
        
        if count is None:
            return self.buffers[symbol]
        
        return self.buffers[symbol][-count:]
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get most recent price for a symbol."""
        ticks = self.get_ticks(symbol, count=1)
        return ticks[0]['price'] if ticks else None
    
    def clear(self, symbol: Optional[str] = None):
        """Clear buffer for specific symbol or all."""
        if symbol:
            self.buffers[symbol] = []
        else:
            self.buffers = {}


if __name__ == "__main__":
    import asyncio
    
    async def test():
        cache = RedisCache("redis://localhost:6379")
        await cache.connect()
        
        # Test health check
        healthy = await cache.health_check()
        print(f"Redis healthy: {healthy}")
        
        # Test tick buffering
        test_tick = {
            'symbol': 'btcusdt',
            'timestamp': datetime.now(),
            'price': 45000.0,
            'size': 0.1
        }
        await cache.buffer_tick(test_tick)
        
        # Retrieve ticks
        recent = await cache.get_recent_ticks('btcusdt', count=10)
        print(f"Retrieved {len(recent)} ticks")
        
        # Test analytics caching
        await cache.cache_analytics('btcusdt', 'zscore', 1.5, ttl=30)
        analytics = await cache.get_cached_analytics('btcusdt', 'zscore')
        print(f"Cached analytics: {analytics}")
        
        await cache.disconnect()
    
    asyncio.run(test())
