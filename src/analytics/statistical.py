"""
Core statistical analytics for pairs trading and statistical arbitrage.
Implements: spread calculation, z-score, hedge ratio (OLS), ADF test, correlation.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict
from scipy import stats
from statsmodels.tsa.stattools import adfuller
from statsmodels.regression.linear_model import OLS
from loguru import logger
import warnings
warnings.filterwarnings('ignore')


class StatisticalAnalytics:
    """
    Statistical analytics for pairs trading.
    
    Key metrics:
    - Hedge ratio (OLS regression)
    - Spread and z-score
    - Cointegration test (ADF)
    - Rolling correlation
    """
    
    @staticmethod
    def calculate_hedge_ratio(
        y: pd.Series, 
        x: pd.Series,
        method: str = 'ols'
    ) -> Tuple[float, float, float]:
        """
        Calculate hedge ratio between two price series.
        
        Args:
            y: Dependent variable (e.g., ETH price)
            x: Independent variable (e.g., BTC price)
            method: 'ols' or 'tls' (total least squares)
        
        Returns:
            (hedge_ratio, r_squared, p_value)
        """
        # Align series
        df = pd.DataFrame({'y': y, 'x': x}).dropna()
        
        if len(df) < 20:
            return np.nan, np.nan, np.nan
        
        if method == 'ols':
            # OLS: y = beta * x + alpha
            model = OLS(df['y'], df['x']).fit()
            hedge_ratio = model.params[0]
            r_squared = model.rsquared
            p_value = model.pvalues[0]
            
        else:
            # TLS: minimize perpendicular distance
            # Use scipy for total least squares
            coeffs = np.polyfit(df['x'], df['y'], 1)
            hedge_ratio = coeffs[0]
            r_squared = np.corrcoef(df['x'], df['y'])[0, 1] ** 2
            p_value = np.nan
        
        return hedge_ratio, r_squared, p_value
    
    @staticmethod
    def calculate_spread(
        price_1: pd.Series,
        price_2: pd.Series,
        hedge_ratio: float
    ) -> pd.Series:
        """
        Calculate spread: spread = price_1 - hedge_ratio * price_2
        
        For pairs trading, this represents the relative mispricing.
        """
        # Align series
        df = pd.DataFrame({'p1': price_1, 'p2': price_2}).dropna()
        spread = df['p1'] - hedge_ratio * df['p2']
        return spread
    
    @staticmethod
    def calculate_zscore(
        series: pd.Series,
        window: int = 60,
        min_periods: int = 20
    ) -> pd.Series:
        """
        Calculate rolling z-score: (x - mean) / std
        
        Z-score indicates how many standard deviations away from mean.
        Used for mean-reversion signals.
        """
        if len(series) < min_periods:
            return pd.Series(np.nan, index=series.index)
        
        # Rolling mean and std
        rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
        rolling_std = series.rolling(window=window, min_periods=min_periods).std()
        
        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)
        
        zscore = (series - rolling_mean) / rolling_std
        return zscore
    
    @staticmethod
    def adf_test(
        series: pd.Series,
        max_lag: Optional[int] = None,
        significance: float = 0.05
    ) -> Dict[str, any]:
        """
        Augmented Dickey-Fuller test for stationarity/cointegration.
        
        H0: Series has unit root (non-stationary)
        H1: Series is stationary
        
        Returns:
            {
                'statistic': test statistic,
                'p_value': p-value,
                'is_stationary': True if reject H0,
                'critical_values': dict of critical values
            }
        """
        if len(series) < 20:
            return {
                'statistic': np.nan,
                'p_value': np.nan,
                'is_stationary': False,
                'critical_values': {}
            }
        
        # Remove NaN
        series_clean = series.dropna()
        
        if len(series_clean) < 20:
            return {
                'statistic': np.nan,
                'p_value': np.nan,
                'is_stationary': False,
                'critical_values': {}
            }
        
        try:
            result = adfuller(series_clean, maxlag=max_lag)
            
            return {
                'statistic': result[0],
                'p_value': result[1],
                'is_stationary': result[1] < significance,
                'critical_values': result[4],
                'used_lag': result[2],
                'n_obs': result[3]
            }
        except Exception as e:
            logger.error(f"ADF test failed: {e}")
            return {
                'statistic': np.nan,
                'p_value': np.nan,
                'is_stationary': False,
                'critical_values': {}
            }
    
    @staticmethod
    def rolling_correlation(
        series_1: pd.Series,
        series_2: pd.Series,
        window: int = 100
    ) -> pd.Series:
        """
        Calculate rolling correlation between two series.
        
        High correlation is necessary (but not sufficient) for pairs trading.
        """
        # Align series
        df = pd.DataFrame({'s1': series_1, 's2': series_2}).dropna()
        
        if len(df) < window:
            return pd.Series(np.nan, index=df.index)
        
        correlation = df['s1'].rolling(window=window).corr(df['s2'])
        return correlation
    
    @staticmethod
    def calculate_half_life(spread: pd.Series) -> float:
        """
        Calculate half-life of mean reversion using AR(1) model.
        
        Half-life = -log(2) / log(lambda)
        where lambda is AR(1) coefficient
        
        Interpretation: time for spread to revert halfway to mean
        """
        spread_clean = spread.dropna()
        
        if len(spread_clean) < 20:
            return np.nan
        
        # Lag spread by 1
        spread_lag = spread_clean.shift(1).dropna()
        spread_ret = spread_clean.diff().dropna()
        
        # Align
        df = pd.DataFrame({
            'ret': spread_ret,
            'lag': spread_lag
        }).dropna()
        
        if len(df) < 10:
            return np.nan
        
        try:
            # OLS: spread_ret = alpha + beta * spread_lag
            model = OLS(df['ret'], df['lag']).fit()
            lambda_coef = model.params[0]
            
            if lambda_coef >= 0:  # No mean reversion
                return np.inf
            
            half_life = -np.log(2) / np.log(1 + lambda_coef)
            return half_life
            
        except Exception as e:
            logger.error(f"Half-life calculation failed: {e}")
            return np.nan
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252 * 24 * 60  # For minute data
    ) -> float:
        """
        Calculate annualized Sharpe ratio.
        
        Sharpe = (mean_return - rf) / std_return * sqrt(periods_per_year)
        """
        if len(returns) < 2:
            return np.nan
        
        excess_returns = returns - risk_free_rate / periods_per_year
        
        if excess_returns.std() == 0:
            return np.nan
        
        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(periods_per_year)
        return sharpe


class ExecutionAnalytics:
    """
    Execution quality and market microstructure analytics.
    
    Metrics that matter to traders:
    - VWAP deviation
    - Trade imbalance
    - Effective spread
    - Liquidity metrics
    """
    
    @staticmethod
    def calculate_vwap(prices: pd.Series, volumes: pd.Series) -> float:
        """Calculate Volume-Weighted Average Price."""
        if len(prices) == 0 or volumes.sum() == 0:
            return np.nan
        
        return (prices * volumes).sum() / volumes.sum()
    
    @staticmethod
    def calculate_trade_imbalance(
        buy_volume: float,
        sell_volume: float
    ) -> float:
        """
        Trade imbalance: (buy_vol - sell_vol) / total_vol
        
        Range: [-1, 1]
        Positive = buying pressure
        Negative = selling pressure
        """
        total = buy_volume + sell_volume
        if total == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total
    
    @staticmethod
    def calculate_volatility(
        prices: pd.Series,
        window: int = 60,
        annualize: bool = False,
        periods_per_year: int = 252 * 24 * 60
    ) -> pd.Series:
        """
        Calculate rolling volatility (standard deviation of returns).
        
        If annualize=True, multiply by sqrt(periods_per_year)
        """
        returns = prices.pct_change()
        vol = returns.rolling(window=window).std()
        
        if annualize:
            vol = vol * np.sqrt(periods_per_year)
        
        return vol
    
    @staticmethod
    def calculate_realized_volatility(
        prices: pd.Series,
        window: int = 60
    ) -> float:
        """
        Realized volatility using sum of squared returns.
        
        More robust than standard deviation for high-frequency data.
        """
        returns = prices.pct_change().dropna()
        
        if len(returns) < window:
            return np.nan
        
        rv = np.sqrt(np.sum(returns[-window:] ** 2))
        return rv


class RegimeDetection:
    """
    Market regime detection for adaptive strategy parameters.
    
    Regimes: low volatility, high volatility, trending, mean-reverting
    """
    
    @staticmethod
    def detect_volatility_regime(
        prices: pd.Series,
        window: int = 60,
        threshold: float = 1.5
    ) -> str:
        """
        Classify current volatility regime.
        
        Returns: 'low', 'normal', or 'high'
        """
        returns = prices.pct_change().dropna()
        
        if len(returns) < window:
            return 'unknown'
        
        current_vol = returns[-window:].std()
        historical_vol = returns.std()
        
        ratio = current_vol / historical_vol if historical_vol > 0 else 1.0
        
        if ratio < 1 / threshold:
            return 'low'
        elif ratio > threshold:
            return 'high'
        else:
            return 'normal'
    
    @staticmethod
    def detect_trend(
        prices: pd.Series,
        window: int = 60
    ) -> Dict[str, any]:
        """
        Detect trend using linear regression slope.
        
        Returns:
            {
                'direction': 'up', 'down', or 'flat',
                'slope': regression slope,
                'r_squared': fit quality
            }
        """
        if len(prices) < window:
            return {'direction': 'unknown', 'slope': 0, 'r_squared': 0}
        
        recent = prices[-window:].reset_index(drop=True)
        x = np.arange(len(recent))
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, recent)
        
        # Normalized slope (% change per period)
        norm_slope = slope / recent.mean() if recent.mean() > 0 else 0
        
        # Classify
        if abs(norm_slope) < 0.0001:  # Essentially flat
            direction = 'flat'
        elif norm_slope > 0:
            direction = 'up'
        else:
            direction = 'down'
        
        return {
            'direction': direction,
            'slope': norm_slope,
            'r_squared': r_value ** 2
        }


if __name__ == "__main__":
    # Test analytics with sample data
    np.random.seed(42)
    
    # Generate correlated price series
    n = 1000
    x = np.cumsum(np.random.randn(n)) + 100
    y = 1.5 * x + np.random.randn(n) * 2 + 50
    
    prices_x = pd.Series(x)
    prices_y = pd.Series(y)
    
    # Test hedge ratio
    hedge_ratio, r2, pval = StatisticalAnalytics.calculate_hedge_ratio(prices_y, prices_x)
    print(f"Hedge Ratio: {hedge_ratio:.4f}, R²: {r2:.4f}, p-value: {pval:.4e}")
    
    # Test spread and z-score
    spread = StatisticalAnalytics.calculate_spread(prices_y, prices_x, hedge_ratio)
    zscore = StatisticalAnalytics.calculate_zscore(spread)
    print(f"Current Z-Score: {zscore.iloc[-1]:.4f}")
    
    # Test ADF
    adf_result = StatisticalAnalytics.adf_test(spread)
    print(f"ADF Test - Stationary: {adf_result['is_stationary']}, p-value: {adf_result['p_value']:.4f}")
    
    # Test correlation
    corr = StatisticalAnalytics.rolling_correlation(prices_x, prices_y, window=100)
    print(f"Current Correlation: {corr.iloc[-1]:.4f}")
