import streamlit as st
import requests
from streamlit_searchbox import st_searchbox
from src.agent.core import QuantAgent
from src.UI.charts import render_candlestick_chart
from src.utils.storage import load_chat_history, save_chat_history

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()
# 1. Page Configuration
st.set_page_config(
    page_title="QuantAgent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Custom CSS for Professional Dashboard & Green Focus Glow ---
# --- Custom CSS for Professional Dashboard & Clean Green Glow ---
st.markdown(
    """
    <style>
        /* 1. Remove excessive top padding */
        .block-container {
            padding-top: 2rem !important;
            padding-bottom: 1rem !important;
            max-width: 95% !important;
        }
        
        /* 2. Outer Chat Container Styling & Green Glow (Fixing the Red Bleed) */
        div[data-testid="stChatInputContainer"], 
        div[data-testid="stChatInput"] {
            border-radius: 12px !important;
            border: 1px solid #31333F !important;
            outline: none !important;
        }
        
        div[data-testid="stChatInputContainer"]:focus-within,
        div[data-testid="stChatInput"]:focus-within {
            border-color: #00E676 !important;
            box-shadow: 0 0 10px rgba(0, 230, 118, 0.4) !important;
            outline: none !important;
        }
        
        /* 3. Aggressive Reset: Remove inner red borders and default focus rings */
        div[data-testid="stChatInput"] * {
            box-shadow: none !important;
        }
        div[data-testid="stChatInput"] div[data-baseweb="input"] {
            border-color: transparent !important;
            background-color: transparent !important;
        }
        
        /* 4. The Real Green Glow on the Outer Container */
        div[data-testid="stChatInput"] {
            border: 1px solid #31333F !important;
            border-radius: 12px !important;
            transition: all 0.2s ease-in-out;
        }
        div[data-testid="stChatInput"]:focus-within {
            border-color: #00E676 !important;
            box-shadow: 0 0 10px rgba(0, 230, 118, 0.4) !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# 2. Cached resources / helpers
@st.cache_resource
def get_agent() -> QuantAgent:
    """Created once per server process instead of on every Streamlit rerun."""
    return QuantAgent()


@st.cache_data(ttl=60, show_spinner=False)
def load_summary(symbol: str):
    """Market snapshot for the dashboard, cached for 60 seconds. Returns None on failure."""
    try:
        return get_agent().data_engine.get_market_summary(symbol)
    except Exception:
        return None


def fmt(value, suffix: str = "", digits: int = 2) -> str:
    """Formats a number for display, or 'N/A' if missing/invalid."""
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def search_tickers(searchterm: str):
    """Queries the Yahoo Finance public search endpoint for matching tickers."""
    if not searchterm:
        return []

    url = "https://query2.finance.yahoo.com/v1/finance/search"
    params = {"q": searchterm, "quotesCount": 5, "newsCount": 0}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=3).json()
        quotes = res.get("quotes", [])
        return [(f"{q['symbol']} - {q.get('shortname', '')}", q["symbol"]) for q in quotes if "symbol" in q]
    except Exception:
        return []


agent = get_agent()

# 3. Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "NVDA"
if "portfolio_value" not in st.session_state:
    st.session_state.portfolio_value = 10000.0

# 4. Layout: 70% terminal, 30% chat
col_main, col_chat = st.columns([7, 3], gap="large")

# ==========================================
# LEFT COLUMN: Trading Terminal
# ==========================================
with col_main:
    st.title("📈 QuantAgent")

    selected_value = st_searchbox(
        search_tickers,
        key="ticker_searchbox",
        placeholder="Search ticker (e.g., TSLA, NVDA, AAPL)...",
    )
    if selected_value:
        st.session_state.selected_ticker = selected_value

    st.number_input(
        "Portfolio value (USD)",
        min_value=100.0,
        step=500.0,
        key="portfolio_value",
        help="Used by the risk guardrails (e.g., the 25% single-position cap).",
    )

    symbol = st.session_state.selected_ticker
    st.subheader(f"Active Symbol: {symbol}")
    st.markdown("---")
    st.markdown("#### Live Market Snapshot")

    summary = load_summary(symbol)
    if not summary:
        st.warning(f"Could not load market data for {symbol}.")
        summary = {}

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(label="Latest Price", value=fmt(summary.get("latest_price"), " USD"))
    with m2:
        st.metric(label="VWAP", value=fmt(summary.get("vwap"), " USD"))
    with m3:
        st.metric(label="RSI (14)", value=fmt(summary.get("rsi_14")))
    with m4:
        st.metric(label="ATR", value=fmt(summary.get("atr_14", summary.get("atr"))))

    st.markdown("---")
    if symbol:
        historical_data = agent.data_engine.fetch_historical_data(symbol, period="2d", interval="5m")
        if not historical_data.empty:
            fig = render_candlestick_chart(historical_data, symbol)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No historical data found for {symbol}.")
    else:
        st.info("Please search for a symbol to view the chart.")

# ==========================================
# RIGHT COLUMN: AI Co-Pilot
# ==========================================
with col_chat:
    st.subheader("🤖 AI Co-Pilot")

    chat_container = st.container(height=530)

    with chat_container:
        if not st.session_state.messages:
            st.info("QuantAgent is online and ready. Search a symbol on the left or ask any risk question below.")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if user_prompt := st.chat_input("Ask QuantAgent..."):
        history = list(st.session_state.messages)[-15:]  # history BEFORE this message
        
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        save_chat_history(st.session_state.messages) 
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("Analyzing market data & risk guardrails..."):
                    response = agent.run_advisor_agent(
                        user_prompt=user_prompt,
                        portfolio_value=float(st.session_state.portfolio_value),
                        chat_history=history,
                        active_symbol=st.session_state.selected_ticker,
                    )
                    final_answer = response.get("final_answer", "No response generated.")
                    final_answer = final_answer.replace("$", "USD ") # to avoid frontend LaTeX parser bug
                    st.markdown(final_answer)

        st.session_state.messages.append({"role": "assistant", "content": final_answer})
        save_chat_history(st.session_state.messages) 
    st.markdown("---") 
    st.caption("⚠️ **Risk Warning & Disclaimer:** QuantAgent provides automated quantitative analysis for educational and informational purposes only. It is **not** a licensed financial advisor. All trading involves risk, and investment decisions are strictly your own.")
