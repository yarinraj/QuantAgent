import base64
import html
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytz
import streamlit as st


# ==========================================
# Chat message rendering (markdown -> safe HTML)
# ==========================================
class ChatMessageRenderer:
    """Turns chat messages into theme-aware, single-line, escaped HTML.

    Every message is rendered as ONE HTML block, so bubble sizing never
    depends on Streamlit's internal container layout. All user / LLM text is
    HTML-escaped before a small markdown subset is applied.
    """

    _UL_RE = re.compile(r"^[-*•]\s+(.*)$")
    _OL_RE = re.compile(r"^\d+[.)]\s+(.*)$")

    # ----- inline / block markdown -----
    @staticmethod
    def _inline(text: str) -> str:
        codes: List[str] = []

        def _stash(match: "re.Match[str]") -> str:
            codes.append(match.group(1))
            return f"\x00{len(codes) - 1}\x00"

        t = html.escape(text.replace("\x00", ""), quote=False)
        t = re.sub(r"`([^`\n]+)`", _stash, t)
        t = t.replace("$", "&#36;")
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(
            r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<em>\1</em>", t
        )
        t = re.sub(
            r"\[([^\]]+)\]\((https?://[^\s)\"'<>]+)\)",
            r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            t,
        )
        return re.sub(
            r"\x00(\d+)\x00",
            lambda m: f"<code>{codes[int(m.group(1))]}</code>",
            t,
        )

    @classmethod
    def markdown_to_html(cls, text: str) -> str:
        """Convert markdown to a single-line HTML string (no raw newlines)."""
        lines = text.replace("\r\n", "\n").split("\n")
        out: List[str] = []
        para: List[str] = []
        i = 0

        def flush() -> None:
            if para:
                out.append(
                    "<p>" + "<br>".join(cls._inline(x) for x in para) + "</p>"
                )
                para.clear()

        while i < len(lines):
            stripped = lines[i].strip()

            if stripped.startswith("```"):
                flush()
                i += 1
                code: List[str] = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code.append(lines[i])
                    i += 1
                i += 1
                out.append(
                    "<pre><code>"
                    + html.escape("\n".join(code), quote=False)
                    + "</code></pre>"
                )
                continue

            if not stripped:
                flush()
                i += 1
                continue

            if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
                flush()
                out.append("<hr>")
                i += 1
                continue

            heading = re.match(r"^#{1,6}\s+(.*)$", stripped)
            if heading:
                flush()
                out.append(f'<p class="qa-h">{cls._inline(heading.group(1))}</p>')
                i += 1
                continue

            pattern: Optional["re.Pattern[str]"] = None
            if cls._UL_RE.match(stripped):
                pattern = cls._UL_RE
            elif cls._OL_RE.match(stripped):
                pattern = cls._OL_RE

            if pattern is not None:
                flush()
                items: List[str] = []
                while i < len(lines):
                    current = lines[i].strip()
                    if not current:
                        j = i + 1
                        while j < len(lines) and not lines[j].strip():
                            j += 1
                        if j < len(lines) and pattern.match(lines[j].strip()):
                            i = j
                            continue
                        break
                    match = pattern.match(current)
                    if not match:
                        break
                    items.append(match.group(1))
                    i += 1
                tag = "ul" if pattern is cls._UL_RE else "ol"
                out.append(
                    f"<{tag}>"
                    + "".join(f"<li>{cls._inline(x)}</li>" for x in items)
                    + f"</{tag}>"
                )
                continue

            para.append(stripped)
            i += 1

        flush()
        # Raw newlines would terminate the HTML block inside st.markdown.
        return "".join(out).replace("\n", "&#10;")

    # ----- message-level HTML -----
    @classmethod
    def message_html(cls, role: str, content: str) -> str:
        role = "user" if role == "user" else "assistant"
        body = cls.markdown_to_html(content or "")
        bubble = f'<div class="qa-bubble qa-bubble-{role}" dir="auto">{body}</div>'
        if role == "user":
            avatar = '<div class="qa-av qa-av-user" aria-hidden="true"></div>'
            inner = bubble + avatar
        else:
            avatar = '<div class="qa-av" aria-hidden="true"></div>'
            inner = avatar + bubble
        return f'<div class="qa-row qa-row-{role}">{inner}</div>'

    @staticmethod
    def typing_html() -> str:
        return (
            '<div class="qa-row qa-row-assistant">'
            '<div class="qa-av" aria-hidden="true"></div>'
            '<div class="qa-bubble qa-bubble-assistant"><div class="qa-typing">'
            '<span class="qa-typing-dots"><i></i><i></i><i></i></span>'
            '<span class="qa-typing-label">'
            "Analyzing market data &amp; risk guardrails…</span>"
            "</div></div></div>"
        )

    @staticmethod
    def empty_state_html() -> str:
        return (
            '<div class="qa-empty">'
            '<div class="qa-av qa-av-lg" aria-hidden="true"></div>'
            '<div class="qa-empty-title">How can I help?</div>'
            '<div class="qa-empty-sub">Search a symbol, then ask about momentum, '
            "risk, or position sizing.</div></div>"
        )


