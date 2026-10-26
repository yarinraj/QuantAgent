import numpy as np
import pandas as pd

class RiskEngine:
    """
    Quantitative Risk Engine.
    Evaluates market data and portfolio metrics against strict trading guardrails.
    """
    def __init__(self):
        # Risk Limits (Guardrails)
        self.max_allocation_limit = 0.25  # Max 25% of portfolio in one trade
        self.max_drawdown_limit = -0.15   # Reject if current drawdown is worse than -15%
        self.min_sharpe_ratio = 0.5       # Reject if Sharpe is too low
        self.max_rsi_limit = 70.0         # Reject if RSI is in extreme overbought territory

    def evaluate_risk_guardrails(self, market_summary: dict, price_series: pd.Series, daily_returns: pd.Series, proposed_trade_value: float, total_portfolio_value: float) -> dict:
        violations = []

        # 1. Position Sizing / Allocation Check
        allocation = proposed_trade_value / total_portfolio_value
        if allocation > self.max_allocation_limit:
            violations.append(f"Position size too large: {allocation*100:.1f}% exceeds the {self.max_allocation_limit*100:.1f}% portfolio limit.")

        # 2. Drawdown Check
        rolling_max = price_series.cummax()
        drawdowns = (price_series - rolling_max) / rolling_max
        current_drawdown = drawdowns.iloc[-1] if not drawdowns.empty else 0
        if current_drawdown < self.max_drawdown_limit:
            violations.append(f"Severe Drawdown: Stock is down {current_drawdown*100:.1f}%, exceeding the {self.max_drawdown_limit*100:.1f}% limit.")

        # 3. Sharpe Ratio Check (Annualized)
        mean_return = daily_returns.mean()
        std_return = daily_returns.std()
        sharpe = 0
        if std_return > 0:
            sharpe = (mean_return / std_return) * np.sqrt(252)
        
        if sharpe < self.min_sharpe_ratio:
            violations.append(f"Poor Risk-Adjusted Return: Sharpe ratio ({sharpe:.2f}) is below the {self.min_sharpe_ratio} minimum.")

        # 4. RSI Overbought Check
        try:
            rsi = float(market_summary.get("rsi_14", 50))
        except (ValueError, TypeError):
            rsi = 50

        if rsi > self.max_rsi_limit:
            violations.append(f"Overbought Warning: RSI is {rsi:.1f} (Above {self.max_rsi_limit}). High risk of pullback.")

        # Final Verdict
        status = "REJECTED" if violations else "APPROVED"

        return {
            "status": status,
            "is_approved": len(violations) == 0,
            "violations": violations,
            "metrics": {
                "proposed_allocation": f"{allocation*100:.1f}%",
                "current_drawdown": f"{current_drawdown*100:.1f}%",
                "sharpe_ratio": f"{sharpe:.2f}",
                "rsi_14": f"{rsi:.1f}"
            }
        }