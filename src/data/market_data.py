import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any

class MarketDataEngine:
    def fetch_historical_data(self, symbol: str, period: str = "5d", interval: str = "5m") -> pd.DataFrame:
        """
        Fetches intraday price data from Yahoo Finance safely.
        Default is 5 days of 5-minute candles for Day Trading analysis.
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
        Calculates SMA, RSI, VWAP, and ATR on intraday historical data.
        """
        if df.empty or len(df) < 20:
            return df

        df = df.copy()
        df['Daily_Return'] = df['Close'].pct_change()
        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()

        # RSI (14 periods)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # --- DAY TRADING INDICATORS ---
        
        # 1. VWAP (Volume Weighted Average Price)
        # מחיר ממוצע משוקלל נפח שמתאפס בתחילת כל יום מסחר
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        df['VWAP'] = (df['Typical_Price'] * df['Volume']).groupby(df.index.date).cumsum() / df['Volume'].groupby(df.index.date).cumsum()

        # 2. ATR (Average True Range - 14 periods)
        # מדד תנודתיות שמשמש לקביעת מרחק ה-Stop-Loss הדינמי
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR_14'] = true_range.rolling(14).mean()

        return df

    def get_market_summary(self, symbol: str) -> dict:
        """
        Returns a structured summary dictionary of the latest intraday stock metrics.
        """
        try:
            raw_df = self.fetch_historical_data(symbol)
            
            if raw_df.empty:
                return {"error": f"No market data retrieved for symbol '{symbol}'. Symbol may be invalid or unavailable."}
            
            df = self.add_technical_indicators(raw_df)
            
            if len(df) < 2:
                return {"error": f"Insufficient historical data available for symbol '{symbol}'."}

            latest = df.iloc[-1]
            
            latest_date = df.index[-1].date()
            today_data = df[df.index.date == latest_date]
            if not today_data.empty:
                today_open = today_data.iloc[0]['Open']
                intraday_change_pct = ((latest['Close'] - today_open) / today_open) * 100
            else:
                intraday_change_pct = 0.0

            return {
                "symbol": symbol.upper(),
                "latest_price": round(float(latest['Close']), 2),
                "intraday_change_pct": round(float(intraday_change_pct), 2),
                "vwap": round(float(latest['VWAP']), 2) if not np.isnan(latest.get('VWAP', float('nan'))) else round(float(latest['Close']), 2),
                "atr_14": round(float(latest['ATR_14']), 2) if not np.isnan(latest.get('ATR_14', float('nan'))) else 0.0,
                "sma_20": round(float(latest['SMA_20']), 2) if not np.isnan(latest.get('SMA_20', float('nan'))) else 0.0,
                "sma_50": round(float(latest['SMA_50']), 2) if not np.isnan(latest.get('SMA_50', float('nan'))) else 0.0,
                "rsi_14": round(float(latest['RSI_14']), 2) if not np.isnan(latest.get('RSI_14', float('nan'))) else 50.0,
                "volume": int(latest['Volume'])
            }
            
        except Exception as e:
            return {"error": f"Could not retrieve data for '{symbol}'. Details: {str(e)}"}