# ==========================================
# UI manager: layout, themes, CSS and components
# ==========================================
class UIManager:
    """Manages application layout, CSS injection, themes, and UI components."""

    CHAT_PANEL_KEY = "qa-chat-panel"
    ASSISTANT_ICON_FILE = "quantagent_icon.png"
    # Used only if assets/quantagent_icon.png is missing.
    ASSISTANT_ICON_FALLBACK = (
        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'%3E%3Crect x='4' y='14' width='3' height='6' rx='1' fill='white'/%3E%3Crect x='9' y='11' width='3' height='9' rx='1' fill='white'/%3E%3Crect x='14' y='8' width='3' height='12' rx='1' fill='white'/%3E%3Cpath d='M3.5 10.5 9 6l4 3 7.5-5.5' stroke='white' stroke-width='1.7' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"
    )
    CHAT_PANEL_HEIGHT = 475  
    CHAT_VIEWPORT_OFFSET = 380
    CHAT_MIN_HEIGHT = 300
    CHAT_MAX_HEIGHT = 760

    DARK_THEME = {
        "bg_primary": "#0B0F17",
        "bg_secondary": "#161B26",
        "bg_card": "rgba(22, 27, 38, 0.85)",
        "text_primary": "#F3F4F6",
        "text_secondary": "#9CA3AF",
        "border_color": "rgba(255, 255, 255, 0.12)",
        "accent_color": "#26A69A",
        "accent_glow": "rgba(38, 166, 154, 0.22)",
        "positive_color": "#26A69A",
        "negative_color": "#EF5350",
        "accent_blue": "#3B82F6",
        "chat_user_bg": "#172C4A",
        "chat_bot_bg": "#15312F",
        "chat_user_border": "rgba(59, 130, 246, 0.36)",
        "chat_bot_border": "rgba(38, 166, 154, 0.32)",
        "toggle_track": "#1F2937",
        "avatar_bg": "#111F28",
        "avatar_border": "rgba(38, 166, 154, 0.45)",
        "skeleton_base": "rgba(255, 255, 255, 0.06)",
        "skeleton_highlight": "rgba(255, 255, 255, 0.13)",
        "iframe_filter": "none",
    }

    LIGHT_THEME = {
        "bg_primary": "#F1F5F9",
        "bg_secondary": "#FFFFFF",
        "bg_card": "#FFFFFF",
        "text_primary": "#0F172A",
        "text_secondary": "#475569",
        "border_color": "rgba(0, 0, 0, 0.12)",
        "accent_color": "#26A69A",
        "accent_glow": "rgba(38, 166, 154, 0.22)",
        "positive_color": "#26A69A",
        "negative_color": "#EF5350",
        "accent_blue": "#2563EB",
        "chat_user_bg": "#EFF6FF",
        "chat_bot_bg": "#EAF7F5",
        "chat_user_border": "rgba(37, 99, 235, 0.24)",
        "chat_bot_border": "rgba(38, 166, 154, 0.26)",
        "toggle_track": "#CBD5E1",
        "avatar_bg": "#FFFFFF",
        "avatar_border": "rgba(38, 166, 154, 0.50)",
        "skeleton_base": "rgba(15, 23, 42, 0.06)",
        "skeleton_highlight": "rgba(15, 23, 42, 0.12)",
        "iframe_filter": "invert(1) hue-rotate(180deg)",
    }

    def __init__(self) -> None:
        self._init_theme_state()
        self._chat_renderer = ChatMessageRenderer()

    # ----- theme state -----
    def _init_theme_state(self) -> None:
        """Initialize the application theme to dark when none is stored."""
        if "theme" not in st.session_state:
            st.session_state["theme"] = "dark"

    @property
    def current_theme_name(self) -> str:
        return st.session_state.get("theme", "dark")

    @property
    def theme_config(self) -> Dict[str, str]:
        if self.current_theme_name == "light":
            return self.LIGHT_THEME
        return self.DARK_THEME

    # ----- global styles -----
    def inject_global_styles(self) -> None:
        """Inject global theme, typography, and chat styling."""
        cfg = self.theme_config
        avatar_uri = self._assistant_avatar_uri()

        css = f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Poppins:wght@400;500;600;700&display=swap');

            :root {{
                --bg-primary: {cfg['bg_primary']};
                --bg-secondary: {cfg['bg_secondary']};
                --bg-card: {cfg['bg_card']};
                --text-primary: {cfg['text_primary']};
                --text-secondary: {cfg['text_secondary']};
                --border-color: {cfg['border_color']};
                --accent-color: {cfg['accent_color']};
                --accent-glow: {cfg['accent_glow']};
                --positive-color: {cfg['positive_color']};
                --negative-color: {cfg['negative_color']};
                --accent-blue: {cfg['accent_blue']};
                --chat-user-bg: {cfg['chat_user_bg']};
                --chat-bot-bg: {cfg['chat_bot_bg']};
                --chat-user-border: {cfg['chat_user_border']};
                --chat-bot-border: {cfg['chat_bot_border']};
                --toggle-track: {cfg['toggle_track']};
                --avatar-bg: {cfg['avatar_bg']};
                --avatar-border: {cfg['avatar_border']};
                --skeleton-base: {cfg['skeleton_base']};
                --skeleton-highlight: {cfg['skeleton_highlight']};
                --iframe-filter: {cfg['iframe_filter']};
                --font-primary: 'Poppins', sans-serif;
                --font-numeric: 'Inter', sans-serif;
            }}

            /* ===== Global Typography ===== */
            html,
            body,
            .stApp,
            .stApp p,
            .stApp span,
            .stApp label,
            .stApp button,
            .stApp input,
            .stApp textarea,
            .stApp select,
            .stApp option,
            .stApp a,
            .stApp h1,
            .stApp h2,
            .stApp h3,
            .stApp h4,
            .stApp h5,
            .stApp h6,
            .stApp li,
            .stApp [data-testid="stMarkdownContainer"],
            .stApp [data-testid="stWidgetLabel"] {{
                font-family: var(--font-primary) !important;
            }}

            .metric-value,
            .st-key-portfolio_value input,
            .stApp [data-testid="stMetricValue"],
            .stApp [data-testid="stMetricValue"] * {{
                font-family: var(--font-numeric) !important;
                font-variant-numeric: tabular-nums lining-nums;
                font-feature-settings: "tnum" 1, "lnum" 1;
            }}

            /* ===== App General Setup ===== */
            .stApp {{
                background-color: var(--bg-primary) !important;
                color: var(--text-primary) !important;
            }}

            #MainMenu, footer, header {{ visibility: hidden; }}

            .block-container {{
                padding-top: 0.5rem !important;
                padding-bottom: 0.5rem !important;
                max-width: 96% !important;
            }}

            hr {{
                border: none !important;
                border-top: 1px solid var(--border-color) !important;
                opacity: 1 !important;
                margin-top: 0.5rem !important;
                margin-bottom: 1rem !important;
            }}

            iframe[title*="searchbox"] {{
                filter: var(--iframe-filter) !important;
                transition: filter 0.3s ease;
            }}

            /* ===== Market Status Indicator ===== */
            @keyframes pulse-green {{
                0% {{ box-shadow: 0 0 0 0 rgba(38, 166, 154, 0.60); }}
                70% {{ box-shadow: 0 0 0 6px rgba(38, 166, 154, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(38, 166, 154, 0); }}
            }}

            @keyframes pulse-red {{
                0% {{ box-shadow: 0 0 0 0 rgba(239, 83, 80, 0.60); }}
                70% {{ box-shadow: 0 0 0 6px rgba(239, 83, 80, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(239, 83, 80, 0); }}
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
                width: 9px;
                height: 9px;
                border-radius: 50%;
                display: inline-block;
            }}

            .status-dot.open {{
                background-color: var(--positive-color);
                animation: pulse-green 2s infinite;
            }}

            .status-dot.closed {{
                background-color: var(--negative-color);
                animation: pulse-red 2s infinite;
            }}

            /* ===== Floating Metric Cards ===== */
            .floating-metrics-container {{
                display: flex;
                gap: 12px;
                margin-top: 6px;
                margin-bottom: 8px;
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
                font-family: var(--font-primary) !important;
                font-size: 0.7rem;
                color: var(--text-secondary);
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-weight: 600;
            }}

            .metric-value {{
                font-family: var(--font-numeric) !important;
                font-size: 1.05rem;
                font-weight: 600;
                color: var(--text-primary);
                margin-top: 2px;
                letter-spacing: -0.02em;
                font-variant-numeric: tabular-nums lining-nums;
                font-feature-settings: "tnum" 1, "lnum" 1;
            }}

            /* ===== Terminal Input Labels ===== */
            .input-label {{
                font-family: var(--font-primary) !important;
                font-size: 0.72rem !important;
                font-weight: 600 !important;
                color: var(--text-secondary) !important;
                text-transform: uppercase !important;
                letter-spacing: 0.5px !important;
                margin-bottom: 6px !important;
                margin-top: 0 !important;
                display: block !important;
            }}

            .stSearchbox,
            .stSearchbox > div,
            .st-key-portfolio_value [data-testid="stNumberInput"],
            .st-key-portfolio_value [data-testid="stNumberInputContainer"] {{
                height: 40px !important;
                min-height: 40px !important;
                max-height: 40px !important;
                margin-top: 0 !important;
                margin-bottom: 0 !important;
            }}

            /* ===== Portfolio Cash ===== */
            .st-key-portfolio_value [data-testid="stNumberInputContainer"] {{
                box-sizing: border-box !important;
                background-color: var(--bg-secondary) !important;
                border: 1px solid var(--border-color) !important;
                border-radius: 8px !important;
                overflow: hidden !important;
            }}

            .st-key-portfolio_value input[data-testid="stNumberInputField"] {{
                height: 38px !important;
                min-height: 38px !important;
                box-sizing: border-box !important;
                background-color: transparent !important;
                color: var(--text-primary) !important;
                -webkit-text-fill-color: var(--text-primary) !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepDown"]:enabled {{
                color: var(--negative-color) !important;
                background-color: transparent !important;
                border: none !important;
                box-shadow: none !important;
                transition: color 0.2s ease, background-color 0.2s ease !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepDown"]:enabled svg {{
                color: var(--negative-color) !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepDown"]:hover:enabled {{
                color: var(--negative-color) !important;
                background-color: rgba(239, 83, 80, 0.14) !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepDown"]:focus:enabled:not(:hover) {{
                color: var(--negative-color) !important;
                background-color: transparent !important;
                box-shadow: none !important;
                outline: none !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepUp"]:enabled {{
                color: var(--positive-color) !important;
                background-color: transparent !important;
                border: none !important;
                box-shadow: none !important;
                transition: color 0.2s ease, background-color 0.2s ease !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepUp"]:enabled svg {{
                color: var(--positive-color) !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepUp"]:hover:enabled {{
                color: var(--positive-color) !important;
                background-color: rgba(38, 166, 154, 0.14) !important;
            }}

            .st-key-portfolio_value button[data-testid="stNumberInputStepUp"]:focus:enabled:not(:hover) {{
                color: var(--positive-color) !important;
                background-color: transparent !important;
                box-shadow: none !important;
                outline: none !important;
            }}

            /* ===== QuantAgent Chat ===== */
            .st-key-{self.CHAT_PANEL_KEY} {{
                box-sizing: border-box !important;
                height: clamp({self.CHAT_MIN_HEIGHT}px, calc(100vh - {self.CHAT_VIEWPORT_OFFSET}px), {self.CHAT_MAX_HEIGHT}px) !important;
                background: var(--bg-card) !important;
                border: 1px solid var(--border-color) !important;
                border-radius: 14px !important;
                padding: 18px 16px !important;
                scrollbar-width: thin;
                scrollbar-color: var(--border-color) transparent;
            }}

            .qa-row {{
                display: flex;
                align-items: flex-start;
                gap: 10px;
                width: 100%;
                direction: ltr;
                box-sizing: border-box;
                margin: 0 0 10px 0;
            }}

            .qa-row-user {{ justify-content: flex-end; }}

            .qa-av {{
                box-sizing: border-box;
                flex: 0 0 34px;
                width: 34px;
                height: 34px;
                border-radius: 50%;
                background-color: var(--avatar-bg);
                background-image: url("{avatar_uri}");
                background-position: center;
                background-repeat: no-repeat;
                background-size: 64% 64%;
                border: 1px solid var(--avatar-border);
            }}

            .qa-av-user {{
                background-color: #2563EB;
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round'%3E%3Ccircle cx='12' cy='8' r='3.6'/%3E%3Cpath d='M5 20c0-3.9 3.1-6.5 7-6.5s7 2.6 7 6.5'/%3E%3C/svg%3E");
                background-size: 19px 19px;
                border-color: transparent;
            }}

            .qa-av-lg {{
                width: 56px;
                height: 56px;
                flex-basis: 56px;
            }}

            .qa-bubble {{
                box-sizing: border-box;
                max-width: calc(100% - 46px);
                min-width: 0;
                padding: 12px 16px;
                border-radius: 18px;
                font-size: 0.92rem;
                line-height: 1.6;
                color: var(--text-primary);
                overflow-wrap: anywhere;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
            }}

            .qa-bubble-user {{
                max-width: min(80%, calc(100% - 46px));
                background: var(--chat-user-bg);
                border: 1px solid var(--chat-user-border);
            }}

            .qa-bubble-assistant {{
                background: var(--chat-bot-bg);
                border: 1px solid var(--chat-bot-border);
            }}

            .stApp .qa-bubble p {{
                margin: 0 0 0.55em 0 !important;
                padding: 0 !important;
                font-size: inherit !important;
                line-height: inherit !important;
                color: inherit !important;
            }}
            .stApp .qa-bubble > :last-child {{ margin-bottom: 0 !important; }}
            .stApp .qa-bubble ul,
            .stApp .qa-bubble ol {{
                margin: 0 0 0.55em 0;
                padding-inline-start: 1.25em;
            }}
            .stApp .qa-bubble li {{ margin: 0.15em 0; color: inherit; }}
            .stApp .qa-bubble strong {{ font-weight: 600; color: inherit; }}
            .stApp .qa-bubble .qa-h {{ font-weight: 600 !important; font-size: 1.04em !important; }}
            .stApp .qa-bubble hr {{
                border: none !important;
                border-top: 1px solid var(--chat-bot-border) !important;
                margin: 0.7em 0 !important;
                opacity: 1 !important;
            }}
            .stApp .qa-bubble a {{
                color: var(--accent-blue);
                text-decoration: underline;
                text-underline-offset: 2px;
            }}
            .stApp .qa-bubble code {{
                font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
                font-size: 0.82em;
                padding: 1px 6px;
                border-radius: 6px;
                background: rgba(127, 127, 127, 0.18);
                color: inherit;
            }}
            .stApp .qa-bubble pre {{
                margin: 0.3em 0 0.6em 0;
                padding: 10px 12px;
                overflow-x: auto;
                border-radius: 9px;
                background: rgba(127, 127, 127, 0.14);
                border: 1px solid var(--border-color);
            }}
            .stApp .qa-bubble pre code {{ background: none; padding: 0; font-size: 0.8rem; }}

            .qa-typing {{ display: inline-flex; align-items: center; gap: 10px; }}
            .qa-typing-dots {{ display: inline-flex; gap: 4px; }}
            .qa-typing-dots i {{
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: var(--accent-color);
                animation: qa-bounce 1.2s infinite ease-in-out;
            }}
            .qa-typing-dots i:nth-child(2) {{ animation-delay: 0.15s; }}
            .qa-typing-dots i:nth-child(3) {{ animation-delay: 0.30s; }}
            .qa-typing-label {{ font-size: 0.78rem; color: var(--text-secondary); }}

            @keyframes qa-bounce {{
                0%, 80%, 100% {{ opacity: 0.3; transform: translateY(0); }}
                40% {{ opacity: 1; transform: translateY(-3px); }}
            }}

            .qa-empty {{
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                gap: 6px;
                min-height: 380px;
                text-align: center;
            }}
            .qa-empty-title {{
                margin-top: 8px;
                font-size: 1rem;
                font-weight: 600;
                color: var(--text-primary);
            }}
            .qa-empty-sub {{
                max-width: 260px;
                font-size: 0.8rem;
                line-height: 1.5;
                color: var(--text-secondary);
            }}

            /* ===== Chat Input ===== */
            div[data-testid="stChatInputContainer"],
            div[data-testid="stChatInputContainer"] > div,
            div[data-testid="stChatInput"],
            div[data-testid="stChatInput"] > div,
            div[data-testid="stChatInput"] > div > div {{
                background-color: var(--bg-secondary) !important;
                border-color: var(--border-color) !important;
                border-radius: 16px !important;
            }}

            div[data-testid="stChatInput"] textarea {{
                background-color: transparent !important;
                color: var(--text-primary) !important;
                -webkit-text-fill-color: var(--text-primary) !important;
                font-family: var(--font-primary) !important;
            }}

            div[data-testid="stChatInputContainer"]:focus-within,
            div[data-testid="stChatInput"]:focus-within {{
                border-color: var(--accent-blue) !important;
                box-shadow: 0 0 10px rgba(59, 130, 246, 0.20) !important;
            }}

            div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:enabled {{
                background-color: var(--accent-blue) !important;
                border: 1px solid var(--accent-blue) !important;
                color: #FFFFFF !important;
                box-shadow: none !important;
                transition: all 0.2s ease !important;
            }}

            div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:enabled svg {{
                color: #FFFFFF !important;
            }}

            div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:enabled:hover {{
                filter: brightness(1.1);
            }}

            div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]:enabled:active {{
                transform: scale(0.96);
            }}

            div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] {{
                border-radius: 10px !important;
            }}

            /* ===== Theme Toggle ===== */
            div[data-testid="stCheckbox"]:has(input[aria-label="Theme Toggle"]) {{
                display: flex !important;
                justify-content: flex-end !important;
                padding-top: 4px !important;
            }}

            div[data-testid="stCheckbox"]:has(input[aria-label="Theme Toggle"]) div[data-testid="stWidgetLabel"] {{
                display: none !important;
            }}

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

            span:has(input[aria-label="Theme Toggle"]) + div > div {{
                background-color: #FFFFFF !important;
                width: 22px !important;
                height: 22px !important;
                border-radius: 50% !important;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                position: relative !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            }}

            span:has(input[aria-label="Theme Toggle"]) + div > div::after {{
                content: "" !important;
                position: absolute !important;
                width: 14px !important;
                height: 14px !important;
                background-repeat: no-repeat !important;
                background-position: center !important;
                background-size: contain !important;
            }}

            span:has(input[aria-label="Theme Toggle"]:not(:checked)) + div > div::after {{
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23F59E0B' stroke-width='2.2' stroke-linecap='round'%3E%3Ccircle cx='12' cy='12' r='4.2' fill='%23F59E0B'/%3E%3Cpath d='M12 2.5v2.3M12 19.2v2.3M2.5 12h2.3M19.2 12h2.3M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6'/%3E%3C/svg%3E") !important;
            }}

            span:has(input[aria-label="Theme Toggle"]:checked) + div > div {{
                background-color: #1E293B !important;
                border: 1px solid rgba(255, 255, 255, 0.15) !important;
                transform: translateX(24px) !important;
            }}

            span:has(input[aria-label="Theme Toggle"]:checked) + div > div::after {{
                background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z' fill='%23E2E8F0'/%3E%3C/svg%3E") !important;
            }}

            /* ===== Quant Analyst Header ===== */
            .assistant-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                width: 100%;
                padding: 2px 0 8px 0;
                margin: 0 0 8px 0;
                border-bottom: 1px solid var(--border-color);
                box-sizing: border-box;
            }}

            .assistant-header-main {{
                display: flex;
                align-items: center;
                gap: 11px;
                min-width: 0;
            }}

            .assistant-header-icon {{
                box-sizing: border-box;
                width: 42px;
                height: 42px;
                min-width: 42px;
                border-radius: 11px;
                border: 1px solid var(--avatar-border);
                background-color: var(--avatar-bg);
                background-image: url("{avatar_uri}");
                background-position: center;
                background-repeat: no-repeat;
                background-size: 66% 66%;
            }}

            .assistant-header-copy {{
                display: flex;
                flex-direction: column;
                gap: 3px;
                min-width: 0;
            }}

            .assistant-header-title {{
                color: var(--text-primary);
                font-family: var(--font-primary) !important;
                font-size: 1.08rem;
                font-weight: 600;
                line-height: 1.2;
                letter-spacing: -0.025em;
                white-space: nowrap;
            }}

            .assistant-header-subtitle {{
                color: var(--text-secondary);
                font-family: var(--font-primary) !important;
                font-size: 0.56rem;
                font-weight: 600;
                line-height: 1.3;
                letter-spacing: 0.085em;
                white-space: nowrap;
            }}

            .assistant-header-status {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                flex-shrink: 0;
                padding: 5px 8px;
                border: 1px solid rgba(38, 166, 154, 0.22);
                border-radius: 999px;
                background: rgba(38, 166, 154, 0.10);
                color: var(--positive-color);
                font-family: var(--font-primary) !important;
                font-size: 0.58rem;
                font-weight: 600;
                letter-spacing: 0.06em;
                line-height: 1;
            }}

            .assistant-header-status-dot {{
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: var(--positive-color);
                box-shadow: 0 0 7px rgba(38, 166, 154, 0.48);
                animation: pulse-green 2s infinite;
            }}

            @media (max-width: 1100px) {{
                .assistant-header-status {{ display: none; }}
                .assistant-header-subtitle {{ font-size: 0.52rem; }}
            }}
            /* ===== Loading Skeletons ===== */
            @keyframes qa-shimmer {{
                0% {{ background-position: 200% 0; }}
                100% {{ background-position: -200% 0; }}
            }}

            .qa-skel {{
                display: inline-block;
                vertical-align: middle;
                border-radius: 6px;
                background: linear-gradient(
                    90deg,
                    var(--skeleton-base) 25%,
                    var(--skeleton-highlight) 50%,
                    var(--skeleton-base) 75%
                );
                background-size: 200% 100%;
                animation: qa-shimmer 1.5s ease-in-out infinite;
            }}

            .qa-skel-label {{ width: 58px; height: 9px; }}
            .qa-skel-value {{ width: 112px; height: 17px; }}

            .qa-chart-skel {{
                box-sizing: border-box;
                display: flex;
                flex-direction: column;
                width: 100%;
                padding: 16px 18px;
                border: 1px solid var(--border-color);
                border-radius: 10px;
                background: var(--bg-card);
            }}
            .qa-chart-skel .qa-skel-title {{ width: 150px; height: 14px; margin-bottom: 14px; }}
            .qa-chart-skel .qa-skel-plot {{ display: block; flex: 1; width: 100%; border-radius: 8px; }}

            @media (prefers-reduced-motion: reduce) {{
                .qa-skel {{ animation: none; }}
            }}

            /* ===== Global Footer (Disclaimer) ===== */
            hr.footer-divider {{
                border: none !important;
                border-top: 1px solid var(--border-color) !important;
                margin: 24px 0 12px 0 !important;
                opacity: 0.25 !important;
            }}

            .footer-disclaimer {{
                font-family: var(--font-primary) !important;
                font-size: 0.70rem !important;
                color: var(--text-secondary) !important;
                text-align: center !important;
                line-height: 1.5 !important;
                margin-bottom: 16px !important;
                padding: 0 12% !important;
                opacity: 0.70 !important;
            }}

            .footer-disclaimer strong {{
                color: var(--text-secondary) !important;
                font-weight: 600 !important;
            }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)

    # ----- branding -----
    @staticmethod
    @lru_cache(maxsize=4)
    def _encode_image(path: str) -> str:
        return base64.b64encode(Path(path).read_bytes()).decode("ascii")

    def _assistant_avatar_uri(self, assets_dir: str = "assets") -> str:
        """Data URI of the QuantAgent mark used as the assistant avatar."""
        path = f"{assets_dir}/{self.ASSISTANT_ICON_FILE}"
        try:
            return f"data:image/png;base64,{self._encode_image(path)}"
        except OSError:
            return self.ASSISTANT_ICON_FALLBACK

    def render_logo(self, width: int = 260, assets_dir: str = "assets") -> None:
        """Render the theme-matched logo as a raw <img>.

        Using HTML (instead of st.image) lets the browser downscale the
        high-resolution file itself, so the logo stays sharp on retina screens.
        """
        path = f"{assets_dir}/quantagent_logo_{self.current_theme_name}.png"
        encoded = self._encode_image(path)
        st.markdown(
            f'<img src="data:image/png;base64,{encoded}" alt="QuantAgent" '
            f'style="width:{width}px; height:auto; display:block;">',
            unsafe_allow_html=True,
        )

    # ----- chat -----
    def create_chat_container(self) -> Any:
        """Scrollable chat panel. Its border is drawn by our own CSS so it
        follows the active theme (fixes the divider vanishing in light mode)."""
        return st.container(
            height=self.CHAT_PANEL_HEIGHT,
            border=False,
            gap="small",
            autoscroll=True,
            key=self.CHAT_PANEL_KEY,
        )

    def render_chat_message(self, role: str, content: str) -> None:
        st.markdown(
            self._chat_renderer.message_html(role, content), unsafe_allow_html=True
        )

    def chat_message_html(self, role: str, content: str) -> str:
        return self._chat_renderer.message_html(role, content)

    def typing_indicator_html(self) -> str:
        return self._chat_renderer.typing_html()

    def empty_state_html(self) -> str:
        return self._chat_renderer.empty_state_html()

    def render_assistant_header(self) -> None:
        """Render the theme-aware Quant Analyst header above the chat panel."""
        html_block = """
        <div class="assistant-header">
            <div class="assistant-header-main">
                <div class="assistant-header-icon" aria-hidden="true"></div>
                <div class="assistant-header-copy">
                    <div class="assistant-header-title">Quant Analyst</div>
                    <div class="assistant-header-subtitle">
                        AI-POWERED MARKET INTELLIGENCE
                    </div>
                </div>
            </div>
            <div class="assistant-header-status">
                <span class="assistant-header-status-dot"></span>
                ONLINE
            </div>
        </div>
        """
        st.markdown(html_block, unsafe_allow_html=True)

    # ----- terminal components -----
    def render_market_status(self) -> None:
        """Render a US market-hours indicator using Eastern Time."""
        eastern = pytz.timezone("US/Eastern")
        now = datetime.now(eastern)

        is_open = False
        if now.weekday() < 5:
            market_start = now.replace(hour=9, minute=30, second=0, microsecond=0)
            market_end = now.replace(hour=16, minute=0, second=0, microsecond=0)
            is_open = market_start <= now <= market_end

        status_text = "MARKET LIVE" if is_open else "MARKET CLOSED"
        dot_class = "open" if is_open else "closed"

        html_block = f"""
        <div class="market-status">
            <span class="status-dot {dot_class}"></span>
            <span>{status_text}</span>
        </div>
        """
        st.markdown(html_block, unsafe_allow_html=True)

    def create_main_layout(self) -> Tuple[Any, Any]:
        """Create the main trading and chat columns."""
        return st.columns([7, 3], gap="medium")

    def floating_metrics_html(self, market_summary: Dict[str, Any]) -> str:
        """HTML for the market summary cards."""
        price = market_summary.get("latest_price", "N/A")
        vwap = market_summary.get("vwap", "N/A")
        rsi = market_summary.get("rsi_14", "N/A")
        atr = market_summary.get("atr_14", market_summary.get("atr", "N/A"))

        def fmt(value: Any, suffix: str = "") -> str:
            try:
                return f"{float(value):,.2f}{suffix}"
            except (ValueError, TypeError):
                return "N/A"

        return f"""
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

    def render_floating_metrics(self, market_summary: Dict[str, Any]) -> None:
        """Render the market summary cards."""
        st.markdown(self.floating_metrics_html(market_summary), unsafe_allow_html=True)

    # ----- loading skeletons -----
    def metrics_skeleton_html(self) -> str:
        """Placeholder cards with the same geometry as the real metric cards."""
        card = (
            '<div class="metric-card">'
            '<div class="metric-label"><span class="qa-skel qa-skel-label"></span></div>'
            '<div class="metric-value"><span class="qa-skel qa-skel-value"></span></div>'
            "</div>"
        )
        return f'<div class="floating-metrics-container">{card * 4}</div>'

    def chart_skeleton_html(self, height: int = 450) -> str:
        """Placeholder block that reserves the chart's space while data loads."""
        return (
            f'<div class="qa-chart-skel" style="height:{int(height)}px;">'
            '<span class="qa-skel qa-skel-title"></span>'
            '<span class="qa-skel qa-skel-plot"></span>'
            "</div>"
        )
