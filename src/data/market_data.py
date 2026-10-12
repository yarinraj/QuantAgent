import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any

class MarketDataEngine:
    def fetch_historical_data(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """
        Fetches historical price data from Yahoo Finance safely.
        """
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            
            if df is None or df.empty or 'Close' not in df.columns:
                return pd.DataFrame()  
                
            return df
        except Exception:
            return pd.DataFrame()

    def add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates SMA, RSI, and Volatility indicators on historical data.
        """
        if df.empty or len(df) < 20:
            return df

        df = df.copy()
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()

        # RSI (14)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # Volatility (20-day annualized)
        df['Daily_Return'] = df['Close'].pct_change()
        df['Volatility_20d'] = df['Daily_Return'].rolling(window=20).std() * np.sqrt(252)

        return df

    def get_market_summary(self, symbol: str) -> dict:
        """
        Returns a structured summary dictionary of the latest stock metrics.
        """
        try:
            raw_df = self.fetch_historical_data(symbol)
            
            if raw_df.empty:
                return {"error": f"No market data retrieved for symbol '{symbol}'. Symbol may be invalid or unavailable."}
            
            df = self.add_technical_indicators(raw_df)
            
            if len(df) < 2:
                return {"error": f"Insufficient historical data available for symbol '{symbol}'."}

            latest = df.iloc[-1]
            prev_close = df.iloc[-2]['Close']
            daily_change_pct = ((latest['Close'] - prev_close) / prev_close) * 100

            return {
                "symbol": symbol.upper(),
                "latest_price": round(float(latest['Close']), 2),
                "daily_change_pct": round(float(daily_change_pct), 2),
                "sma_20": round(float(latest['SMA_20']), 2) if not np.isnan(latest.get('SMA_20', float('nan'))) else 0.0,
                "sma_50": round(float(latest['SMA_50']), 2) if not np.isnan(latest.get('SMA_50', float('nan'))) else 0.0,
                "rsi_14": round(float(latest['RSI_14']), 2) if not np.isnan(latest.get('RSI_14', float('nan'))) else 50.0,
                "annualized_volatility": round(float(latest['Volatility_20d']), 2) if not np.isnan(latest.get('Volatility_20d', float('nan'))) else 0.0,
                "52w_high": round(float(df['High'].max()), 2),
                "52w_low": round(float(df['Low'].min()), 2),
                "volume": int(latest['Volume'])
            }
            
        except Exception as e:
            return {"error": f"Could not retrieve data for '{symbol}'. Details: {str(e)}"}