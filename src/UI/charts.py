from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# Semantic trading colors are shared by the chart and the rest of the UI.
BULLISH_COLOR = "#26A69A"
BEARISH_COLOR = "#EF5350"

# Poppins is used for chart headings; Inter is reserved for numeric labels.
HEADING_FONT = "Poppins, sans-serif"
NUMERIC_FONT = "Inter, sans-serif"


def render_candlestick_chart(
    data: pd.DataFrame,
    symbol: str,
    theme: Optional[str] = None,
) -> go.Figure:
    """Build a theme-aware candlestick chart using the QuantAgent typography."""
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
        height = 400,
        template="plotly_dark" if is_dark else "plotly_white",
        title={
            "text": f"{symbol} Price Action",
            "font": {
                "family": HEADING_FONT,
                "color": font_color,
                "size": 18,
            },
            "x": 0.01,
            "xanchor": "left",
        },
        # General chart text and axis titles use the interface font.
        font={
            "family": HEADING_FONT,
            "color": font_color,
            "size": 12,
        },
        yaxis_title={
            "text": "Price (USD)",
            "font": {"family": HEADING_FONT, "color": font_color},
        },
        margin={"l": 0, "r": 0, "t": 48, "b": 0},
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        hoverlabel={
            "bgcolor": hover_bg,
            "font": {
                "family": NUMERIC_FONT,
                "color": font_color,
                "size": 12,
            },
        },
    )

    # Axis tick labels are numeric/date-oriented, so use Inter.
    fig.update_xaxes(
        rangebreaks=[
            {"bounds": ["sat", "mon"]},
            {"bounds": [16, 9.5], "pattern": "hour"},
        ],
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        linecolor=grid_color,
        tickfont={"family": NUMERIC_FONT, "color": font_color, "size": 11},
        title_font={"family": HEADING_FONT, "color": font_color},
    )

    fig.update_yaxes(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        linecolor=grid_color,
        tickfont={"family": NUMERIC_FONT, "color": font_color, "size": 11},
        title_font={"family": HEADING_FONT, "color": font_color},
    )

    return fig
