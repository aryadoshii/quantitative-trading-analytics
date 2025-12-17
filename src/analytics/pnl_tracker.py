"""
Live PnL Tracker and Position Simulator for Statistical Arbitrage.

Simulates trading positions based on z-score signals and tracks hypothetical PnL.
Demonstrates real-world trading application of statistical arbitrage signals.
"""

from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import pandas as pd
import numpy as np
from loguru import logger


@dataclass
class Position:
    """Represents an open trading position."""
    entry_time: datetime
    entry_zscore: float
    entry_spread: float
    entry_price_1: float
    entry_price_2: float
    direction: str  # 'long' or 'short'
    size: float  # Position size in USD
    hedge_ratio: float


@dataclass
class ClosedTrade:
    """Represents a completed trade with PnL."""
    entry_time: datetime
    exit_time: datetime
    entry_zscore: float
    exit_zscore: float
    direction: str
    size: float
    pnl: float
    pnl_percent: float
    hold_duration: float  # in seconds
    max_favorable: float  # max unrealized profit during trade
    max_adverse: float  # max unrealized loss during trade


class PositionSimulator:
    """
    Simulates statistical arbitrage positions based on z-score signals.
    
    Strategy Logic:
    - Entry: |z-score| > entry_threshold (default: 2.0)
    - Exit: z-score crosses zero OR hits stop loss
    - Direction: Short spread when z > 0, Long spread when z < 0
    
    Position Sizing:
    - Configurable capital allocation per trade
    - Tracks total capital and cumulative PnL
    
    Features:
    - Real-time unrealized PnL tracking
    - Trade history with detailed metrics
    - Win rate and Sharpe ratio calculation
    - Max drawdown monitoring
    """
    
    def __init__(
        self,
        initial_capital: float = 10000,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.2,
        position_size_pct: float = 0.10,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.10
    ):
        """
        Initialize position simulator.
        
        Args:
            initial_capital: Starting capital in USD
            entry_threshold: Z-score threshold for entry (e.g., 2.0)
            exit_threshold: Z-score threshold for exit (close to 0)
            position_size_pct: % of capital to allocate per trade
            stop_loss_pct: Stop loss as % of position size
            take_profit_pct: Take profit as % of position size
        """
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.position_size_pct = position_size_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        
        self.current_position: Optional[Position] = None
        self.closed_trades: List[ClosedTrade] = []
        
        # Track extremes during position holding
        self.max_unrealized_profit = 0.0
        self.max_unrealized_loss = 0.0
        
        # Performance metrics
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0
        self.max_drawdown = 0.0
        self.peak_capital = initial_capital
    
    def check_entry_signal(
        self,
        zscore: float,
        spread: float,
        price_1: float,
        price_2: float,
        hedge_ratio: float,
        timestamp: datetime
    ) -> Optional[str]:
        """
        Check if entry signal is triggered.
        
        Returns signal message if entered, None otherwise.
        """
        # Don't enter if already in position
        if self.current_position is not None:
            return None
        
        # Check if z-score exceeds threshold
        if abs(zscore) > self.entry_threshold:
            direction = 'short' if zscore > 0 else 'long'
            size = self.current_capital * self.position_size_pct
            
            self.current_position = Position(
                entry_time=timestamp,
                entry_zscore=zscore,
                entry_spread=spread,
                entry_price_1=price_1,
                entry_price_2=price_2,
                direction=direction,
                size=size,
                hedge_ratio=hedge_ratio
            )
            
            # Reset tracking for new position
            self.max_unrealized_profit = 0.0
            self.max_unrealized_loss = 0.0
            
            logger.info(
                f"🎯 ENTRY: {direction.upper()} spread @ z={zscore:.2f}, "
                f"size=${size:.2f}"
            )
            
            return f"🎯 ENTRY: {direction.upper()} @ z={zscore:.2f}"
        
        return None
    
    def check_exit_signal(
        self,
        zscore: float,
        spread: float,
        price_1: float,
        price_2: float,
        timestamp: datetime
    ) -> Optional[str]:
        """
        Check if exit signal is triggered.
        
        Exit conditions:
        1. Z-score crosses threshold toward zero
        2. Stop loss hit
        3. Take profit hit
        
        Returns signal message if exited, None otherwise.
        """
        if self.current_position is None:
            return None
        
        pos = self.current_position
        
        # Calculate current PnL
        current_pnl, pnl_pct = self._calculate_pnl(spread, price_1, price_2)
        
        # Track extremes
        self.max_unrealized_profit = max(self.max_unrealized_profit, current_pnl)
        self.max_unrealized_loss = min(self.max_unrealized_loss, current_pnl)
        
        # Exit conditions
        should_exit = False
        exit_reason = ""
        
        # 1. Mean reversion complete (z-score near zero)
        if abs(zscore) < self.exit_threshold:
            should_exit = True
            exit_reason = "Mean reversion complete"
        
        # 2. Z-score crossed zero
        elif (pos.direction == 'long' and zscore > 0) or \
             (pos.direction == 'short' and zscore < 0):
            should_exit = True
            exit_reason = "Z-score crossed zero"
        
        # 3. Stop loss
        elif current_pnl < -(pos.size * self.stop_loss_pct):
            should_exit = True
            exit_reason = "Stop loss"
        
        # 4. Take profit
        elif current_pnl > (pos.size * self.take_profit_pct):
            should_exit = True
            exit_reason = "Take profit"
        
        if should_exit:
            return self._close_position(
                zscore, spread, price_1, price_2, timestamp, exit_reason
            )
        
        return None
    
    def _calculate_pnl(
        self,
        current_spread: float,
        current_price_1: float,
        current_price_2: float
    ) -> tuple:
        """Calculate current PnL for open position."""
        if self.current_position is None:
            return 0.0, 0.0
        
        pos = self.current_position
        
        # Spread change
        spread_change = current_spread - pos.entry_spread
        
        # PnL calculation
        # Long spread: profit when spread increases
        # Short spread: profit when spread decreases
        if pos.direction == 'long':
            pnl = pos.size * (spread_change / pos.entry_spread)
        else:  # short
            pnl = pos.size * (-spread_change / pos.entry_spread)
        
        pnl_pct = (pnl / pos.size) * 100
        
        return pnl, pnl_pct
    
    def _close_position(
        self,
        exit_zscore: float,
        exit_spread: float,
        exit_price_1: float,
        exit_price_2: float,
        exit_time: datetime,
        reason: str
    ) -> str:
        """Close current position and record trade."""
        if self.current_position is None:
            return None
        
        pos = self.current_position
        
        # Calculate final PnL
        pnl, pnl_pct = self._calculate_pnl(exit_spread, exit_price_1, exit_price_2)
        
        # Update capital
        self.current_capital += pnl
        self.total_pnl += pnl
        
        # Update peak and drawdown
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        self.max_drawdown = max(self.max_drawdown, drawdown)
        
        # Update win/loss count
        if pnl > 0:
            self.win_count += 1
        else:
            self.loss_count += 1
        
        # Hold duration
        hold_duration = (exit_time - pos.entry_time).total_seconds()
        
        # Create closed trade record
        trade = ClosedTrade(
            entry_time=pos.entry_time,
            exit_time=exit_time,
            entry_zscore=pos.entry_zscore,
            exit_zscore=exit_zscore,
            direction=pos.direction,
            size=pos.size,
            pnl=pnl,
            pnl_percent=pnl_pct,
            hold_duration=hold_duration,
            max_favorable=self.max_unrealized_profit,
            max_adverse=self.max_unrealized_loss
        )
        
        self.closed_trades.append(trade)
        
        logger.info(
            f"💰 EXIT ({reason}): {pos.direction.upper()} @ z={exit_zscore:.2f}, "
            f"PnL=${pnl:.2f} ({pnl_pct:.2f}%), "
            f"Total PnL=${self.total_pnl:.2f}"
        )
        
        # Clear position
        self.current_position = None
        
        return f"💰 EXIT ({reason}): PnL=${pnl:.2f} ({pnl_pct:+.2f}%)"
    
    def get_unrealized_pnl(
        self,
        current_spread: float,
        current_price_1: float,
        current_price_2: float
    ) -> Dict:
        """Get current unrealized PnL for open position."""
        if self.current_position is None:
            return {
                'has_position': False,
                'pnl': 0.0,
                'pnl_percent': 0.0
            }
        
        pnl, pnl_pct = self._calculate_pnl(current_spread, current_price_1, current_price_2)
        
        return {
            'has_position': True,
            'direction': self.current_position.direction,
            'entry_time': self.current_position.entry_time,
            'entry_zscore': self.current_position.entry_zscore,
            'size': self.current_position.size,
            'pnl': pnl,
            'pnl_percent': pnl_pct,
            'max_favorable': self.max_unrealized_profit,
            'max_adverse': self.max_unrealized_loss
        }
    
    def get_performance_metrics(self) -> Dict:
        """Calculate performance statistics."""
        total_trades = len(self.closed_trades)
        
        if total_trades == 0:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'total_pnl': 0.0,
                'current_capital': self.current_capital
            }
        
        # Win rate
        win_rate = (self.win_count / total_trades) * 100 if total_trades > 0 else 0
        
        # Average win/loss
        wins = [t.pnl for t in self.closed_trades if t.pnl > 0]
        losses = [t.pnl for t in self.closed_trades if t.pnl < 0]
        
        avg_win = np.mean(wins) if wins else 0
        avg_loss = abs(np.mean(losses)) if losses else 0
        
        # Profit factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # Sharpe ratio (simplified - based on trade PnL)
        returns = [t.pnl_percent for t in self.closed_trades]
        sharpe_ratio = 0.0
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                sharpe_ratio = (mean_return / std_return) * np.sqrt(252)  # Annualized
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': self.max_drawdown * 100,
            'total_pnl': self.total_pnl,
            'total_return': ((self.current_capital - self.initial_capital) / self.initial_capital) * 100,
            'current_capital': self.current_capital,
            'peak_capital': self.peak_capital
        }
    
    def get_trade_history(self) -> pd.DataFrame:
        """Get DataFrame of all closed trades."""
        if not self.closed_trades:
            return pd.DataFrame()
        
        trades_data = []
        for trade in self.closed_trades:
            trades_data.append({
                'Entry Time': trade.entry_time,
                'Exit Time': trade.exit_time,
                'Direction': trade.direction.upper(),
                'Entry Z-Score': trade.entry_zscore,
                'Exit Z-Score': trade.exit_zscore,
                'Size ($)': trade.size,
                'PnL ($)': trade.pnl,
                'PnL (%)': trade.pnl_percent,
                'Hold (min)': trade.hold_duration / 60,
                'Result': '✅ Win' if trade.pnl > 0 else '❌ Loss'
            })
        
        return pd.DataFrame(trades_data)


if __name__ == "__main__":
    # Test the simulator
    simulator = PositionSimulator(initial_capital=10000)
    
    # Simulate some trades
    print("Testing Position Simulator...")
    
    # Entry signal
    msg = simulator.check_entry_signal(
        zscore=2.5,
        spread=10.0,
        price_1=100.0,
        price_2=50.0,
        hedge_ratio=2.0,
        timestamp=datetime.now()
    )
    print(msg)
    
    # Check unrealized PnL
    unrealized = simulator.get_unrealized_pnl(8.0, 98.0, 49.0)
    print(f"Unrealized PnL: ${unrealized['pnl']:.2f}")
    
    # Exit signal
    msg = simulator.check_exit_signal(
        zscore=0.1,
        spread=8.0,
        price_1=98.0,
        price_2=49.0,
        timestamp=datetime.now()
    )
    print(msg)
    
    # Performance
    perf = simulator.get_performance_metrics()
    print(f"\nPerformance: {perf}")
