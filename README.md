# QuantAgent - Autonomous Portfolio & Risk Manager

`QuantAgent` is an autonomous AI-driven portfolio management and market analysis system built in Python. It combines real-time market data retrieval, quantitative risk guardrails, and a ReAct-based AI Advisor agent to provide safe, data-backed investment recommendations.

---

## Key Features

- **Live Market Data Engine**: Fetches real-time stock prices and computes technical indicators ($SMA_{20}$, $SMA_{50}$, $RSI_{14}$, Annualized Volatility) using `Pandas` and `yfinance`.
- **Deterministic Risk Engine**: Calculates risk-adjusted metrics ($Sharpe\ Ratio$, $Max\ Drawdown$) and enforces strict risk guardrails before any recommendation is approved.
- **ReAct AI Advisor Agent**: An LLM agent operating in a reasoning loop (Reason + Act) using Groq API (`Llama-3.3-70B`) to analyze market opportunities.
- **Interactive Web Dashboard**: Streamlit-powered UI presenting real-time charts, portfolio status, risk metrics, and full AI reasoning traces.

---

## Architecture Overview

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      Interactive Web App (Streamlit)                   │
│   - Stock Selector & Portfolio Input  │ - Real-time Charts & RSI       │
│   - Risk Metrics Dashboard            │ - AI Agent Thought Process Log │
└───────────────────┬────────────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     1. Data Engine (Pandas & yfinance)                 │
│   Pulls live stock data, calculates SMA_20, SMA_50, RSI_14, Volatility│
└───────────────────┬────────────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    2. Risk Engine (Deterministic Guardrails)           │
│   Computes Sharpe Ratio, Max Drawdown (MDD) & Enforces Risk Rules      │
└───────────────────┬────────────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      3. AI Advisor Agent (ReAct Loop)                  │
│   Evaluates market summary, runs ReAct reasoning, outputs recommendation│
└────────────────────────────────────────────────────────────────────────┘
```
## Project Structure:
quant-agent/
├── src/
│   ├── data/
│   │   └── market_data.py   # Live market data & technical indicators
│   ├── risk/
│   │   └── risk_engine.py   # Sharpe ratio, Max Drawdown & Risk Guardrails
│   ├── agent/
│   │   └── core.py          # ReAct Agent loop & Groq API integration
│   └── app.py               # Streamlit web dashboard
├── requirements.txt
├── .gitignore
└── README.md