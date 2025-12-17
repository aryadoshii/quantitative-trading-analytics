"""
Streamlit dashboard for real-time trading analytics visualization.
Interactive controls, live charts, and alert display.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import asyncio
import sys
from datetime import datetime, timedelta

sys.path.append('/home/claude/quantdev-assignment/src')

from storage.timeseries_db import TimeSeriesDB
from storage.redis_cache import RedisCache
from analytics.statistical import StatisticalAnalytics, ExecutionAnalytics, RegimeDetection
from alerts.engine import AlertEngine, AlertRuleBuilder, AlertSeverity

# Page configuration
st.set_page_config(
    page_title="Quantitative Trading Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        margin-bottom: 0;
    }
    .metric-card {
        background: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .alert-critical {
        background: #ff4b4b;
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .alert-warning {
        background: #ffa500;
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_connection():
    """Get database connection (cached)."""
    return TimeSeriesDB("postgresql://trader:tradersecret@localhost:5432/trading_data")


@st.cache_resource
def get_redis_connection():
    """Get Redis connection (cached)."""
    return RedisCache("redis://localhost:6379")


def plot_price_chart(df1, df2, symbol1, symbol2):
    """Create price comparison chart."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(f'{symbol1.upper()} Price', f'{symbol2.upper()} Price'),
        row_heights=[0.5, 0.5]
    )
    
    # Symbol 1
    fig.add_trace(
        go.Scatter(x=df1.index, y=df1['close'], name=symbol1.upper(),
                  line=dict(color='#1f77b4', width=2)),
        row=1, col=1
    )
    
    # Symbol 2
    fig.add_trace(
        go.Scatter(x=df2.index, y=df2['close'], name=symbol2.upper(),
                  line=dict(color='#ff7f0e', width=2)),
        row=2, col=1
    )
    
    fig.update_layout(
        height=600,
        hovermode='x unified',
        showlegend=True,
        template='plotly_white'
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=1, col=1)
    fig.update_yaxes(title_text="Price (USD)", row=2, col=1)
    
    return fig


def plot_spread_zscore(spread, zscore):
    """Create spread and z-score chart."""
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=('Spread', 'Z-Score'),
        row_heights=[0.5, 0.5]
    )
    
    # Spread
    fig.add_trace(
        go.Scatter(x=spread.index, y=spread.values, name='Spread',
                  line=dict(color='#2ca02c', width=2)),
        row=1, col=1
    )
    
    # Z-score
    fig.add_trace(
        go.Scatter(x=zscore.index, y=zscore.values, name='Z-Score',
                  line=dict(color='#d62728', width=2)),
        row=2, col=1
    )
    
    # Add threshold lines for z-score
    fig.add_hline(y=2, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
    fig.add_hline(y=-2, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.3, row=2, col=1)
    
    fig.update_layout(
        height=600,
        hovermode='x unified',
        showlegend=True,
        template='plotly_white'
    )
    
    fig.update_xaxes(title_text="Time", row=2, col=1)
    fig.update_yaxes(title_text="Spread", row=1, col=1)
    fig.update_yaxes(title_text="Z-Score", row=2, col=1)
    
    return fig


def plot_correlation(correlation):
    """Create correlation chart."""
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(x=correlation.index, y=correlation.values,
                  name='Rolling Correlation',
                  line=dict(color='#9467bd', width=2),
                  fill='tozeroy', fillcolor='rgba(148, 103, 189, 0.2)')
    )
    
    fig.add_hline(y=0.7, line_dash="dash", line_color="orange", 
                  annotation_text="Threshold (0.7)", opacity=0.7)
    
    fig.update_layout(
        title="Rolling Correlation",
        xaxis_title="Time",
        yaxis_title="Correlation",
        height=400,
        hovermode='x',
        template='plotly_white'
    )
    
    return fig


