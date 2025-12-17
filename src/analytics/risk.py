"""
Risk Analytics Module - Institutional-grade risk management metrics.

Provides Value at Risk (VaR), Conditional Value at Risk (CVaR), Kelly Criterion,
and portfolio health assessment for trading strategies.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from loguru import logger


class RiskAnalytics:
    """
    Professional risk analytics for trading strategies.
    
    Provides institutional-grade risk metrics:
    - Value at Risk (VaR): Maximum expected loss at confidence level
    - Expected Shortfall (CVaR): Average loss beyond VaR
    - Kelly Criterion: Optimal position sizing
    - Risk-Adjusted Metrics: Sharpe, Sortino, Calmar ratios
    - Drawdown Analysis: Maximum and current drawdown
    """
    
    @staticmethod
    def calculate_var(
        returns: pd.Series,
        confidence: float = 0.95,
        method: str = 'historical'
    ) -> float:
        """
        Calculate Value at Risk (VaR).
        
        VaR represents the maximum expected loss over a given time period
        at a specified confidence level.
        
        Args:
            returns: Series of returns (can be PnL or %)
            confidence: Confidence level (e.g., 0.95 = 95%)
            method: 'historical' or 'parametric'
        
        Returns:
            VaR value (positive number representing potential loss)
        """
        if len(returns) < 20:
            return None
        
        if method == 'historical':
            # Historical VaR: empirical quantile
            var = np.percentile(returns, (1 - confidence) * 100)
        else:
            # Parametric VaR: assumes normal distribution
            mean = returns.mean()
            std = returns.std()
            from scipy.stats import norm
            z_score = norm.ppf(1 - confidence)
            var = mean + z_score * std
        
        return abs(var)
    
    @staticmethod
    def calculate_expected_shortfall(
        returns: pd.Series,
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Expected Shortfall (CVaR).
        
        Also known as Conditional Value at Risk (CVaR), this measures
        the average loss beyond the VaR threshold.
        
        Args:
            returns: Series of returns
            confidence: Confidence level
        
        Returns:
            Expected Shortfall (positive number)
        """
        if len(returns) < 20:
            return None
        
        var_threshold = np.percentile(returns, (1 - confidence) * 100)
        shortfall = returns[returns <= var_threshold].mean()
        
        return abs(shortfall)
    
    @staticmethod
    def calculate_kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing.
        
        Kelly % = (Win Rate * Win/Loss Ratio - Loss Rate) / Win/Loss Ratio
        
        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade size
            avg_loss: Average losing trade size (positive number)
        
        Returns:
            Optimal position size as fraction of capital (0-1)
        """
        if avg_loss == 0 or win_rate == 0:
            return 0.0
        
        loss_rate = 1 - win_rate
        win_loss_ratio = avg_win / abs(avg_loss)
        
        kelly = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio
        
        # Cap at 25% (full Kelly is often too aggressive)
        return max(0, min(kelly, 0.25))
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate annualized Sharpe Ratio.
        
        Sharpe = (Mean Return - Risk Free Rate) / Std Dev
        
        Args:
            returns: Series of returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year (252 for daily)
        
        Returns:
            Annualized Sharpe Ratio
        """
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        
        if excess_returns.std() == 0:
            return 0.0
        
        sharpe = excess_returns.mean() / excess_returns.std()
        sharpe_annual = sharpe * np.sqrt(periods_per_year)
        
        return sharpe_annual
    
    @staticmethod
    def calculate_sortino_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate annualized Sortino Ratio.
        
        Like Sharpe but only considers downside deviation.
        
        Args:
            returns: Series of returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year
        
        Returns:
            Annualized Sortino Ratio
        """
        if len(returns) < 2:
            return 0.0
        
        excess_returns = returns - (risk_free_rate / periods_per_year)
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        sortino = excess_returns.mean() / downside_returns.std()
        sortino_annual = sortino * np.sqrt(periods_per_year)
        
        return sortino_annual
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> Dict:
        """
        Calculate maximum drawdown and related metrics.
        
        Args:
            equity_curve: Series of cumulative equity
        
        Returns:
            Dict with max_drawdown, max_drawdown_pct, drawdown_duration
        """
        if len(equity_curve) < 2:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_pct': 0.0,
                'current_drawdown': 0.0,
                'current_drawdown_pct': 0.0,
                'peak_equity': equity_curve.iloc[0] if len(equity_curve) > 0 else 0
            }
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown
        drawdown = equity_curve - running_max
        drawdown_pct = (drawdown / running_max) * 100
        
        # Maximum drawdown
        max_dd = drawdown.min()
        max_dd_pct = drawdown_pct.min()
        
        # Current drawdown
        current_dd = drawdown.iloc[-1]
        current_dd_pct = drawdown_pct.iloc[-1]
        
        return {
            'max_drawdown': abs(max_dd),
            'max_drawdown_pct': abs(max_dd_pct),
            'current_drawdown': abs(current_dd),
            'current_drawdown_pct': abs(current_dd_pct),
            'peak_equity': running_max.iloc[-1]
        }
    
    @staticmethod
    def calculate_risk_metrics(
        returns: pd.Series,
        equity_curve: pd.Series,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        current_position_size: float = 0.0,
        max_position_size: float = 1000.0,
        confidence: float = 0.95
    ) -> Dict:
        """
        Calculate comprehensive risk metrics.
        
        Args:
            returns: Series of trade returns
            equity_curve: Series of cumulative equity
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade
            avg_loss: Average losing trade
            current_position_size: Current position size ($)
            max_position_size: Maximum allowed position size ($)
            confidence: VaR confidence level
        
        Returns:
            Dictionary of risk metrics
        """
        metrics = {}
        
        # VaR and CVaR
        if len(returns) >= 20:
            metrics['var_95'] = RiskAnalytics.calculate_var(returns, 0.95)
            metrics['var_99'] = RiskAnalytics.calculate_var(returns, 0.99)
            metrics['cvar_95'] = RiskAnalytics.calculate_expected_shortfall(returns, 0.95)
        else:
            metrics['var_95'] = None
            metrics['var_99'] = None
            metrics['cvar_95'] = None
        
        # Kelly Criterion
        if win_rate and avg_win and avg_loss:
            metrics['kelly_pct'] = RiskAnalytics.calculate_kelly_criterion(
                win_rate / 100 if win_rate > 1 else win_rate,
                avg_win,
                avg_loss
            ) * 100
        else:
            metrics['kelly_pct'] = None
        
        # Risk ratios
        if len(returns) >= 2:
            metrics['sharpe_ratio'] = RiskAnalytics.calculate_sharpe_ratio(returns)
            metrics['sortino_ratio'] = RiskAnalytics.calculate_sortino_ratio(returns)
        else:
            metrics['sharpe_ratio'] = None
            metrics['sortino_ratio'] = None
        
        # Drawdown metrics
        dd_metrics = RiskAnalytics.calculate_max_drawdown(equity_curve)
        metrics.update(dd_metrics)
        
        # Position exposure
        metrics['current_exposure'] = current_position_size
        metrics['max_exposure'] = max_position_size
        metrics['exposure_pct'] = (current_position_size / max_position_size * 100) if max_position_size > 0 else 0
        
        # Risk utilization (how much of risk budget is used)
        if metrics['var_95'] and max_position_size > 0:
            metrics['risk_utilization'] = (metrics['var_95'] / max_position_size * 100)
        else:
            metrics['risk_utilization'] = 0
        
        return metrics
    
    @staticmethod
    def calculate_portfolio_health_score(risk_metrics: Dict) -> Dict:
        """
        Calculate overall portfolio health score (0-100).
        
        Considers:
        - Drawdown level (lower = better)
        - Risk-adjusted returns (Sharpe/Sortino)
        - Position sizing (Kelly adherence)
        - Risk utilization
        
        Args:
            risk_metrics: Dict from calculate_risk_metrics()
        
        Returns:
            Dict with health_score and component scores
        """
        scores = {}
        
        # Drawdown score (0-100, lower drawdown = higher score)
        current_dd_pct = risk_metrics.get('current_drawdown_pct', 0)
        if current_dd_pct < 5:
            dd_score = 100
        elif current_dd_pct < 10:
            dd_score = 90 - (current_dd_pct - 5) * 2
        elif current_dd_pct < 20:
            dd_score = 80 - (current_dd_pct - 10)
        elif current_dd_pct < 40:
            dd_score = 70 - (current_dd_pct - 20) * 1.5
        else:
            dd_score = max(0, 40 - (current_dd_pct - 40))
        
        scores['drawdown_score'] = dd_score
        
        # Sharpe ratio score
        sharpe = risk_metrics.get('sharpe_ratio', 0)
        if sharpe is None:
            sharpe_score = 50
        elif sharpe >= 2.0:
            sharpe_score = 100
        elif sharpe >= 1.0:
            sharpe_score = 70 + (sharpe - 1.0) * 30
        elif sharpe >= 0:
            sharpe_score = 50 + sharpe * 20
        else:
            sharpe_score = max(0, 50 + sharpe * 50)
        
        scores['sharpe_score'] = sharpe_score
        
        # Risk utilization score (want 50-80% utilization)
        risk_util = risk_metrics.get('risk_utilization', 0)
        if 50 <= risk_util <= 80:
            util_score = 100
        elif risk_util < 50:
            util_score = 70 + risk_util * 0.6
        else:
            util_score = max(0, 100 - (risk_util - 80))
        
        scores['utilization_score'] = util_score
        
        # Composite health score (weighted average)
        health_score = (
            dd_score * 0.40 +
            sharpe_score * 0.35 +
            util_score * 0.25
        )
        
        # Determine health level
        if health_score >= 80:
            health_level = "Excellent"
            health_emoji = "🟢"
        elif health_score >= 65:
            health_level = "Good"
            health_emoji = "🟢"
        elif health_score >= 50:
            health_level = "Fair"
            health_emoji = "🟡"
        elif health_score >= 35:
            health_level = "Poor"
            health_emoji = "🟠"
        else:
            health_level = "Critical"
            health_emoji = "🔴"
        
        return {
            'health_score': health_score,
            'health_level': health_level,
            'health_emoji': health_emoji,
            'component_scores': scores
        }


if __name__ == "__main__":
    # Test risk analytics
    print("Testing Risk Analytics...")
    
    # Generate sample returns
    np.random.seed(42)
    returns = pd.Series(np.random.randn(100) * 50)
    equity_curve = returns.cumsum() + 10000
    
    # Calculate metrics
    metrics = RiskAnalytics.calculate_risk_metrics(
        returns=returns,
        equity_curve=equity_curve,
        win_rate=55,
        avg_win=75,
        avg_loss=50,
        current_position_size=500,
        max_position_size=1000
    )
    
    print("\nRisk Metrics:")
    for key, value in metrics.items():
        if value is not None:
            print(f"  {key}: {value:.2f}" if isinstance(value, (int, float)) else f"  {key}: {value}")
    
    # Calculate health score
    health = RiskAnalytics.calculate_portfolio_health_score(metrics)
    print(f"\nPortfolio Health: {health['health_emoji']} {health['health_score']:.1f}/100 - {health['health_level']}")
