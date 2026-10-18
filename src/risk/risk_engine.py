import numpy as np
import pandas as pd
from typing import Dict, Any, List

class RiskEngine:
    """
    Intraday Risk Engine responsible for calculating risk metrics
    and enforcing strict risk guardrails for Day Trading.
    """

    def __init__(self, risk_free_rate: float = 0.0, max_allowed_mdd: float = 0.05, max_rsi_buy: float = 75.0, max_vwap_distance: float = 0.03):
        # Adjusted parameters for Day Trading
        self.risk_free_rate = risk_free_rate  # Effectively 0% for intraday holds
        self.max_allowed_mdd = max_allowed_mdd  # Stricter: 5% max intraday drawdown
        self.max_rsi_buy = max_rsi_buy
        self.max_vwap_distance = max_vwap_distance  # Max 3% deviation from VWAP

    def calculate_intraday_sharpe(self, returns_series: pd.Series) -> float:
        """
        Calculates an unannualized Intraday Sharpe Ratio (Momentum quality).
        """
        clean_returns = returns_series.dropna()
        if clean_returns.empty or clean_returns.std() == 0:
            return 0.0
        
        # Simple Intraday Reward-to-Risk ratio
        sharpe = (clean_returns.mean() - self.risk_free_rate) / clean_returns.std()
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
        Evaluates a proposed BUY recommendation against strict Intraday risk guardrails.
        """
        violations: List[str] = []
        
        # 1. Compute quantitative risk metrics
        mdd = self.calculate_max_drawdown(price_series)
        sharpe = self.calculate_intraday_sharpe(daily_returns)
        rsi = market_summary.get("rsi_14", 50.0)
        latest_price = market_summary.get("latest_price", 0.0)
        vwap = market_summary.get("vwap", latest_price)

        # 2. Guardrail Rule 1: Intraday Max Drawdown Limit
        if mdd > self.max_allowed_mdd:
            violations.append(f"Intraday Max Drawdown ({mdd * 100:.1f}%) exceeds safety limit ({self.max_allowed_mdd * 100:.1f}%).")

        # 3. Guardrail Rule 2: Overbought RSI Limit
        if rsi > self.max_rsi_buy:
            violations.append(f"Intraday RSI ({rsi}) indicates overbought territory (> {self.max_rsi_buy}).")

        # 4. Guardrail Rule 3: Single Position Allocation Limit
        if total_portfolio_value > 0:
            allocation_pct = proposed_trade_value / total_portfolio_value
            if allocation_pct > 0.25:
                violations.append(f"Trade allocation ({allocation_pct * 100:.1f}%) exceeds max position cap (25.0%).")

        # 5. Guardrail Rule 4: VWAP Over-Extension (New Day Trading Rule)
        if vwap > 0:
            vwap_distance = abs(latest_price - vwap) / vwap
            if vwap_distance > self.max_vwap_distance:
                violations.append(f"Price is over-extended from VWAP by {vwap_distance * 100:.1f}% (Limit: {self.max_vwap_distance * 100:.1f}%). High reversion risk.")

        # 6. Guardrail Rule 5: Negative Sharpe Ratio Check
        if sharpe < 0:
            violations.append(f"Intraday Sharpe Ratio ({sharpe}) is negative, showing poor risk-adjusted momentum.")

        is_approved = len(violations) == 0

        return {
            "status": "APPROVED" if is_approved else "REJECTED",
            "is_approved": is_approved,
            "metrics": {
                "intraday_sharpe": sharpe,
                "max_drawdown_pct": round(mdd * 100, 2),
                "rsi_14": rsi,
                "vwap_distance_pct": round(abs(latest_price - vwap) / vwap * 100, 2) if vwap > 0 else 0.0
            },
            "violations": violations
        }

if __name__ == "__main__":
    # Test Risk Engine with real intraday data from MarketDataEngine
    from src.data.market_data import MarketDataEngine

    data_engine = MarketDataEngine()
    test_symbol = "NVDA"

    print(f"Fetching intraday market data and running Risk Engine for '{test_symbol}'...")
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

    print("\n--- Intraday Risk Guardrails Evaluation Result ---")
    print(f"Status  : {evaluation['status']}")
    print(f"Metrics : {evaluation['metrics']}")
    if evaluation['violations']:
        print("\nRisk Violations Detected:")
        for v in evaluation['violations']:
            print(f"  - {v}")
    else:
        print("\nNo risk violations detected. Trade is APPROVED.")