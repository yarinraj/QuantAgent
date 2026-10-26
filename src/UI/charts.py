import plotly.graph_objects as go
import pandas as pd

def render_candlestick_chart(data: pd.DataFrame, symbol: str) -> go.Figure:
    """Creates an interactive Plotly candlestick chart."""
    fig = go.Figure(data=[go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name=symbol,
        increasing_line_color='#26a69a', 
        decreasing_line_color='#ef5350'
    )])
    
    fig.update_layout(
        title=f"{symbol} Price Action",
        yaxis_title="Price (USD)",
        template="plotly_dark",
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    
    return fig