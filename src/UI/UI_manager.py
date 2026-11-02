from datetime import datetime
from typing import Any, Dict, Tuple
import pytz
import streamlit as st


class UIManager:
    """Manages application layout, CSS injection, theme toggling, and UI component rendering."""

    DARK_THEME = {
        "bg_primary": "#0B0F17",
        "bg_secondary": "#161B26",
        "bg_card": "rgba(22, 27, 38, 0.85)",
        "text_primary": "#F3F4F6",
        "text_secondary": "#9CA3AF",
        "border_color": "rgba(255, 255, 255, 0.1)",
        "accent_color": "#00F090",
        "accent_glow": "rgba(0, 240, 144, 0.25)",
        "accent_blue": "#3B82F6",
        "chat_user_bg": "#1E293B",
        "chat_bot_bg": "#111827",
        "toggle_track": "#1F2937",
    }

    LIGHT_THEME = {
        "bg_primary": "#F1F5F9",
        "bg_secondary": "#FFFFFF",
        "bg_card": "#FFFFFF",
        "text_primary": "#0F172A",
        "text_secondary": "#475569",
        "border_color": "rgba(0, 0, 0, 0.12)",
        "accent_color": "#10B981",
        "accent_glow": "rgba(16, 185, 129, 0.25)",
        "accent_blue": "#2563EB",
        "chat_user_bg": "#E2E8F0",
        "chat_bot_bg": "#F8FAFC",
        "toggle_track": "#CBD5E1",
    }

    def __init__(self):
        self._init_theme_state()

    def _init_theme_state(self) -> None:
        """Initialize default theme to dark if not set."""
        if "theme" not in st.session_state:
            st.session_state["theme"] = "dark"

    @property
    def current_theme_name(self) -> str:
        return st.session_state["theme"]

    @property
    def theme_config(self) -> Dict[str, str]:
        return (
            self.DARK_THEME
            if self.current_theme_name == "dark"
            else self.LIGHT_THEME
        )

    def inject_global_styles(self) -> None:
        """Injects dynamic theme variables and precise CSS overrides."""
        cfg = self.theme_config
        css = f"""
        <style>
            :root {{
                --bg-primary: {cfg['bg_primary']};
                --bg-secondary: {cfg['bg_secondary']};
                --bg-card: {cfg['bg_card']};
                --text-primary: {cfg['text_primary']};
                --text-secondary: {cfg['text_secondary']};
                --border-color: {cfg['border_color']};
                --accent-color: {cfg['accent_color']};
                --accent-glow: {cfg['accent_glow']};
                --accent-blue: {cfg['accent_blue']};
                --chat-user-bg: {cfg['chat_user_bg']};
                --chat-bot-bg: {cfg['chat_bot_bg']};
                --toggle-track: {cfg['toggle_track']};
            }}

            /* ===== App General Setup ===== */
            .stApp {{
                background-color: var(--bg-primary) !important;
                color: var(--text-primary) !important;
            }}

            #MainMenu, footer, header {{ visibility: hidden; }}

            .block-container {{
                padding-top: 1.2rem !important;
                padding-bottom: 1rem !important;
                max-width: 96% !important;
            }}

            /* ===== Base Inputs & Searchbox Override ===== */
            div[data-baseweb="input"], div[data-baseweb="select"] {{
                background-color: var(--bg-secondary) !important;
                border-radius: 8px !important;
                border: 1px solid var(--border-color) !important;
                color: var(--text-primary) !important;
            }}

            div[data-baseweb="input"] input {{
                color: var(--text-primary) !important;
            }}

            /* ===== Market Status Pulse Indicator ===== */
            @keyframes pulse-green {{
                0% {{ box-shadow: 0 0 0 0 rgba(0, 240, 144, 0.6); }}
                70% {{ box-shadow: 0 0 0 6px rgba(0, 240, 144, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(0, 240, 144, 0); }}
            }}
            @keyframes pulse-red {{
                0% {{ box-shadow: 0 0 0 0 rgba(255, 77, 77, 0.6); }}
                70% {{ box-shadow: 0 0 0 6px rgba(255, 77, 77, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(255, 77, 77, 0); }}
            }}
            .market-status {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 0.82rem;
                font-weight: 600;
                color: var(--text-secondary);
                padding: 6px 0;
            }}
            .status-dot {{
                height: 9px; width: 9px;
                border-radius: 50%;
                display: inline-block;
            }}
            .status-dot.open {{
                background-color: var(--accent-color);
                animation: pulse-green 2s infinite;
            }}
            .status-dot.closed {{
                background-color: #FF4D4D;
                animation: pulse-red 2s infinite;
            }}

            /* ===== Floating Metric Cards ===== */
            .floating-metrics-container {{
                display: flex;
                gap: 12px;
                margin-top: 10px;
                margin-bottom: 15px;
                width: 100%;
            }}

            .metric-card {{
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 10px 14px;
                flex: 1;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
                transition: border-color 0.2s ease, transform 0.2s ease;
            }}

            .metric-card:hover {{
                border-color: var(--accent-blue);
                transform: translateY(-1px);
            }}

            .metric-label {{
                font-size: 0.7rem;
                color: var(--text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-weight: 600;
            }}

            .metric-value {{
                font-size: 1.05rem;
                font-family: 'JetBrains Mono', monospace;
                font-weight: 700;
                color: var(--text-primary);
                margin-top: 2px;
            }}

            /* ===== Terminal Input Labels & Pixel-Perfect Alignment ===== */
            .input-label {{
                font-size: 0.72rem !important;
                font-weight: 600 !important;
                color: var(--text-secondary) !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
                margin-bottom: 6px !important;
                margin-top: 0 !important;
                display: block !important;
            }}

            /* Enforce exact 40px height & zero margins on both input boxes */
            div[data-testid="stNumberInput"], 
            div[data-testid="stNumberInput"] > div,
            div[data-baseweb="input"],
            .stSearchbox,
            .stSearchbox > div {{
                height: 40px !important;
                min-height: 40px !important;
                max-height: 40px !important;
                margin-top: 0 !important;
                margin-bottom: 0 !important;
            }}

            div[data-testid="stNumberInput"] input,
            div[data-baseweb="input"] input {{
                height: 40px !important;
                line-height: 40px !important;
                padding-top: 0 !important;
                padding-bottom: 0 !important;
                color: var(--text-primary) !important;
            }}

            /* Align buttons inside number input */
            div[data-testid="stNumberInput"] button {{
                height: 38px !important;
            }}

            /* ===== Chat Component Styling Overrides ===== */
            .stChatMessage {{
                background-color: var(--bg-secondary) !important;
                border: 1px solid var(--border-color) !important;
                border-radius: 10px !important;
                color: var(--text-primary) !important;
            }}

            div[data-testid="stChatMessageContent"] {{
                color: var(--text-primary) !important;
            }}

            div[data-testid="stChatInputContainer"],
            div[data-testid="stChatInput"] {{
                border-radius: 12px !important;
                border: 1px solid var(--border-color) !important;
                background-color: var(--bg-secondary) !important;
                outline: none !important;
                transition: all 0.2s ease-in-out;
            }}

            div[data-testid="stChatInputContainer"]:focus-within,
            div[data-testid="stChatInput"]:focus-within {{
                border-color: var(--accent-color) !important;
                box-shadow: 0 0 10px var(--accent-glow) !important;
            }}

            /* ===== iOS-Style Toggle Switch (DOM Override) ===== */
            
            /* Align container & hide widget label */
            div[data-testid="stCheckbox"]:has(input[aria-label="Theme Toggle"]) {{
                display: flex !important;
                justify-content: flex-end !important;
                padding-top: 4px !important;
            }}
            div[data-testid="stCheckbox"]:has(input[aria-label="Theme Toggle"]) div[data-testid="stWidgetLabel"] {{
                display: none !important;
            }}

            /* Track styling */
            span:has(input[aria-label="Theme Toggle"]) + div {{
                background-color: var(--toggle-track) !important;
                border: 1px solid var(--border-color) !important;
                width: 52px !important;
                height: 28px !important;
                border-radius: 14px !important;
                padding: 2px !important;
                box-sizing: border-box !important;
                transition: background-color 0.3s ease !important;
            }}

            /* Base Knob styling (Light Mode) */
            span:has(input[aria-label="Theme Toggle"]) + div > div {{
                background-color: #FFFFFF !important;
                width: 22px !important;
                height: 22px !important;
                border-radius: 50% !important;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                position: relative !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            }}

            /* Sun emoji for light mode (unchecked) */
            span:has(input[aria-label="Theme Toggle"]:not(:checked)) + div > div::after {{
                content: "☀️" !important;
                font-size: 13px !important;
                position: absolute !important;
            }}

            /* Dark Mode Knob Override: Darker background & shifted further right */
            span:has(input[aria-label="Theme Toggle"]:checked) + div > div {{
                background-color: #1E293B !important;
                border: 1px solid rgba(255, 255, 255, 0.15) !important;
                transform: translateX(24px) !important;
            }}

            /* Moon emoji for dark mode (checked) */
            span:has(input[aria-label="Theme Toggle"]:checked) + div > div::after {{
                content: "🌙" !important;
                font-size: 13px !important;
                position: absolute !important;
            }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

    def render_market_status(self) -> None:
        """Renders live pulsing dot based on US Market Hours (EST)."""
        tz = pytz.timezone("US/Eastern")
        now = datetime.now(tz)
        is_open = False
        if now.weekday() < 5:
            market_start = now.replace(
                hour=9, minute=30, second=0, microsecond=0
            )
            market_end = now.replace(
                hour=16, minute=0, second=0, microsecond=0
            )
            if market_start <= now <= market_end:
                is_open = True

        status_text = "MARKET LIVE" if is_open else "MARKET CLOSED"
        dot_class = "open" if is_open else "closed"

        html = f"""
        <div class="market-status">
            <span class="status-dot {dot_class}"></span>
            <span>{status_text}</span>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)

    def create_main_layout(self) -> Tuple[Any, Any]:
        """Creates 70% / 30% grid split for Trading Terminal and AI Co-Pilot."""
        return st.columns([7, 3], gap="medium")

    def render_floating_metrics(self, market_summary: Dict[str, Any]) -> None:
        """Renders custom metric cards above the chart region."""
        price = market_summary.get("latest_price", "N/A")
        vwap = market_summary.get("vwap", "N/A")
        rsi = market_summary.get("rsi_14", "N/A")
        atr = market_summary.get(
            "atr_14", market_summary.get("atr", "N/A")
        )

        def fmt(val, suffix=""):
            try:
                return f"{float(val):,.2f}{suffix}"
            except (ValueError, TypeError):
                return "N/A"

        html = f"""
        <div class="floating-metrics-container">
            <div class="metric-card">
                <div class="metric-label">Latest Price</div>
                <div class="metric-value">{fmt(price, ' USD')}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">VWAP</div>
                <div class="metric-value">{fmt(vwap, ' USD')}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">RSI (14)</div>
                <div class="metric-value">{fmt(rsi)}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">ATR</div>
                <div class="metric-value">{fmt(atr)}</div>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)