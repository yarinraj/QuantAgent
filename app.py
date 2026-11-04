from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
from streamlit_searchbox import st_searchbox

from src.agent.core import QuantAgent
from src.UI.charts import render_candlestick_chart
from src.UI.UI_manager import UIManager
from src.utils.storage import load_chat_history, save_chat_history


class QuantAgentApp:
    """Streamlit front-end: trading terminal (left) + AI co-pilot chat (right)."""

    PAGE_TITLE = "QuantAgent"
    PAGE_ICON = "assets/quantagent_favicon.png"
    DEFAULT_TICKER = "NVDA"
    DEFAULT_PORTFOLIO = 10000.0
    HISTORY_WINDOW = 15
    LOGO_WIDTH = 220
    CHART_SKELETON_HEIGHT = 450  # keep close to the real chart height to avoid layout jumps
    YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

    DISCLAIMER = (
        "⚠️ <strong>Risk Warning & Disclaimer:</strong> QuantAgent is an educational AI demonstration "
        "tool using automated language models. AI outputs may contain inaccuracies. It is <strong>not</strong> "
        "a licensed financial advisor, does <strong>not</strong> offer investment advice, and assumes "
        "<strong>no liability</strong> for any financial decisions or trading losses. All trading involves risk."
    )

    # ==========================================
    # Setup
    # ==========================================
    def __init__(self) -> None:
        # set_page_config must be the first Streamlit call of the script run.
        st.set_page_config(
            page_title=self.PAGE_TITLE,
            page_icon=self.PAGE_ICON,
            layout="wide",
            initial_sidebar_state="collapsed",
        )
        self.ui = UIManager()
        self.ui.inject_global_styles()
        self._init_session_state()
        self.agent = self.get_agent()

    def _init_session_state(self) -> None:
        state = st.session_state
        if "messages" not in state:
            state.messages = load_chat_history()
        if "selected_ticker" not in state:
            state.selected_ticker = self.DEFAULT_TICKER
        if "portfolio_value" not in state:
            state.portfolio_value = self.DEFAULT_PORTFOLIO

    # ==========================================
    # Cached resources & data helpers
    # ==========================================
    @staticmethod
    @st.cache_resource(show_spinner="Starting QuantAgent...")
    def get_agent() -> QuantAgent:
        return QuantAgent()

    @staticmethod
    @st.cache_data(ttl=60, show_spinner=False)
    def load_summary(symbol: str) -> Optional[Dict[str, Any]]:
        try:
            return QuantAgentApp.get_agent().data_engine.get_market_summary(symbol)
        except Exception:
            return None

    @staticmethod
    @st.cache_data(ttl=60, show_spinner=False)
    def load_history(symbol: str):
        """Cached so chat messages / theme toggles don't refetch market data.
        Exceptions are not cached; the caller handles them."""
        return QuantAgentApp.get_agent().data_engine.fetch_historical_data(
            symbol, period="2d", interval="5m"
        )

    @classmethod
    def search_tickers(cls, searchterm: str) -> List[Tuple[str, str]]:
        if not searchterm:
            return []
        params = {"q": searchterm, "quotesCount": 5, "newsCount": 0}
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            res = requests.get(
                cls.YAHOO_SEARCH_URL, params=params, headers=headers, timeout=3
            ).json()
            quotes = res.get("quotes", [])
            return [
                (f"{q['symbol']} - {q.get('shortname', '')}", q["symbol"])
                for q in quotes
                if "symbol" in q
            ]
        except Exception:
            return []

    # ==========================================
    # Header bar (logo + theme toggle)
    # ==========================================
    def render_header(self) -> None:
        col_logo, col_toggle = st.columns([9, 1], vertical_alignment="center")

        with col_logo:
            self.ui.render_logo(width=self.LOGO_WIDTH)

        with col_toggle:
            is_dark = st.toggle(
                "Theme Toggle",
                value=(self.ui.current_theme_name == "dark"),
                key="theme_toggle",
                label_visibility="collapsed",
            )
            new_theme = "dark" if is_dark else "light"
            if new_theme != self.ui.current_theme_name:
                st.session_state["theme"] = new_theme
                st.rerun()

        st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
    # ==========================================
    # Left column: trading terminal
    # ==========================================
    def render_terminal(self) -> None:
        self._render_control_strip()

        symbol = st.session_state.selected_ticker

        sym_col, stat_col = st.columns([7, 3], vertical_alignment="center")
        with sym_col:
            st.markdown(f"<h4 style='margin-top:0; margin-bottom:0;'>Active Symbol: {symbol}</h4>", unsafe_allow_html=True)
        with stat_col:
            self.ui.render_market_status()

        metrics_slot = st.empty()
        metrics_slot.markdown(self.ui.metrics_skeleton_html(), unsafe_allow_html=True)
        summary = self.load_summary(symbol) or {}
        metrics_slot.markdown(
            self.ui.floating_metrics_html(summary), unsafe_allow_html=True
        )

        self._render_price_chart(symbol)

    def _render_control_strip(self) -> None:
        ctrl_search, ctrl_cash = st.columns([3.5, 1], vertical_alignment="top")

        with ctrl_search:
            st.markdown(
                "<span class='input-label'>Search Ticker</span>",
                unsafe_allow_html=True,
            )
            selected_symbol = st_searchbox(
                self.search_tickers,
                key="symbol_searchbox",
                placeholder="🔍 Search ticker (e.g. AAPL, TSLA, NVDA)...",
            )
            if selected_symbol and selected_symbol != st.session_state.selected_ticker:
                st.session_state.selected_ticker = selected_symbol
                st.rerun()

        with ctrl_cash:
            st.markdown(
                "<span class='input-label'>Portfolio Cash ($)</span>",
                unsafe_allow_html=True,
            )
            st.number_input(
                "Portfolio Cash ($)",
                min_value=100.0,
                step=500.0,
                key="portfolio_value",
                label_visibility="collapsed",
                help="Portfolio Cash ($) - Available cash for trading decisions",
            )

    def _render_price_chart(self, symbol: str) -> None:
        if not symbol:
            return

        chart_slot = st.empty()
        chart_slot.markdown(
            self.ui.chart_skeleton_html(self.CHART_SKELETON_HEIGHT),
            unsafe_allow_html=True,
        )

        try:
            historical_data = self.load_history(symbol)
        except Exception:
            chart_slot.warning(f"Could not load market data for {symbol}.")
            return

        if historical_data is None or historical_data.empty:
            chart_slot.warning(f"No historical data found for {symbol}.")
            return

        fig = render_candlestick_chart(
            historical_data, symbol, theme=self.ui.current_theme_name
        )
        chart_slot.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # Right column: AI co-pilot
    # ==========================================
    def render_chat(self) -> None:
        self.ui.render_assistant_header()
        chat_container = self.ui.create_chat_container()

        with chat_container:
            empty_slot = st.empty()
            if not st.session_state.messages:
                empty_slot.markdown(
                    self.ui.empty_state_html(), unsafe_allow_html=True
                )
            for message in st.session_state.messages:
                self.ui.render_chat_message(
                    message.get("role", "assistant"), message.get("content", "")
                )

        user_prompt = st.chat_input("Ask Quant Analyst...")
        if user_prompt:
            self._handle_user_prompt(user_prompt, chat_container, empty_slot)

        

    def _handle_user_prompt(
        self, user_prompt: str, chat_container: Any, empty_slot: Any
    ) -> None:
        history = list(st.session_state.messages)[-self.HISTORY_WINDOW :]

        st.session_state.messages.append({"role": "user", "content": user_prompt})
        save_chat_history(st.session_state.messages)

        with chat_container:
            empty_slot.empty()
            self.ui.render_chat_message("user", user_prompt)

            pending = st.empty()
            pending.markdown(self.ui.typing_indicator_html(), unsafe_allow_html=True)

            final_answer = self._ask_agent(user_prompt, history)

            pending.markdown(
                self.ui.chat_message_html("assistant", final_answer),
                unsafe_allow_html=True,
            )

        st.session_state.messages.append({"role": "assistant", "content": final_answer})
        save_chat_history(st.session_state.messages)

    def _ask_agent(self, user_prompt: str, history: List[Dict[str, str]]) -> str:
        response = self.agent.run_advisor_agent(
            user_prompt=user_prompt,
            portfolio_value=float(st.session_state.portfolio_value),
            chat_history=history,
            active_symbol=st.session_state.selected_ticker,
        )
        return response.get("final_answer", "No response generated.").replace(
            "$", "USD "
        )

    # ==========================================
    # Entry point
    # ==========================================
    def run(self) -> None:
        self.render_header()
        col_main, col_chat = self.ui.create_main_layout()

        with col_main:
            self.render_terminal()
        with col_chat:
            self.render_chat()
        # Global Footer for Disclaimer
        st.markdown("<hr class='footer-divider'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='footer-disclaimer'>{self.DISCLAIMER}</div>", 
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    QuantAgentApp().run()