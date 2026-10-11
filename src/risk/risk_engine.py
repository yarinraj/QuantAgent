import numpy as np
import pandas as pd
from typing import Dict, Any, List

class RiskEngine:
    """
    Deterministic Risk Engine responsible for calculating risk metrics
    (Sharpe Ratio, Max Drawdown) and enforcing strict risk guardrails.
    """

    def __init__(self, risk_free_rate: float = 0.04, max_allowed_mdd: float = 0.30, max_rsi_buy: float = 75.0):
        self.risk_free_rate = risk_free_rate  # 4% annualized risk-free rate
        self.max_allowed_mdd = max_allowed_mdd  # Max allowed Drawdown threshold (30%)
        self.max_rsi_buy = max_rsi_buy  # Max RSI threshold for BUY recommendations

    def calculate_sharpe_ratio(self, daily_returns: pd.Series) -> float:
        """
        Calculates the annualized Sharpe Ratio.
        Formula: (Mean Annual Return - Risk Free Rate) / Annualized Volatility
        """
        clean_returns = daily_returns.dropna()
        if clean_returns.empty or clean_returns.std() == 0:
            return 0.0
        
        mean_annual_return = clean_returns.mean() * 252
        annual_std = clean_returns.std() * np.sqrt(252)
        
        sharpe = (mean_annual_return - self.risk_free_rate) / annual_std
        return round(float(sharpe), 2)

    def calculate_max_drawdown(self, price_series: pd.Series) -> float:
        """
        Calculates the Maximum Drawdown (MDD) from peak to trough over a price series.
        """
        if price_series.empty:
            return 0.0

        cumulative_max = price_series.cummax()
        drawdown = (price_series - cumulative_max) / cumulative_max
        max_drawdown = abs(float(drawdown.min()))
        return round(max_drawdown, 4)

    def evaluate_risk_guardrails(
        self, 
        market_summary: Dict[str, Any], 
        price_series: pd.Series, 
        daily_returns: pd.Series,
        proposed_trade_value: float,
        total_portfolio_value: float
    ) -> Dict[str, Any]:
        """
        Evaluates a proposed BUY recommendation against strict risk guardrails.
        """
        violations: List[str] = []
        
        # 1. Compute quantitative risk metrics
        mdd = self.calculate_max_drawdown(price_series)
        sharpe = self.calculate_sharpe_ratio(daily_returns)
        rsi = market_summary.get("rsi_14", 50.0)

        # 2. Guardrail Rule 1: Max Drawdown Limit
        if mdd > self.max_allowed_mdd:
            violations.append(f"Max Drawdown ({mdd * 100:.1f}%) exceeds safety limit ({self.max_allowed_mdd * 100:.1f}%).")

        # 3. Guardrail Rule 2: Overbought RSI Limit
        if rsi > self.max_rsi_buy:
            violations.append(f"RSI ({rsi}) indicates overbought territory (> {self.max_rsi_buy}).")

        # 4. Guardrail Rule 3: Single Position Allocation Limit (Max 25% of portfolio)
        if total_portfolio_value > 0:
            allocation_pct = proposed_trade_value / total_portfolio_value
            if allocation_pct > 0.25:
                violations.append(f"Trade allocation ({allocation_pct * 100:.1f}%) exceeds max position cap (25.0%).")

        # 5. Guardrail Rule 4: Negative Sharpe Ratio Check
        if sharpe < 0:
            violations.append(f"Sharpe Ratio ({sharpe}) is negative, showing poor risk-adjusted returns.")

        is_approved = len(violations) == 0

        return {
            "status": "APPROVED" if is_approved else "REJECTED",
            "is_approved": is_approved,
            "metrics": {
                "sharpe_ratio": sharpe,
                "max_drawdown_pct": round(mdd * 100, 2),
                "rsi_14": rsi
            },
            "violations": violations
        }


if __name__ == "__main__":
    # Test Risk Engine with real data from MarketDataEngine
    from src.data.market_data import MarketDataEngine

    data_engine = MarketDataEngine()
    test_symbol = "NVDA"

    print(f"Fetching market data and running Risk Engine for '{test_symbol}'...")
    raw_df = data_engine.fetch_historical_data(test_symbol)
    df = data_engine.add_technical_indicators(raw_df)
    summary = data_engine.get_market_summary(test_symbol)

    risk_engine = RiskEngine()
    
    # Simulate evaluating a $3,000 trade in a $10,000 portfolio
    evaluation = risk_engine.evaluate_risk_guardrails(
        market_summary=summary,
        price_series=df['Close'],
        daily_returns=df['Daily_Return'],
        proposed_trade_value=3000.0,
        total_portfolio_value=10000.0
    )

    print("\n--- Risk Guardrails Evaluation Result ---")
    print(f"Status  : {evaluation['status']}")
    print(f"Metrics : {evaluation['metrics']}")
    if evaluation['violations']:
        print("\nRisk Violations Detected:")
        for v in evaluation['violations']:
            print(f"  - {v}")
    else:
        print("\nNo risk violations detected. Trade is APPROVED.")