def main():
    """Main dashboard function."""
    
    # Header
    st.markdown('<p class="main-header">📊 Quantitative Trading Analytics</p>', unsafe_allow_html=True)
    st.markdown("Real-time pairs trading analytics with statistical arbitrage signals")
    
    # Sidebar controls
    st.sidebar.header("⚙️ Configuration")
    
    # Symbol selection
    available_symbols = ['btcusdt', 'ethusdt', 'bnbusdt', 'solusdt', 'adausdt']
    symbol1 = st.sidebar.selectbox("Symbol 1", available_symbols, index=0)
    symbol2 = st.sidebar.selectbox("Symbol 2", available_symbols, index=1)
    
    # Timeframe selection
    interval = st.sidebar.selectbox(
        "Timeframe",
        ['1s', '1m', '5m'],
        index=1
    )
    
    lookback_minutes = st.sidebar.slider(
        "Lookback Period (minutes)",
        min_value=5,
        max_value=60,
        value=30,
        step=5
    )
    
    # Analytics parameters
    st.sidebar.subheader("Analytics Parameters")
    rolling_window = st.sidebar.slider("Rolling Window", 20, 200, 60, 10)
    zscore_threshold = st.sidebar.slider("Z-Score Threshold", 1.0, 3.0, 2.0, 0.1)
    
    # Alert configuration
    st.sidebar.subheader("🔔 Alerts")
    enable_alerts = st.sidebar.checkbox("Enable Alerts", value=True)
    
    if enable_alerts:
        alert_zscore = st.sidebar.number_input("Z-Score Alert", value=2.0, step=0.1)
        alert_corr = st.sidebar.number_input("Correlation Alert", value=0.7, step=0.05)
    
    # Risk Dashboard
    st.sidebar.subheader("⚠️ Risk Dashboard")
    
    # Fetch risk metrics
    loop_risk = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_risk)
    cache_risk = get_redis_connection()
    loop_risk.run_until_complete(cache_risk.connect())
    
    pair_risk = f"{symbol1}-{symbol2}"
    risk_data = loop_risk.run_until_complete(cache_risk.get_cached_analytics(pair_risk, 'risk_metrics'))
    
    loop_risk.run_until_complete(cache_risk.disconnect())
    
    if risk_data:
        rm = risk_data['value']
        health = rm.get('health', {})
        
        # Portfolio Health Score
        st.sidebar.markdown(f"**Portfolio Health**")
        st.sidebar.markdown(f"### {health.get('health_emoji', '🟡')} {health.get('health_score', 50):.0f}/100")
        st.sidebar.caption(health.get('health_level', 'Unknown'))
        
        # Key risk metrics
        if rm.get('var_95'):
            st.sidebar.metric("VaR (95%)", f"${rm['var_95']:.2f}", help="Maximum expected loss (95% confidence)")
        
        if rm.get('current_drawdown_pct') is not None:
            st.sidebar.metric("Current Drawdown", f"{rm['current_drawdown_pct']:.1f}%")
        
        if rm.get('exposure_pct') is not None:
            st.sidebar.metric("Position Exposure", f"{rm['exposure_pct']:.0f}%")
    else:
        st.sidebar.info("Risk metrics available after trades complete")
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()
    
    # Main content
    try:
        # Get data
        db = get_db_connection()
        
        # Run async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Connect to DB
        loop.run_until_complete(db.connect())
        
        # Fetch OHLCV data
        df1 = loop.run_until_complete(db.get_ohlcv(symbol1, interval, lookback_minutes))
        df2 = loop.run_until_complete(db.get_ohlcv(symbol2, interval, lookback_minutes))
        
        if df1.empty or df2.empty:
            st.warning(f"⚠️ No data available yet. Waiting for data ingestion...")
            st.info(f"💡 Make sure the main application is running: `python src/main.py`")
            st.stop()
        
        # Align dataframes
        df_combined = pd.DataFrame({
            'price1': df1['close'],
            'price2': df2['close']
        }).dropna()
        
        if len(df_combined) < 20:
            st.warning("⏳ Not enough data for analytics (need at least 20 data points)")
            st.stop()
        
        # Compute analytics
        prices1 = df_combined['price1']
        prices2 = df_combined['price2']
        
        hedge_ratio, r2, pval = StatisticalAnalytics.calculate_hedge_ratio(prices1, prices2)
        spread = StatisticalAnalytics.calculate_spread(prices1, prices2, hedge_ratio)
        zscore = StatisticalAnalytics.calculate_zscore(spread, window=rolling_window)
        correlation = StatisticalAnalytics.rolling_correlation(prices1, prices2, window=rolling_window)
        
        # ADF test
        adf_result = StatisticalAnalytics.adf_test(spread)
        
        # Regime detection
        regime = RegimeDetection.detect_volatility_regime(spread, window=rolling_window)
        trend = RegimeDetection.detect_trend(spread, window=rolling_window)
        
        # Close DB connection
        loop.run_until_complete(db.disconnect())
        
        # Top metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Hedge Ratio",
                f"{hedge_ratio:.4f}",
                delta=f"R² = {r2:.3f}",
                help="OLS regression coefficient"
            )
        
        with col2:
            current_zscore = zscore.iloc[-1] if not zscore.empty else 0
            zscore_color = "🔴" if abs(current_zscore) > zscore_threshold else "🟢"
            st.metric(
                "Current Z-Score",
                f"{zscore_color} {current_zscore:.2f}",
                delta=f"Threshold: ±{zscore_threshold}",
                help="Current spread z-score"
            )
        
        with col3:
            current_corr = correlation.iloc[-1] if not correlation.empty else 0
            st.metric(
                "Correlation",
                f"{current_corr:.3f}",
                delta="60-period rolling",
                help="Rolling correlation between symbols"
            )
        
        with col4:
            stationary_icon = "✅" if adf_result['is_stationary'] else "❌"
            st.metric(
                "ADF Test",
                f"{stationary_icon} {'Stationary' if adf_result['is_stationary'] else 'Non-stationary'}",
                delta=f"p-value: {adf_result['p_value']:.4f}",
                help="Augmented Dickey-Fuller test for cointegration"
            )
        
        # Signal Quality Score - Prominent Display
        st.markdown("---")
        
        # Fetch signal quality from Redis
        cache = get_redis_connection()
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)
        loop2.run_until_complete(cache.connect())
        
        pair = f"{symbol1}-{symbol2}"
        signal_quality_data = loop2.run_until_complete(cache.get_cached_analytics(pair, 'signal_quality'))
        
        loop2.run_until_complete(cache.disconnect())
        
        if signal_quality_data:
            sq = signal_quality_data['value']
            
            # Large prominent display with better styling
            st.markdown("---")
            
            # Main score display - centered and prominent
            col_main1, col_main2, col_main3 = st.columns([1, 2, 1])
            
            with col_main2:
                # Determine color based on score
                if sq['composite_score'] >= 75:
                    score_color = "#22c55e"  # Green
                elif sq['composite_score'] >= 60:
                    score_color = "#eab308"  # Yellow
                elif sq['composite_score'] >= 40:
                    score_color = "#f97316"  # Orange
                else:
                    score_color = "#ef4444"  # Red
                
                st.markdown(f"""
                <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; margin-bottom: 20px;">
                    <h2 style="color: white; margin: 0; font-size: 1.2rem;">{sq['emoji']} Signal Quality Score</h2>
                    <h1 style="color: white; margin: 10px 0; font-size: 3.5rem; font-weight: bold;">{sq['composite_score']:.1f}<span style="font-size: 2rem; opacity: 0.8;">/100</span></h1>
                    <p style="color: white; margin: 5px 0; font-size: 1.3rem; font-weight: 600;">{sq['quality_level']} | {sq['confidence']} Confidence</p>
                    <p style="color: white; margin: 0; font-size: 1rem; font-style: italic; opacity: 0.9;">{sq['recommendation']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Component breakdown - cleaner layout
            st.markdown("### 📊 Score Breakdown")
            
            # Create 5 columns for component scores
            comp_cols = st.columns(5)
            
            components = [
                ("Z-Score\nStrength", sq['components']['zscore_score'], "25%", "💪"),
                ("Correlation\nQuality", sq['components']['correlation_score'], "25%", "🔗"),
                ("Spread\nStability", sq['components']['stability_score'], "20%", "📊"),
                ("Cointegration\nTest", sq['components']['cointegration_score'], "15%", "🧪"),
                ("Historical\nPerformance", sq['components']['historical_score'], "15%", "📈")
            ]
            
            for idx, (name, score, weight, emoji) in enumerate(components):
                with comp_cols[idx]:
                    # Determine color for this component
                    if score >= 75:
                        comp_color = "#22c55e"
                        comp_bg = "#dcfce7"
                    elif score >= 60:
                        comp_color = "#eab308"
                        comp_bg = "#fef9c3"
                    elif score >= 40:
                        comp_color = "#f97316"
                        comp_bg = "#ffedd5"
                    else:
                        comp_color = "#ef4444"
                        comp_bg = "#fee2e2"
                    
                    st.markdown(f"""
                    <div style="text-align: center; padding: 15px; background: {comp_bg}; border-radius: 10px; border: 2px solid {comp_color};">
                        <div style="font-size: 2rem; margin-bottom: 5px;">{emoji}</div>
                        <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 8px; line-height: 1.2;">{name}</div>
                        <div style="font-size: 2rem; font-weight: bold; color: {comp_color}; margin-bottom: 5px;">{score:.0f}</div>
                        <div style="font-size: 0.75rem; color: {comp_color}; font-weight: 600;">{weight} weight</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Improved horizontal bar chart
            st.markdown("#### 📊 Visual Component Analysis")
            
            import plotly.graph_objects as go
            
            # Sort components by score for better visualization
            component_names = ['Z-Score\nStrength', 'Correlation\nQuality', 'Spread\nStability', 
                             'Cointegration\nQuality', 'Historical\nPerformance']
            component_values = list(sq['components'].values())
            
            # Create color array based on scores
            colors = []
            for val in component_values:
                if val >= 75:
                    colors.append('#22c55e')  # Green
                elif val >= 60:
                    colors.append('#eab308')  # Yellow
                elif val >= 40:
                    colors.append('#f97316')  # Orange
                else:
                    colors.append('#ef4444')  # Red
            
            fig = go.Figure()
            
            # Add bars
            fig.add_trace(go.Bar(
                y=component_names,
                x=component_values,
                orientation='h',
                marker=dict(
                    color=colors,
                    line=dict(color='rgba(0,0,0,0.3)', width=1)
                ),
                text=[f"<b>{v:.0f}</b>" for v in component_values],
                textposition='inside',
                textfont=dict(size=16, color='white', family='Arial Black'),
                hovertemplate='<b>%{y}</b><br>Score: %{x:.0f}/100<extra></extra>'
            ))
            
            # Add reference lines
            fig.add_vline(x=75, line_dash="dash", line_color="green", opacity=0.3, 
                         annotation_text="Strong", annotation_position="top")
            fig.add_vline(x=60, line_dash="dash", line_color="yellow", opacity=0.3,
                         annotation_text="Moderate", annotation_position="top")
            fig.add_vline(x=40, line_dash="dash", line_color="orange", opacity=0.3,
                         annotation_text="Weak", annotation_position="top")
            
            fig.update_layout(
                title=dict(
                    text="Component Scores (0-100 scale)",
                    font=dict(size=16, color='#1e293b')
                ),
                xaxis=dict(
                    title="Score",
                    range=[0, 100],
                    dtick=20,
                    gridcolor='rgba(0,0,0,0.1)',
                    showgrid=True
                ),
                yaxis=dict(
                    title="",
                    categoryorder='total ascending'
                ),
                height=350,
                margin=dict(l=150, r=50, t=80, b=50),
                plot_bgcolor='rgba(0,0,0,0.02)',
                paper_bgcolor='white',
                showlegend=False,
                font=dict(size=13, color='#1e293b')
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Interpretation guide
            with st.expander("📖 How to Interpret the Signal Quality Score"):
                st.markdown("""
                **Score Ranges:**
                - 🟢 **90-100**: Exceptional - Very High Confidence - Strong Trade Signal
                - 🟢 **75-89**: Strong - High Confidence - Trade with Confidence
                - 🟡 **60-74**: Moderate - Medium Confidence - Consider Trading
                - 🟠 **40-59**: Weak - Low Confidence - Trade with Caution
                - 🔴 **0-39**: Poor - Very Low Confidence - Avoid Trading
                
                **Component Weights:**
                - **Z-Score Strength (25%)**: How far the spread is from its mean. Higher = stronger signal.
                - **Correlation Quality (25%)**: How well the pairs move together. Higher = more reliable.
                - **Spread Stability (20%)**: How predictable the spread behavior is. Higher = lower risk.
                - **Cointegration Quality (15%)**: Statistical test for mean reversion. Higher = better pair relationship.
                - **Historical Performance (15%)**: Track record of similar signals. Higher = proven strategy.
                
                **The score updates automatically every 5 seconds** based on real-time market data and analytics.
                """)
        
        st.markdown("---")
        
        # Alert banner
        if enable_alerts and abs(current_zscore) > alert_zscore:
            st.markdown(
                f'<div class="alert-critical">🚨 <strong>CRITICAL ALERT:</strong> '
                f'Z-Score = {current_zscore:.2f} exceeds threshold {alert_zscore:.2f}!</div>',
                unsafe_allow_html=True
            )
        
        # Tabs for different visualizations
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Prices", "📊 Spread & Z-Score", "🔗 Correlation", "💰 Trading Simulator", "📋 Summary"])
        
        with tab1:
            st.subheader(f"Price Comparison: {symbol1.upper()} vs {symbol2.upper()}")
            fig_prices = plot_price_chart(df1, df2, symbol1, symbol2)
            st.plotly_chart(fig_prices, use_container_width=True)
            
            # Volume subplot
            col1, col2 = st.columns(2)
            with col1:
                st.line_chart(df1['volume'], height=200)
                st.caption(f"{symbol1.upper()} Volume")
            with col2:
                st.line_chart(df2['volume'], height=200)
                st.caption(f"{symbol2.upper()} Volume")
        
        with tab2:
            st.subheader("Spread Analysis & Z-Score")
            fig_spread = plot_spread_zscore(spread, zscore)
            st.plotly_chart(fig_spread, use_container_width=True)
            
            # Trading signals
            st.markdown("### Trading Signals")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if current_zscore > zscore_threshold:
                    st.success(f"🎯 **SELL SPREAD** (z = {current_zscore:.2f})")
                    st.caption("Spread is overextended, expect mean reversion")
                elif current_zscore < -zscore_threshold:
                    st.success(f"🎯 **BUY SPREAD** (z = {current_zscore:.2f})")
                    st.caption("Spread is underextended, expect mean reversion")
                else:
                    st.info("⏸️ **NO SIGNAL** - Within normal range")
            
            with col2:
                st.metric("Volatility Regime", regime.upper())
                st.caption(f"Trend: {trend['direction'].upper()}")
            
            with col3:
                half_life = StatisticalAnalytics.calculate_half_life(spread)
                if pd.notna(half_life) and half_life < 100:
                    st.metric("Mean Reversion Half-Life", f"{half_life:.1f} periods")
                else:
                    st.metric("Mean Reversion Half-Life", "N/A")
        
        with tab3:
            st.subheader("Rolling Correlation Analysis")
            fig_corr = plot_correlation(correlation)
            st.plotly_chart(fig_corr, use_container_width=True)
            
            if current_corr < 0.7:
                st.warning(f"⚠️ Correlation dropped to {current_corr:.3f} - pairs relationship weakening")
        
        with tab4:
            st.subheader("💰 Live Trading Simulator")
            st.caption("Hypothetical position tracking based on z-score signals")
            
            # Fetch PnL data from Redis
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            cache = get_redis_connection()
            loop.run_until_complete(cache.connect())
            
            pair = f"{symbol1}-{symbol2}"
            unrealized_data = loop.run_until_complete(cache.get_cached_analytics(pair, 'unrealized_pnl'))
            performance_data = loop.run_until_complete(cache.get_cached_analytics(pair, 'performance'))
            
            loop.run_until_complete(cache.disconnect())
            
            if unrealized_data and performance_data:
                unrealized = unrealized_data['value']
                performance = performance_data['value']
                
                # Current Position Status
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if unrealized.get('has_position', False):
                        st.metric(
                            "Position Status",
                            f"🟢 {unrealized['direction'].upper()}",
                            f"Entry z={unrealized['entry_zscore']:.2f}"
                        )
                    else:
                        st.metric("Position Status", "⚪ FLAT", "No position")
                
                with col2:
                    if unrealized.get('has_position', False):
                        pnl_color = "🟢" if unrealized.get('pnl', 0) > 0 else "🔴"
                        st.metric(
                            "Unrealized PnL",
                            f"{pnl_color} ${unrealized.get('pnl', 0):.2f}",
                            f"{unrealized.get('pnl_percent', 0):+.2f}%"
                        )
                    else:
                        st.metric("Unrealized PnL", "$0.00", "No position")
                
                with col3:
                    total_pnl = performance.get('total_pnl', 0)
                    total_pnl_color = "🟢" if total_pnl > 0 else "🔴"
                    total_return = performance.get('total_return', 0)
                    st.metric(
                        "Total PnL",
                        f"{total_pnl_color} ${total_pnl:.2f}",
                        f"{total_return:+.2f}%"
                    )
                
                # Performance Metrics
                st.markdown("### 📊 Performance Metrics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Trades", performance.get('total_trades', 0))
                    st.metric("Win Rate", f"{performance.get('win_rate', 0):.1f}%")
                
                with col2:
                    st.metric("Avg Win", f"${performance.get('avg_win', 0):.2f}")
                    st.metric("Avg Loss", f"${performance.get('avg_loss', 0):.2f}")
                
                with col3:
                    st.metric("Profit Factor", f"{performance.get('profit_factor', 0):.2f}")
                    st.metric("Sharpe Ratio", f"{performance.get('sharpe_ratio', 0):.2f}")
                
                with col4:
                    st.metric("Max Drawdown", f"{performance.get('max_drawdown', 0):.2f}%")
                    st.metric("Current Capital", f"${performance.get('current_capital', 10000):.2f}")
                
                # Strategy Settings
                st.markdown("### ⚙️ Strategy Settings")
                st.info("""
                **Entry:** |Z-Score| > 2.0  
                **Exit:** Z-Score crosses 0.2 OR Stop Loss (-5%) OR Take Profit (+10%)  
                **Position Size:** 10% of capital  
                **Direction:** Short spread when z > 0, Long spread when z < 0
                """)
                
                # Current Position Details
                if unrealized.get('has_position', False):
                    st.markdown("### 📍 Current Position Details")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        entry_time = unrealized.get('entry_time')
                        st.write(f"**Entry Time:** {entry_time}")
                        st.write(f"**Position Size:** ${unrealized.get('size', 0):.2f}")
                        st.write(f"**Entry Z-Score:** {unrealized.get('entry_zscore', 0):.2f}")
                    
                    with col2:
                        st.write(f"**Max Favorable:** ${unrealized.get('max_favorable', 0):.2f}")
                        st.write(f"**Max Adverse:** ${unrealized.get('max_adverse', 0):.2f}")
                        
                        # Calculate hold duration
                        if entry_time:
                            from datetime import datetime as dt
                            hold_duration = (dt.now() - entry_time).total_seconds() / 60
                            st.write(f"**Hold Duration:** {hold_duration:.1f} minutes")
                
                # Visual PnL Chart (if there are closed trades)
                if performance.get('total_trades', 0) > 0:
                    st.markdown("### 📈 Cumulative PnL")
                    
                    cumulative_pnl = performance.get('total_pnl', 0)
                    
                    # Create a simple metric display
                    pnl_chart_data = pd.DataFrame({
                        'PnL': [0, cumulative_pnl]
                    })
                    st.line_chart(pnl_chart_data)
                
            else:
                st.info("⏳ Waiting for trading signals to generate positions...")
                st.caption("The simulator will start tracking positions once z-score signals trigger.")
                
                # Show what will happen
                st.markdown("### 🎯 How It Works")
                st.write("""
                The trading simulator automatically:
                1. **Enters** positions when |z-score| > 2.0
                2. **Tracks** unrealized PnL in real-time
                3. **Exits** when z-score crosses 0.2 or hits stop/profit targets
                4. **Records** all trades with performance metrics
                
                **Current Status:** Monitoring for entry signals...
                """)
        
        with tab5:
            st.subheader("Analytics Summary")
            
            # Summary table
            summary_data = {
                "Metric": [
                    "Hedge Ratio (β)",
                    "R-Squared",
                    "P-Value",
                    "Current Z-Score",
                    "Max Z-Score",
                    "Min Z-Score",
                    "Correlation",
                    "ADF Statistic",
                    "ADF P-Value",
                    "Stationary",
                    "Volatility Regime",
                    "Trend Direction",
                    "Data Points",
                    "Timeframe"
                ],
                "Value": [
                    f"{hedge_ratio:.4f}",
                    f"{r2:.4f}",
                    f"{pval:.4e}" if pd.notna(pval) else "N/A",
                    f"{current_zscore:.4f}",
                    f"{zscore.max():.4f}",
                    f"{zscore.min():.4f}",
                    f"{current_corr:.4f}",
                    f"{adf_result['statistic']:.4f}",
                    f"{adf_result['p_value']:.4f}",
                    "✅ Yes" if adf_result['is_stationary'] else "❌ No",
                    regime.upper(),
                    trend['direction'].upper(),
                    len(df_combined),
                    f"{interval} bars"
                ]
            }
            
            st.dataframe(
                pd.DataFrame(summary_data),
                hide_index=True,
                use_container_width=True
            )
            
            # Download button
            csv = df_combined.to_csv()
            st.download_button(
                label="📥 Download Price Data (CSV)",
                data=csv,
                file_name=f"{symbol1}_{symbol2}_{interval}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)
    
    # Footer
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
               f"Gemscap Quantitative Developer Assignment")


if __name__ == "__main__":
    main()
