"""
Alert engine for rule-based notifications on trading opportunities.
Supports custom rules, rate limiting, and alert history.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from loguru import logger


class AlertType(Enum):
    """Types of alerts supported."""
    ZSCORE_THRESHOLD = "zscore_threshold"
    SPREAD_BREAKOUT = "spread_breakout"
    VOLATILITY_SPIKE = "volatility_spike"
    CORRELATION_BREAK = "correlation_break"
    CUSTOM = "custom"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """
    Definition of an alert rule.
    
    Attributes:
        rule_id: Unique identifier
        alert_type: Type of alert
        symbol: Trading symbol or symbol pair
        condition: Callable that returns True when alert should trigger
        threshold: Numeric threshold for condition
        severity: Alert severity level
        cooldown_seconds: Minimum time between repeat alerts
        message_template: Alert message with placeholders
    """
    rule_id: str
    alert_type: AlertType
    symbol: str
    condition: Callable
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    cooldown_seconds: int = 60
    message_template: str = "Alert triggered for {symbol}"
    enabled: bool = True


@dataclass
class Alert:
    """Triggered alert instance."""
    rule_id: str
    alert_type: AlertType
    symbol: str
    severity: AlertSeverity
    message: str
    value: float
    threshold: float
    timestamp: datetime


class AlertEngine:
    """
    Alert engine that monitors analytics and triggers notifications.
    
    Features:
    - Multiple rule types
    - Cooldown to prevent spam
    - Alert history
    - Async callbacks for real-time notifications
    """
    
    def __init__(self, check_interval: float = 0.5):
        self.check_interval = check_interval
        self.rules: Dict[str, AlertRule] = {}
        self.alert_history: List[Alert] = []
        self.last_trigger_times: Dict[str, datetime] = {}
        self.callbacks: List[Callable] = []
        self.running = False
        
    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules[rule.rule_id] = rule
        logger.info(f"Added alert rule: {rule.rule_id} for {rule.symbol}")
        
    def remove_rule(self, rule_id: str):
        """Remove an alert rule."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"Removed alert rule: {rule_id}")
    
    def enable_rule(self, rule_id: str):
        """Enable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            
    def disable_rule(self, rule_id: str):
        """Disable a rule."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
    
    def register_callback(self, callback: Callable):
        """
        Register a callback function to be called when alert triggers.
        
        Callback signature: async def callback(alert: Alert)
        """
        self.callbacks.append(callback)
        
    async def check_rule(
        self,
        rule: AlertRule,
        current_value: float,
        analytics_data: Dict = None
    ) -> Optional[Alert]:
        """
        Check if a rule should trigger.
        
        Returns Alert if triggered, None otherwise.
        """
        if not rule.enabled:
            return None
        
        # Check cooldown
        last_trigger = self.last_trigger_times.get(rule.rule_id)
        if last_trigger:
            elapsed = (datetime.now() - last_trigger).total_seconds()
            if elapsed < rule.cooldown_seconds:
                return None
        
        # Evaluate condition
        try:
            should_trigger = rule.condition(current_value, rule.threshold, analytics_data)
        except Exception as e:
            logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
            return None
        
        if not should_trigger:
            return None
        
        # Create alert
        message = rule.message_template.format(
            symbol=rule.symbol,
            value=current_value,
            threshold=rule.threshold
        )
        
        alert = Alert(
            rule_id=rule.rule_id,
            alert_type=rule.alert_type,
            symbol=rule.symbol,
            severity=rule.severity,
            message=message,
            value=current_value,
            threshold=rule.threshold,
            timestamp=datetime.now()
        )
        
        # Update last trigger time
        self.last_trigger_times[rule.rule_id] = datetime.now()
        
        # Store in history
        self.alert_history.append(alert)
        
        # Trigger callbacks
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
        
        logger.warning(f"🚨 ALERT: {alert.message}")
        
        return alert
    
    def get_recent_alerts(self, minutes: int = 60) -> List[Alert]:
        """Get alerts from the last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [a for a in self.alert_history if a.timestamp > cutoff]
    
    def get_alerts_by_symbol(self, symbol: str) -> List[Alert]:
        """Get all alerts for a specific symbol."""
        return [a for a in self.alert_history if a.symbol == symbol]
    
    def clear_history(self):
        """Clear alert history."""
        self.alert_history = []
        logger.info("Alert history cleared")


# Predefined condition functions
class AlertConditions:
    """Common alert condition functions."""
    
    @staticmethod
    def zscore_above(value: float, threshold: float, data: Dict = None) -> bool:
        """Trigger when z-score exceeds threshold."""
        return abs(value) > threshold
    
    @staticmethod
    def zscore_entry(value: float, threshold: float, data: Dict = None) -> bool:
        """Trigger on mean-reversion entry signal (|z| > threshold)."""
        return abs(value) > threshold
    
    @staticmethod
    def zscore_exit(value: float, threshold: float, data: Dict = None) -> bool:
        """Trigger on mean-reversion exit signal (|z| < threshold)."""
        return abs(value) < threshold
    
    @staticmethod
    def correlation_break(value: float, threshold: float, data: Dict = None) -> bool:
        """Trigger when correlation drops below threshold."""
        return value < threshold
    
    @staticmethod
    def volatility_spike(value: float, threshold: float, data: Dict = None) -> bool:
        """Trigger when volatility exceeds threshold times historical."""
        if not data or 'historical_vol' not in data:
            return False
        
        ratio = value / data['historical_vol']
        return ratio > threshold
    
    @staticmethod
    def spread_percentile(value: float, threshold: float, data: Dict = None) -> bool:
        """Trigger when spread is in extreme percentile."""
        if not data or 'spread_series' not in data:
            return False
        
        percentile = pd.Series(data['spread_series']).rank(pct=True).iloc[-1] * 100
        return percentile > threshold or percentile < (100 - threshold)


# Predefined alert rule builders
class AlertRuleBuilder:
    """Helper to build common alert rules."""
    
    @staticmethod
    def zscore_threshold_alert(
        symbol: str,
        threshold: float = 2.0,
        severity: AlertSeverity = AlertSeverity.WARNING
    ) -> AlertRule:
        """Create a z-score threshold alert."""
        return AlertRule(
            rule_id=f"zscore_{symbol}_{threshold}",
            alert_type=AlertType.ZSCORE_THRESHOLD,
            symbol=symbol,
            condition=AlertConditions.zscore_above,
            threshold=threshold,
            severity=severity,
            cooldown_seconds=60,
            message_template=f"Z-score for {{symbol}} = {{value:.2f}} (threshold: {{threshold}})"
        )
    
    @staticmethod
    def mean_reversion_entry_alert(
        symbol: str,
        entry_threshold: float = 2.0
    ) -> AlertRule:
        """Create mean-reversion entry signal alert."""
        return AlertRule(
            rule_id=f"mr_entry_{symbol}",
            alert_type=AlertType.ZSCORE_THRESHOLD,
            symbol=symbol,
            condition=AlertConditions.zscore_entry,
            threshold=entry_threshold,
            severity=AlertSeverity.CRITICAL,
            cooldown_seconds=120,
            message_template=f"🎯 ENTRY SIGNAL: {{symbol}} z-score = {{value:.2f}} (target: {{threshold}})"
        )
    
    @staticmethod
    def correlation_break_alert(
        symbol: str,
        threshold: float = 0.7
    ) -> AlertRule:
        """Create correlation breakdown alert."""
        return AlertRule(
            rule_id=f"corr_break_{symbol}",
            alert_type=AlertType.CORRELATION_BREAK,
            symbol=symbol,
            condition=AlertConditions.correlation_break,
            threshold=threshold,
            severity=AlertSeverity.WARNING,
            cooldown_seconds=300,
            message_template=f"⚠️ Correlation dropped: {{symbol}} = {{value:.2f}} (threshold: {{threshold}})"
        )


if __name__ == "__main__":
    # Test alert engine
    async def test_callback(alert: Alert):
        print(f"Alert triggered: {alert.message}")
    
    async def test():
        engine = AlertEngine(check_interval=0.1)
        
        # Add z-score alert
        rule = AlertRuleBuilder.zscore_threshold_alert("btcusdt-ethusdt", threshold=2.0)
        engine.add_rule(rule)
        engine.register_callback(test_callback)
        
        # Simulate z-score values
        for zscore in [1.5, 2.1, 2.5, 1.0, 2.8]:
            alert = await engine.check_rule(rule, zscore)
            if alert:
                print(f"✓ Alert fired: z={zscore}")
            else:
                print(f"✗ No alert: z={zscore}")
            await asyncio.sleep(0.5)
        
        # Check history
        recent = engine.get_recent_alerts(minutes=5)
        print(f"\nRecent alerts: {len(recent)}")
    
    asyncio.run(test())
