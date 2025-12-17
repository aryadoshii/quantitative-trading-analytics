"""
Signal Quality Score - Composite metric for trading signal confidence.

Synthesizes multiple factors into a single actionable score (0-100) that indicates
how confident traders should be in the current statistical arbitrage signal.

Components:
- Z-Score Magnitude: How far from mean (stronger signal = higher score)
- Correlation Strength: How well pairs move together (higher = better)
- Spread Stability: How consistent the spread behaves (lower volatility = better)
- Cointegration Quality: ADF test result and half-life (stationary = better)
- Historical Success: Past win rate on similar signals (track record)
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
from loguru import logger


class SignalQualityScorer:
    """
    Calculate composite signal quality score for trading decisions.
    
    Score ranges from 0-100:
    - 90-100: Exceptional signal quality - High confidence
    - 75-89: Strong signal quality - Good confidence
    - 60-74: Moderate signal quality - Cautious confidence
    - 40-59: Weak signal quality - Low confidence
    - 0-39: Poor signal quality - Avoid trading
    
    The score combines multiple factors with intelligent weighting:
    1. Z-Score Magnitude (25%): Signal strength indicator
    2. Correlation (25%): Pair relationship quality
    3. Spread Stability (20%): Predictability measure
    4. Cointegration (15%): Statistical relationship quality
    5. Historical Performance (15%): Track record
    """
    
    # Score thresholds for quality levels
    EXCEPTIONAL_THRESHOLD = 90
    STRONG_THRESHOLD = 75
    MODERATE_THRESHOLD = 60
    WEAK_THRESHOLD = 40
    
    @staticmethod
    def calculate_zscore_score(zscore: float, threshold: float = 2.0) -> float:
        """
        Score based on z-score magnitude.
        
        Logic:
        - Z-score near threshold (2.0): Maximum score
        - Z-score at 3.0: Full score (100)
        - Z-score > 3.0: Capped at 100 (avoid extreme values)
        - Z-score < threshold: Low score
        
        Args:
            zscore: Current z-score value
            threshold: Entry threshold (default: 2.0)
        
        Returns:
            Score from 0-100
        """
        abs_zscore = abs(zscore)
        
        if abs_zscore < threshold:
            # Below threshold: scale 0-50
            score = (abs_zscore / threshold) * 50
        else:
            # Above threshold: scale 50-100
            # Max out at z=3.0
            excess = abs_zscore - threshold
            score = 50 + min(excess / 1.0, 1.0) * 50
        
        return min(score, 100)
    
    @staticmethod
    def calculate_correlation_score(correlation: float, threshold: float = 0.7) -> float:
        """
        Score based on correlation strength.
        
        Logic:
        - Correlation > 0.85: Excellent (90-100)
        - Correlation 0.70-0.85: Good (70-90)
        - Correlation 0.50-0.70: Moderate (40-70)
        - Correlation < 0.50: Poor (0-40)
        
        Args:
            correlation: Pearson correlation coefficient
            threshold: Minimum acceptable correlation
        
        Returns:
            Score from 0-100
        """
        abs_corr = abs(correlation)
        
        if abs_corr >= 0.85:
            # Excellent correlation: 90-100
            score = 90 + (abs_corr - 0.85) / 0.15 * 10
        elif abs_corr >= threshold:
            # Good correlation: 70-90
            score = 70 + (abs_corr - threshold) / 0.15 * 20
        elif abs_corr >= 0.50:
            # Moderate correlation: 40-70
            score = 40 + (abs_corr - 0.50) / 0.20 * 30
        else:
            # Poor correlation: 0-40
            score = abs_corr / 0.50 * 40
        
        return min(score, 100)
    
    @staticmethod
    def calculate_stability_score(
        spread: pd.Series,
        lookback: int = 60
    ) -> float:
        """
        Score based on spread stability (inverse of volatility).
        
        Logic:
        - Lower volatility = more stable = higher score
        - Measures coefficient of variation (std / mean)
        
        Args:
            spread: Time series of spread values
            lookback: Number of periods to consider
        
        Returns:
            Score from 0-100
        """
        if len(spread) < lookback:
            return 50  # Neutral score if insufficient data
        
        recent_spread = spread.tail(lookback)
        
        # Calculate coefficient of variation
        mean_spread = abs(recent_spread.mean())
        std_spread = recent_spread.std()
        
        if mean_spread == 0:
            return 0
        
        cv = std_spread / mean_spread
        
        # Lower CV = higher stability = higher score
        # CV < 0.1: Excellent stability (90-100)
        # CV 0.1-0.3: Good stability (60-90)
        # CV > 0.3: Poor stability (0-60)
        
        if cv < 0.1:
            score = 90 + (0.1 - cv) / 0.1 * 10
        elif cv < 0.3:
            score = 60 + (0.3 - cv) / 0.2 * 30
        else:
            score = max(0, 60 - (cv - 0.3) * 100)
        
        return min(score, 100)
    
    @staticmethod
    def calculate_cointegration_score(
        adf_pvalue: Optional[float],
        half_life: Optional[float]
    ) -> float:
        """
        Score based on cointegration quality.
        
        Logic:
        - ADF p-value < 0.01: Strong cointegration (high score)
        - Half-life 5-50: Optimal mean reversion speed
        - Half-life < 5: Too fast (unstable)
        - Half-life > 50: Too slow (weak reversion)
        
        Args:
            adf_pvalue: Augmented Dickey-Fuller test p-value
            half_life: Half-life of mean reversion (in bars)
        
        Returns:
            Score from 0-100
        """
        score = 50  # Default neutral score
        
        # ADF test component (50% of cointegration score)
        if adf_pvalue is not None:
            if adf_pvalue < 0.01:
                adf_score = 100
            elif adf_pvalue < 0.05:
                adf_score = 80
            elif adf_pvalue < 0.10:
                adf_score = 60
            else:
                adf_score = max(0, 60 - (adf_pvalue - 0.10) * 200)
        else:
            adf_score = 50
        
        # Half-life component (50% of cointegration score)
        if half_life is not None and half_life > 0:
            if 5 <= half_life <= 50:
                # Optimal range
                # Best at half_life = 20
                distance_from_optimal = abs(half_life - 20)
                hl_score = 100 - (distance_from_optimal / 30) * 30
            elif half_life < 5:
                # Too fast
                hl_score = (half_life / 5) * 70
            else:
                # Too slow
                hl_score = max(0, 70 - (half_life - 50) * 2)
        else:
            hl_score = 50
        
        # Combined cointegration score
        score = (adf_score * 0.5) + (hl_score * 0.5)
        
        return min(score, 100)
    
    @staticmethod
    def calculate_historical_score(
        win_rate: Optional[float],
        profit_factor: Optional[float],
        total_trades: int = 0
    ) -> float:
        """
        Score based on historical performance.
        
        Logic:
        - Win rate > 60%: Good (80-100)
        - Win rate 50-60%: Acceptable (60-80)
        - Win rate < 50%: Poor (0-60)
        - Profit factor > 2.0: Excellent multiplier
        - Require minimum trades for confidence
        
        Args:
            win_rate: Historical win rate (0-100)
            profit_factor: Ratio of avg win to avg loss
            total_trades: Number of trades in history
        
        Returns:
            Score from 0-100
        """
        if total_trades == 0 or win_rate is None:
            return 50  # Neutral score if no history
        
        # Base score from win rate
        if win_rate >= 60:
            base_score = 80 + (win_rate - 60) / 40 * 20
        elif win_rate >= 50:
            base_score = 60 + (win_rate - 50) / 10 * 20
        else:
            base_score = win_rate / 50 * 60
        
        # Adjust for profit factor
        if profit_factor is not None:
            if profit_factor >= 2.0:
                pf_multiplier = 1.0 + min((profit_factor - 2.0) / 3.0, 0.2)
            else:
                pf_multiplier = 0.8 + (profit_factor / 2.0) * 0.2
            
            base_score *= pf_multiplier
        
        # Confidence adjustment based on sample size
        if total_trades < 5:
            confidence_factor = total_trades / 5
            base_score = 50 + (base_score - 50) * confidence_factor
        
        return min(base_score, 100)
    
    @classmethod
    def calculate_composite_score(
        cls,
        zscore: float,
        correlation: float,
        spread: pd.Series,
        adf_pvalue: Optional[float] = None,
        half_life: Optional[float] = None,
        win_rate: Optional[float] = None,
        profit_factor: Optional[float] = None,
        total_trades: int = 0,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict:
        """
        Calculate composite signal quality score.
        
        Args:
            zscore: Current z-score
            correlation: Correlation coefficient
            spread: Spread time series
            adf_pvalue: ADF test p-value
            half_life: Mean reversion half-life
            win_rate: Historical win rate
            profit_factor: Historical profit factor
            total_trades: Number of historical trades
            weights: Custom weights for components (optional)
        
        Returns:
            Dictionary with overall score and component breakdown
        """
        # Default weights
        if weights is None:
            weights = {
                'zscore': 0.25,
                'correlation': 0.25,
                'stability': 0.20,
                'cointegration': 0.15,
                'historical': 0.15
            }
        
        # Calculate component scores
        zscore_score = cls.calculate_zscore_score(zscore)
        correlation_score = cls.calculate_correlation_score(correlation)
        stability_score = cls.calculate_stability_score(spread)
        cointegration_score = cls.calculate_cointegration_score(adf_pvalue, half_life)
        historical_score = cls.calculate_historical_score(win_rate, profit_factor, total_trades)
        
        # Calculate weighted composite score
        composite_score = (
            zscore_score * weights['zscore'] +
            correlation_score * weights['correlation'] +
            stability_score * weights['stability'] +
            cointegration_score * weights['cointegration'] +
            historical_score * weights['historical']
        )
        
        # Determine quality level and recommendation
        if composite_score >= cls.EXCEPTIONAL_THRESHOLD:
            quality_level = "Exceptional"
            confidence = "Very High"
            recommendation = "Strong Trade Signal"
            emoji = "🟢"
        elif composite_score >= cls.STRONG_THRESHOLD:
            quality_level = "Strong"
            confidence = "High"
            recommendation = "Trade with Confidence"
            emoji = "🟢"
        elif composite_score >= cls.MODERATE_THRESHOLD:
            quality_level = "Moderate"
            confidence = "Medium"
            recommendation = "Consider Trading"
            emoji = "🟡"
        elif composite_score >= cls.WEAK_THRESHOLD:
            quality_level = "Weak"
            confidence = "Low"
            recommendation = "Trade with Caution"
            emoji = "🟠"
        else:
            quality_level = "Poor"
            confidence = "Very Low"
            recommendation = "Avoid Trading"
            emoji = "🔴"
        
        return {
            'composite_score': round(composite_score, 1),
            'quality_level': quality_level,
            'confidence': confidence,
            'recommendation': recommendation,
            'emoji': emoji,
            'components': {
                'zscore_score': round(zscore_score, 1),
                'correlation_score': round(correlation_score, 1),
                'stability_score': round(stability_score, 1),
                'cointegration_score': round(cointegration_score, 1),
                'historical_score': round(historical_score, 1)
            },
            'weights': weights
        }


if __name__ == "__main__":
    # Test the signal quality scorer
    import pandas as pd
    
    print("Testing Signal Quality Scorer...")
    
    # Create sample spread data
    spread = pd.Series(np.random.randn(100) * 10 + 50)
    
    # Test case 1: Strong signal
    result = SignalQualityScorer.calculate_composite_score(
        zscore=2.5,
        correlation=0.92,
        spread=spread,
        adf_pvalue=0.01,
        half_life=20,
        win_rate=70,
        profit_factor=3.5,
        total_trades=10
    )
    
    print("\nTest Case 1: Strong Signal")
    print(f"Composite Score: {result['composite_score']}/100 {result['emoji']}")
    print(f"Quality Level: {result['quality_level']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Components: {result['components']}")
    
    # Test case 2: Weak signal
    result2 = SignalQualityScorer.calculate_composite_score(
        zscore=1.2,
        correlation=0.55,
        spread=spread,
        adf_pvalue=0.15,
        half_life=None,
        win_rate=45,
        profit_factor=1.2,
        total_trades=3
    )
    
    print("\nTest Case 2: Weak Signal")
    print(f"Composite Score: {result2['composite_score']}/100 {result2['emoji']}")
    print(f"Quality Level: {result2['quality_level']}")
    print(f"Confidence: {result2['confidence']}")
    print(f"Recommendation: {result2['recommendation']}")
