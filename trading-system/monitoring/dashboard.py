"""
Streamlit dashboard for real-time monitoring.

Displays:
- Portfolio overview (equity curve, P&L, positions)
- Active signals and trade history
- Strategy performance by hypothesis
- Risk status and alerts
- Sentiment heatmap

Run with: streamlit run monitoring/dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path when run via streamlit
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import settings
from data.storage.timescale import TimescaleDB


def main() -> None:
    st.set_page_config(page_title="Trading System Dashboard", layout="wide")
    st.title("Anti-Overfit Trading System")

    # Database connection
    db = TimescaleDB()
    try:
        db.connect()
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        st.info("Make sure TimescaleDB is running: `docker-compose up -d`")
        return

    # Sidebar
    st.sidebar.header("Controls")
    lookback_days = st.sidebar.slider("Lookback (days)", 1, 90, 30)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Portfolio", "Trades", "Strategies", "Risk"])

    with tab1:
        _portfolio_tab(db, lookback_days)

    with tab2:
        _trades_tab(db, lookback_days)

    with tab3:
        _strategies_tab(db)

    with tab4:
        _risk_tab(db)

    db.close()


def _portfolio_tab(db: TimescaleDB, lookback_days: int) -> None:
    st.header("Portfolio Overview")

    col1, col2, col3 = st.columns(3)

    # Get recent trades for P&L
    from datetime import datetime, timedelta, timezone
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    trades = db.get_trades(start=start, end=end)

    if not trades.empty:
        closed = trades[trades["status"].isin(["closed", "stopped"])]
        total_pnl = closed["pnl"].sum() if not closed.empty else 0
        win_rate = (closed["pnl"] > 0).mean() if not closed.empty and len(closed) > 0 else 0

        col1.metric("Total P&L", f"${total_pnl:.2f}")
        col2.metric("Win Rate", f"{win_rate:.0%}")
        col3.metric("Total Trades", len(trades))

        # Equity curve
        if not closed.empty and "exit_time" in closed.columns:
            closed_sorted = closed.sort_values("exit_time")
            closed_sorted["cumulative_pnl"] = closed_sorted["pnl"].cumsum()
            fig = px.line(closed_sorted, x="exit_time", y="cumulative_pnl", title="Cumulative P&L")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No trades yet.")


def _trades_tab(db: TimescaleDB, lookback_days: int) -> None:
    st.header("Trade Log")

    from datetime import datetime, timedelta, timezone
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    trades = db.get_trades(start=start, end=end)

    if not trades.empty:
        display_cols = ["time", "ticker", "strategy", "direction", "entry_price", "exit_price", "pnl", "status", "explanation"]
        available_cols = [c for c in display_cols if c in trades.columns]
        st.dataframe(trades[available_cols].sort_values("time", ascending=False), use_container_width=True)
    else:
        st.info("No trades in the selected period.")


def _strategies_tab(db: TimescaleDB) -> None:
    st.header("Hypothesis Performance")

    hypotheses = db.get_all_hypotheses()
    if not hypotheses.empty:
        st.dataframe(
            hypotheses[["id", "name", "status", "cpcv_sharpe_mean", "cpcv_sharpe_std", "pbo", "deflated_sharpe"]],
            use_container_width=True,
        )

        # Visual: Sharpe ratio distribution
        active = hypotheses[hypotheses["status"] == "active"]
        if not active.empty and "cpcv_sharpe_mean" in active.columns:
            fig = px.bar(active, x="name", y="cpcv_sharpe_mean", error_y="cpcv_sharpe_std", title="Strategy Sharpe Ratios (CPCV)")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hypotheses registered yet.")


def _risk_tab(db: TimescaleDB) -> None:
    st.header("Risk Status")

    st.subheader("Risk Parameters")
    st.json({
        "max_daily_loss": f"{settings.risk.max_daily_loss_pct}%",
        "max_weekly_loss": f"{settings.risk.max_weekly_loss_pct}%",
        "max_drawdown": f"{settings.risk.max_drawdown_pct}%",
        "max_position": f"{settings.risk.max_position_pct}%",
        "max_open_positions": settings.risk.max_open_positions,
        "leverage": f"{settings.risk.max_leverage}x",
    })

    # Open positions
    st.subheader("Open Positions")
    open_trades = db.get_open_trades()
    if open_trades:
        st.dataframe(pd.DataFrame(open_trades), use_container_width=True)
    else:
        st.info("No open positions.")


if __name__ == "__main__":
    main()
