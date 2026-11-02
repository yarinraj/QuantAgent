from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# Semantic trading colors are shared by the chart and the rest of the UI.
BULLISH_COLOR = "#26A69A"
BEARISH_COLOR = "#EF5350"


def render_candlestick_chart(
    data: pd.DataFrame,
    symbol: str,
    theme: Optional[str] = None,
) -> go.Figure:
    """Build a theme-aware candlestick chart.

    If `theme` is omitted, the function reads the current theme from
    Streamlit session state. This keeps the existing app.py call compatible:
        render_candlestick_chart(historical_data, symbol)
    """
    if theme is None:
        theme = st.session_state.get("theme", "dark")

    is_dark = theme == "dark"

    font_color = "#F3F4F6" if is_dark else "#0F172A"
    grid_color = (
        "rgba(255, 255, 255, 0.12)"
        if is_dark
        else "rgba(15, 23, 42, 0.12)"
    )
    hover_bg = "#161B26" if is_dark else "#FFFFFF"

    candlestick = go.Candlestick(
        x=data.index,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        name=symbol,
        increasing_line_color=BULLISH_COLOR,
        increasing_fillcolor=BULLISH_COLOR,
        decreasing_line_color=BEARISH_COLOR,
        decreasing_fillcolor=BEARISH_COLOR,
    )

    fig = go.Figure(data=[candlestick])

    fig.update_layout(
        template="plotly_dark" if is_dark else "plotly_white",
        title={
            "text": f"{symbol} Price Action",
            "font": {"color": font_color},
            "x": 0.01,
            "xanchor": "left",
        },
        font={"color": font_color},
        yaxis_title="Price (USD)",
        margin={"l": 0, "r": 0, "t": 48, "b": 0},
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        hoverlabel={
            "bgcolor": hover_bg,
            "font": {"color": font_color},
        },
    )

    fig.update_xaxes(
        rangebreaks=[
            {"bounds": ["sat", "mon"]},
            {"bounds": [16, 9.5], "pattern": "hour"},
        ],
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        linecolor=grid_color,
        tickfont={"color": font_color},
        title_font={"color": font_color},
    )

    fig.update_yaxes(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        linecolor=grid_color,
        tickfont={"color": font_color},
        title_font={"color": font_color},
    )

    return fig
