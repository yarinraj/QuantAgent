import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.data.market_data import MarketDataEngine
from src.risk.risk_engine import RiskEngine
from src.agent.core import AIAgentCore

# Page Configuration
st.set_page_config(
    page_title="QuantAgent | Risk & Portfolio Manager",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Professional Fintech Look
st.markdown("""
    <style>
    /* Dark Theme Custom Styling */
    .main { background-color: #0F172A; }
    h1, h2, h3 { color: #F8FAFC !important; font-family: 'Inter', sans-serif; }
    
    /* Metric Cards Styling */
    div[data-testid="stMetric"] {
        background-color: #1E293B;
        border: 1px solid #334155;
        padding: 12px 16px;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    div[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-size: 0.85rem; }
    div[data-testid="stMetricValue"] { color: #F8FAFC !important; font-weight: 600; }

    /* Custom Recommendation Containers */
    .rec-card-approved {
        background-color: #064E3B;
        border: 1px solid #059669;
        border-radius: 8px;
        padding: 20px;
        color: #ECFDF5;
        margin-top: 15px;
    }
    .rec-card-rejected {
        background-color: #7F1D1D;
        border: 1px solid #DC2626;
        border-radius: 8px;
        padding: 20px;
        color: #FEF2F2;
        margin-top: 15px;
    }
    
    .badge-approved {
        background-color: #10B981; color: #064E3B;
        padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem;
    }
    .badge-rejected {
        background-color: #EF4444; color: #7F1D1D;
        padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem;
    }
    </style>
""", unsafe_allow_html=True)

# Header Section
st.title("QuantAgent")
st.caption("Autonomous Quantitative Risk & Portfolio Advisory System")
st.divider()

# ==========================================
# Sidebar Configuration
# ==========================================
st.sidebar.subheader("Portfolio Controls")

portfolio_cash = st.sidebar.number_input(
    "Portfolio Cash ($)",
    min_value=1000.0,
    max_value=1000000.0,
    value=10000.0,
    step=1000.0
)

target_symbol = st.sidebar.text_input("Stock Symbol", value="NVDA").upper()

proposed_amount = st.sidebar.number_input(
    "Proposed Trade ($)",
    min_value=100.0,
    max_value=portfolio_cash,
    value=3000.0,
    step=250.0
)

run_analysis = st.sidebar.button("Execute Analysis", type="primary", use_container_width=True)

# Initialize Engine Classes
@st.cache_resource
def load_engines():
    return MarketDataEngine(), RiskEngine(), AIAgentCore()

data_engine, risk_engine, ai_agent = load_engines()

# ==========================================
# Main Dashboard
# ==========================================
if run_analysis or target_symbol:
    with st.spinner(f"Retrieving market analytics for {target_symbol}..."):
        try:
            # 1. Fetch Market Data
            raw_df = data_engine.fetch_historical_data(target_symbol)
            df = data_engine.add_technical_indicators(raw_df)
            summary = data_engine.get_market_summary(target_symbol)

            # 2. Key Technical Metrics Row
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Price", f"${summary['latest_price']}", f"{summary['daily_change_pct']}%")
            m2.metric("RSI (14)", summary['rsi_14'])
            m3.metric("SMA 20/50", f"${summary['sma_20']} / ${summary['sma_50']}")
            m4.metric("Volatility", f"{summary['annualized_volatility'] * 100:.1f}%")
            m5.metric("52W High/Low", f"${summary['52w_high']} / ${summary['52w_low']}")

            st.write("")

            # 3. Technical Chart (Plotly Dark Template)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.75, 0.25])

            # Candlestick
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name='Price'
            ), row=1, col=1)

            # SMAs
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], mode='lines', name='SMA 20', line=dict(color='#F59E0B', width=1.2)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], mode='lines', name='SMA 50', line=dict(color='#3B82F6', width=1.2)), row=1, col=1)

            # RSI
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], mode='lines', name='RSI 14', line=dict(color='#A855F7', width=1.2)), row=2, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="#EF4444", row=2, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="#10B981", row=2, col=1)

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(15,23,42,0.6)',
                height=450,
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)

            # 4. AI Advisory Output
            st.subheader("Quantitative Risk Assessment & Recommendation")

            with st.spinner("Evaluating trade parameters against risk engine..."):
                prompt = f"Should I buy ${proposed_amount:,.2f} worth of {target_symbol} stock right now?"
                agent_result = ai_agent.run_advisor_agent(prompt, portfolio_value=portfolio_cash)

            # Render Recommendation Text
            st.markdown(agent_result["final_answer"])

            # Render ReAct Reasoning Trace in Clean Expander
            with st.expander("Agent Execution Trace & Tool Logs"):
                for log in agent_result["trace_log"]:
                    st.caption(f"**Step {log['iteration']} - {log['action']}**")
                    if log['action'] == 'TOOL_CALL':
                        st.code(f"{log['tool']}({log['args']})", language="json")
                    else:
                        st.json(log['result'])

        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")