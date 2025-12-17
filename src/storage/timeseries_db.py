"""
Database manager for TimescaleDB.
Handles schema creation, data insertion, and time-series queries.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import asyncpg
from loguru import logger
import pandas as pd


class TimeSeriesDB:
    """
    Async TimescaleDB manager for tick and resampled data.
    
    Schema:
    - ticks: Raw tick data
    - ohlcv_1s, ohlcv_1m, ohlcv_5m: Resampled OHLCV data
    """
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
        
    async def connect(self):
        """Create connection pool."""
        self.pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        logger.info("Database connection pool created")
        await self._initialize_schema()
        
    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def _initialize_schema(self):
        """Create tables and hypertables if they don't exist."""
        async with self.pool.acquire() as conn:
            # Enable TimescaleDB extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
            
            # Create ticks table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    size DOUBLE PRECISION NOT NULL,
                    trade_id BIGINT,
                    is_buyer_maker BOOLEAN,
                    PRIMARY KEY (time, symbol, trade_id)
                );
            """)
            
            # Convert to hypertable (idempotent)
            try:
                await conn.execute("""
                    SELECT create_hypertable('ticks', 'time', 
                                            chunk_time_interval => INTERVAL '1 hour',
                                            if_not_exists => TRUE);
                """)
            except Exception as e:
                logger.debug(f"Hypertable already exists or error: {e}")
            
            # Create index for faster symbol queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time 
                ON ticks (symbol, time DESC);
            """)
            
            # Create OHLCV tables for different timeframes
            for interval in ['1s', '1m', '5m']:
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS ohlcv_{interval} (
                        time TIMESTAMPTZ NOT NULL,
                        symbol TEXT NOT NULL,
                        open DOUBLE PRECISION NOT NULL,
                        high DOUBLE PRECISION NOT NULL,
                        low DOUBLE PRECISION NOT NULL,
                        close DOUBLE PRECISION NOT NULL,
                        volume DOUBLE PRECISION NOT NULL,
                        trade_count INTEGER,
                        PRIMARY KEY (time, symbol)
                    );
                """)
                
                try:
                    await conn.execute(f"""
                        SELECT create_hypertable('ohlcv_{interval}', 'time',
                                                chunk_time_interval => INTERVAL '1 day',
                                                if_not_exists => TRUE);
                    """)
                except Exception as e:
                    logger.debug(f"Hypertable ohlcv_{interval} setup: {e}")
                    
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_ohlcv_{interval}_symbol_time 
                    ON ohlcv_{interval} (symbol, time DESC);
                """)
            
            logger.info("Database schema initialized")
    
    async def insert_tick(self, tick: dict):
        """Insert a single tick into the database."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO ticks (time, symbol, price, size, trade_id, is_buyer_maker)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (time, symbol, trade_id) DO NOTHING;
            """, tick['timestamp'], tick['symbol'], tick['price'], 
                tick['size'], tick['trade_id'], tick['is_buyer_maker'])
    
    async def insert_ticks_batch(self, ticks: List[dict]):
        """Insert multiple ticks efficiently."""
        if not ticks:
            return
            
        async with self.pool.acquire() as conn:
            await conn.executemany("""
                INSERT INTO ticks (time, symbol, price, size, trade_id, is_buyer_maker)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (time, symbol, trade_id) DO NOTHING;
            """, [(t['timestamp'], t['symbol'], t['price'], t['size'], 
                   t['trade_id'], t['is_buyer_maker']) for t in ticks])
            
        logger.debug(f"Inserted batch of {len(ticks)} ticks")
    
    async def get_recent_ticks(
        self, 
        symbol: str, 
        minutes: int = 60,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """Fetch recent ticks for a symbol."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT time, symbol, price, size, is_buyer_maker
                FROM ticks
                WHERE symbol = $1 AND time > NOW() - INTERVAL '%s minutes'
                ORDER BY time DESC
            """ % minutes
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = await conn.fetch(query, symbol)
            
        if not rows:
            return pd.DataFrame()
            
        df = pd.DataFrame(rows, columns=['time', 'symbol', 'price', 'size', 'is_buyer_maker'])
        df['time'] = pd.to_datetime(df['time'])
        return df.sort_values('time')
    
    async def resample_and_store(self, symbol: str, interval: str):
        """
        Resample tick data to OHLCV and store.
        
        interval: '1s', '1m', or '5m'
        """
        # Map interval to SQL interval and pandas freq
        interval_map = {
            '1s': ('1 second', '1S'),
            '1m': ('1 minute', '1T'),
            '5m': ('5 minutes', '5T')
        }
        
        if interval not in interval_map:
            raise ValueError(f"Invalid interval: {interval}")
        
        sql_interval, pd_freq = interval_map[interval]
        
        async with self.pool.acquire() as conn:
            # Get last processed time
            last_time = await conn.fetchval(f"""
                SELECT MAX(time) FROM ohlcv_{interval} WHERE symbol = $1
            """, symbol)
            
            if last_time is None:
                # Start from 1 hour ago if no data
                last_time = datetime.now() - timedelta(hours=1)
            
            # Fetch tick data since last processed time
            rows = await conn.fetch("""
                SELECT time, price, size
                FROM ticks
                WHERE symbol = $1 AND time > $2
                ORDER BY time
            """, symbol, last_time)
            
            if not rows:
                return
            
            # Convert to DataFrame and resample
            df = pd.DataFrame(rows, columns=['time', 'price', 'size'])
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
            
            # Resample to OHLCV
            ohlcv = df['price'].resample(pd_freq).agg(['first', 'max', 'min', 'last'])
            ohlcv.columns = ['open', 'high', 'low', 'close']
            ohlcv['volume'] = df['size'].resample(pd_freq).sum()
            ohlcv['trade_count'] = df['price'].resample(pd_freq).count()
            
            # Remove empty bars
            ohlcv = ohlcv.dropna()
            
            if len(ohlcv) == 0:
                return
            
            # Insert OHLCV data
            records = [
                (idx, symbol, row['open'], row['high'], row['low'], 
                 row['close'], row['volume'], int(row['trade_count']))
                for idx, row in ohlcv.iterrows()
            ]
            
            await conn.executemany(f"""
                INSERT INTO ohlcv_{interval} 
                (time, symbol, open, high, low, close, volume, trade_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (time, symbol) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume,
                    trade_count = EXCLUDED.trade_count;
            """, records)
            
            logger.info(f"Resampled {len(records)} {interval} bars for {symbol}")
    
    async def get_ohlcv(
        self,
        symbol: str,
        interval: str,
        minutes: int = 60
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a symbol and interval."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT time, open, high, low, close, volume, trade_count
                FROM ohlcv_{interval}
                WHERE symbol = $1 AND time > NOW() - INTERVAL '{minutes} minutes'
                ORDER BY time
            """, symbol)
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'trade_count'])
        df['time'] = pd.to_datetime(df['time'])
        df = df.set_index('time')
        return df


if __name__ == "__main__":
    # Test database connection
    async def test():
        db = TimeSeriesDB("postgresql://trader:tradersecret@localhost:5432/trading_data")
        await db.connect()
        
        # Test tick insertion
        test_tick = {
            'timestamp': datetime.now(),
            'symbol': 'btcusdt',
            'price': 45000.0,
            'size': 0.1,
            'trade_id': 12345,
            'is_buyer_maker': False
        }
        await db.insert_tick(test_tick)
        
        # Fetch recent ticks
        df = await db.get_recent_ticks('btcusdt', minutes=5)
        print(f"Recent ticks: {len(df)}")
        
        await db.disconnect()
    
    asyncio.run(test())
