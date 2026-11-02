import streamlit as st
import requests
from streamlit_searchbox import st_searchbox
from src.agent.core import QuantAgent
from src.UI.charts import render_candlestick_chart
from src.UI.UI_manager import UIManager
from src.utils.storage import load_chat_history, save_chat_history

# 1. Page Config
st.set_page_config(
    page_title="QuantAgent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ui_mgr = UIManager()
ui_mgr.inject_global_styles()

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "NVDA"
if "portfolio_value" not in st.session_state:
    st.session_state.portfolio_value = 10000.0

# 2. Helpers
@st.cache_resource
def get_agent() -> QuantAgent:
    return QuantAgent()

@st.cache_data(ttl=60, show_spinner=False)
def load_summary(symbol: str):
    try:
        return get_agent().data_engine.get_market_summary(symbol)
    except Exception:
        return None

def search_tickers(searchterm: str):
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

# 3. Precision Aligned Top Control Bar
col_logo, col_search, col_port, col_status, col_toggle = st.columns(
    [2, 3, 2, 2, 1.2], vertical_alignment="center"
)

with col_logo:
    st.markdown("### 📈 **QuantAgent**")

with col_search:
    selected_value = st_searchbox(
        search_tickers,
        key="ticker_searchbox",
        placeholder="Search ticker (e.g. NVDA, TSLA)...",
    )
    if selected_value:
        st.session_state.selected_ticker = selected_value
        st.rerun()

with col_port:
    st.number_input(
        "Cash (USD)",
        min_value=100.0,
        step=500.0,
        key="portfolio_value",
        label_visibility="collapsed",  # מונע חריגת גובה
    )

with col_status:
    ui_mgr.render_market_status()

with col_toggle:
    is_dark = st.toggle(
        "Theme Toggle",
        value=(ui_mgr.current_theme_name == "dark"),
        key="theme_toggle",
        label_visibility="collapsed",
    )
    new_theme = "dark" if is_dark else "light"
    if new_theme != ui_mgr.current_theme_name:
        st.session_state["theme"] = new_theme
        st.rerun()

st.markdown("---")

# 4. Main Grid Split (70/30)
col_main, col_chat = ui_mgr.create_main_layout()

with col_main:
    symbol = st.session_state.selected_ticker
    st.markdown(f"#### Active Symbol: **{symbol}**")
    
    summary = load_summary(symbol) or {}
    ui_mgr.render_floating_metrics(summary)

    if symbol:
        historical_data = agent.data_engine.fetch_historical_data(symbol, period="2d", interval="5m")
        if not historical_data.empty:
            fig = render_candlestick_chart(historical_data, symbol)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"No historical data found for {symbol}.")

with col_chat:
    st.subheader("🤖 AI Co-Pilot")
    chat_container = st.container(height=520)

    with chat_container:
        if not st.session_state.messages:
            st.info("QuantAgent is ready. Search a symbol or ask a risk question.")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if user_prompt := st.chat_input("Ask QuantAgent..."):
        history = list(st.session_state.messages)[-15:] 
        
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
                    final_answer = response.get("final_answer", "No response generated.").replace("$", "USD ")
                    st.markdown(final_answer)

        st.session_state.messages.append({"role": "assistant", "content": final_answer})
        save_chat_history(st.session_state.messages) 
        
    st.caption("⚠️ **Risk Warning:** Automated quantitative analysis for educational purposes only.")