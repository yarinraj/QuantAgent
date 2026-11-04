# QuantAgent

**An AI-powered quantitative risk co-pilot and trading analytics dashboard**, built with Python, Streamlit and a Groq-hosted LLM.

QuantAgent pairs a live market terminal with a conversational advisor. You search a ticker, watch the intraday chart and key indicators, and ask the co-pilot whether a trade makes sense. The LLM never gets the final word on risk: every trade is checked by a **deterministic risk engine**, and the agent is instructed to report its verdict as-is.

> **Educational project.** QuantAgent is not a licensed financial advisor and does not provide investment advice. See the [disclaimer](#disclaimer).

---

## Features

- **Live trading terminal**: ticker search (Yahoo Finance), 5-minute candlestick chart over the last two days, and metric cards for latest price, VWAP, RSI(14) and ATR(14).
- **Deterministic risk guardrails**: every proposed trade is evaluated by plain Python rules, not by the LLM (see [Risk guardrails](#risk-guardrails)).
- **Tool-calling AI advisor**: an LLM agent on the Groq API (OpenAI-compatible) that can fetch market summaries and run the risk engine inside a reasoning loop of up to 5 iterations.
- **Chat that stays in context**: the last 15 messages of the current session are sent to the model, replies follow the language the user writes in, and trade verdicts always lead with a bold **APPROVED** or **REJECTED**.
- **Polished UI**: light and dark themes, theme-aware chat bubbles with safe markdown rendering, loading skeletons for the metrics and chart, and a market-open/closed indicator (US Eastern time).

---

## Architecture

```text
┌───────────────────────────────────────────────────────────────────┐
│                  Streamlit app  (app.py)                          │
│   QuantAgentApp ── UIManager ── ChatMessageRenderer ── charts     │
│   Terminal (search, metrics, chart)  │  Chat co-pilot             │
└───────────────┬───────────────────────────────┬───────────────────┘
                │                               │ user prompt + history
                ▼                               ▼
┌─────────────────────────────┐   ┌─────────────────────────────────┐
│  MarketDataEngine           │◄──│  QuantAgent  (agent/core.py)    │
│  yfinance + pandas          │   │  Groq LLM, tool-calling loop    │
│  SMA, RSI, VWAP, ATR        │   │  tools: get_market_summary,     │
└─────────────────────────────┘   │         evaluate_risk_guardrails│
                ▲                 └───────────────┬─────────────────┘
                │                                 │
                │                                 ▼
                │                 ┌─────────────────────────────────┐
                └─────────────────│  RiskEngine  (deterministic)    │
                                  │  allocation, drawdown, Sharpe,  │
                                  │  RSI checks → APPROVED/REJECTED │
                                  └─────────────────────────────────┘
```

**Design notes**

- `QuantAgentApp` (in `app.py`) owns page composition: header, trading terminal and chat. Data loading is cached for 60 seconds, so chat messages and theme toggles do not refetch market data.
- `UIManager` owns themes, CSS injection and reusable components (logo, metric cards, skeletons, chat container).
- `ChatMessageRenderer` converts LLM markdown into escaped, single-block HTML. All text is escaped before a small markdown subset is applied.
- The LLM can *call* the risk engine but cannot override it: the system prompt forbids changing a `REJECTED` verdict.

---

## Risk guardrails

A trade is **APPROVED** only if it passes all of these checks. Otherwise it is **REJECTED** and the violations are reported.

| Check | Rule |
| --- | --- |
| Position size | Trade value must be at most **25%** of portfolio cash |
| Drawdown | Current drawdown must not be worse than **-15%** |
| Sharpe ratio | Annualized Sharpe (`mean / std * sqrt(252)`) must be at least **0.5** |
| RSI(14) | Must not be above **70** (overbought) |

The limits live in `src/risk/risk_engine.py` and can be changed there.

---

## Project structure

```text
QuantAgent/
├── app.py                    # Streamlit entry point (QuantAgentApp)
├── requirements.txt
├── .env.example              # copy to .env and add your key
├── .streamlit/
│   └── config.toml           # base theme settings
├── assets/                   # logos, assistant icon, favicon
├── src/
│   ├── agent/core.py         # QuantAgent: Groq client, tools, reasoning loop
│   ├── data/market_data.py   # MarketDataEngine: yfinance + indicators
│   ├── risk/risk_engine.py   # RiskEngine: deterministic guardrails
│   └── UI/
│       ├── UI_manager.py     # UIManager + ChatMessageRenderer
│       └── charts.py         # theme-aware Plotly candlestick chart
└── test_groq.py              # optional: verify your Groq key and models
```

---

## Getting started

**Requirements:** Python 3.10+ and a free [Groq API key](https://console.groq.com/).

```bash
# 1. Clone
git clone https://github.com/yarinraj/QuantAgent.git
cd QuantAgent

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env            # then edit .env and set GROQ_API_KEY

# 5. Run
streamlit run app.py
```

The app opens at `http://localhost:8501`.

To check that your key works and see which models your account can use, run:

```bash
python test_groq.py
```

### Configuration

| Setting | Where | Notes |
| --- | --- | --- |
| `GROQ_API_KEY` | `.env` | Required. Never commit this file. |
| LLM model | `self.model` in `src/agent/core.py` | Any Groq-hosted model that supports tool calling |
| Risk limits | `RiskEngine.__init__` in `src/risk/risk_engine.py` | Allocation, drawdown, Sharpe, RSI |
| Default ticker and cash | constants at the top of `QuantAgentApp` in `app.py` | `NVDA`, 10,000 USD |

---

## Tech stack

Python · [Streamlit](https://streamlit.io/) · [Plotly](https://plotly.com/python/) · pandas / NumPy · [yfinance](https://github.com/ranaroussi/yfinance) · [Groq](https://groq.com/) via the OpenAI Python SDK · `streamlit-searchbox`

---

## Known limitations

- **Chat history is session-only.** Conversations live in the browser session (`st.session_state`): each visitor has their own private chat, nothing is written to disk, and refreshing the page starts a new conversation. Persistent history would require per-user storage (for example a database plus authentication).
- **Market data comes from yfinance**, an unofficial Yahoo Finance wrapper. Data can be delayed, incomplete or temporarily unavailable.
- **Market status is simplified.** The open/closed indicator uses US weekday hours (9:30 to 16:00 Eastern) and does not account for holidays.
- **Risk rules are intentionally simple** and are not a substitute for professional risk management.

---

## Disclaimer

QuantAgent is an educational AI demonstration tool that uses automated language models. AI outputs may contain inaccuracies. It is **not** a licensed financial advisor, does **not** offer investment advice, and assumes **no liability** for financial decisions or trading losses. All trading involves risk.

---

## License

Released under the [MIT License](LICENSE).