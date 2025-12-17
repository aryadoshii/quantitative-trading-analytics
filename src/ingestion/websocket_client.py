"""
WebSocket client for real-time tick data ingestion from Binance Futures.
Handles connection management, reconnection logic, and data normalization.
"""

import asyncio
import json
from datetime import datetime
from typing import Callable, List, Optional
import websockets
from loguru import logger


class BinanceWebSocketClient:
    """
    Async WebSocket client for Binance Futures trade streams.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Data validation and normalization
    - Multiple symbol support
    - Graceful shutdown
    """
    
    def __init__(
        self,
        symbols: List[str],
        on_message: Callable,
        base_url: str = "wss://fstream.binance.com/ws",
        max_reconnect_attempts: int = 10
    ):
        self.symbols = [s.lower() for s in symbols]
        self.on_message = on_message
        self.base_url = base_url
        self.max_reconnect_attempts = max_reconnect_attempts
        self.connections = {}
        self.running = False
        
    async def connect_symbol(self, symbol: str):
        """Connect to WebSocket stream for a single symbol."""
        url = f"{self.base_url}/{symbol}@trade"
        reconnect_count = 0
        
        while self.running and reconnect_count < self.max_reconnect_attempts:
            try:
                async with websockets.connect(url) as websocket:
                    logger.info(f"Connected to {symbol} stream")
                    reconnect_count = 0  # Reset on successful connection
                    
                    async for message in websocket:
                        if not self.running:
                            break
                            
                        try:
                            data = json.loads(message)
                            if data.get('e') == 'trade':
                                normalized = self._normalize_trade(data)
                                await self.on_message(normalized)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON decode error for {symbol}: {e}")
                        except Exception as e:
                            logger.error(f"Error processing message for {symbol}: {e}")
                            
            except websockets.exceptions.WebSocketException as e:
                reconnect_count += 1
                delay = min(2 ** reconnect_count, 60)  # Exponential backoff, max 60s
                logger.warning(
                    f"WebSocket error for {symbol}: {e}. "
                    f"Reconnecting in {delay}s (attempt {reconnect_count}/{self.max_reconnect_attempts})"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Unexpected error for {symbol}: {e}")
                break
                
        logger.info(f"Connection closed for {symbol}")
    
    def _normalize_trade(self, raw_data: dict) -> dict:
        """
        Normalize Binance trade data to standard format.
        
        Input: Binance trade event
        Output: {symbol, timestamp, price, size, trade_id}
        """
        return {
            'symbol': raw_data['s'].lower(),
            'timestamp': datetime.fromtimestamp(raw_data['T'] / 1000.0),
            'price': float(raw_data['p']),
            'size': float(raw_data['q']),
            'trade_id': raw_data['t'],
            'is_buyer_maker': raw_data['m']  # True if sell, False if buy
        }
    
    async def start(self):
        """Start WebSocket connections for all symbols."""
        self.running = True
        logger.info(f"Starting WebSocket client for symbols: {self.symbols}")
        
        # Create tasks for each symbol
        tasks = [
            asyncio.create_task(self.connect_symbol(symbol))
            for symbol in self.symbols
        ]
        
        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """Gracefully stop all WebSocket connections."""
        logger.info("Stopping WebSocket client...")
        self.running = False
        await asyncio.sleep(1)  # Give connections time to close gracefully


class DataValidator:
    """Validates incoming tick data for quality and completeness."""
    
    @staticmethod
    def validate_tick(tick: dict) -> bool:
        """
        Validate tick data structure and values.
        
        Returns True if valid, False otherwise.
        """
        required_fields = ['symbol', 'timestamp', 'price', 'size']
        
        # Check all required fields present
        if not all(field in tick for field in required_fields):
            logger.warning(f"Missing required fields in tick: {tick}")
            return False
        
        # Validate price and size are positive
        if tick['price'] <= 0 or tick['size'] <= 0:
            logger.warning(f"Invalid price or size in tick: {tick}")
            return False
        
        # Validate timestamp is recent (within last 5 minutes)
        age = (datetime.now() - tick['timestamp']).total_seconds()
        if age > 300:
            logger.warning(f"Tick data too old: {age}s")
            return False
            
        return True


if __name__ == "__main__":
    # Test the WebSocket client
    async def test_callback(data):
        print(f"Received: {data}")
    
    client = BinanceWebSocketClient(
        symbols=["btcusdt", "ethusdt"],
        on_message=test_callback
    )
    
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        print("\nShutting down...")
