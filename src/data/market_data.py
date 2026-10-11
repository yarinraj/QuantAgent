import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any

class MarketDataEngine:
    """
    Data Engine for fetching real-time market data from Yahoo Finance
    and computing technical indicators using Pandas & NumPy.
    """

    @staticmethod
    def fetch_historical_data(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """
        Fetches historical daily price data for a given stock symbol.
        """
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            raise ValueError(f"No market data retrieved for symbol '{symbol}'. Check symbol validity.")
            
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]

    @staticmethod
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates key technical indicators:
        - SMA_20: Simple Moving Average (20 days)
        - SMA_50: Simple Moving Average (50 days)
        - RSI_14: Relative Strength Index (14 days)
        - Volatility: Annualized Standard Deviation of daily returns
        """
        df = df.copy()

        # 1. Simple Moving Averages (SMA)
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()

        # 2. Daily Returns & Annualized Volatility
        df['Daily_Return'] = df['Close'].pct_change()
        # 252 trading days in a standard calendar year
        df['Volatility_20d'] = df['Daily_Return'].rolling(window=20).std() * np.sqrt(252)

        # 3. Relative Strength Index (RSI_14)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()

        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        return df

    def get_market_summary(self, symbol: str) -> Dict[str, Any]:
        """
        Returns a structured summary dictionary of the latest stock metrics
        ready to be passed to the Risk Engine or AI Agent.
        """
        raw_df = self.fetch_historical_data(symbol)
        df = self.add_technical_indicators(raw_df)
        
        latest = df.iloc[-1]
        prev_close = df.iloc[-2]['Close']

        daily_change_pct = ((latest['Close'] - prev_close) / prev_close) * 100

        return {
            "symbol": symbol.upper(),
            "latest_price": round(float(latest['Close']), 2),
            "daily_change_pct": round(float(daily_change_pct), 2),
            "sma_20": round(float(latest['SMA_20']), 2),
            "sma_50": round(float(latest['SMA_50']), 2),
            "rsi_14": round(float(latest['RSI_14']), 2),
            "annualized_volatility": round(float(latest['Volatility_20d']), 2) if not np.isnan(latest['Volatility_20d']) else 0.0,
            "52w_high": round(float(df['High'].max()), 2),
            "52w_low": round(float(df['Low'].min()), 2),
            "volume": int(latest['Volume'])
        }


if __name__ == "__main__":
    # Test execution with real market data
    engine = MarketDataEngine()
    test_symbol = "NVDA"
    
    print(f"Fetching real market data for '{test_symbol}'...")
    summary = engine.get_market_summary(test_symbol)
    
    print("\n--- Market Data Summary ---")
    for key, value in summary.items():
        print(f"{key:<22}: {value}")