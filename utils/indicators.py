import pandas as pd
import ta

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算常用的技术指标
    Args:
        df: 包含 open, high, low, close, volume 的 DataFrame
    Returns:
        包含指标的新 DataFrame
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    # 确保是按照日期升序
    df = df.sort_values('date')
    
    # 移动平均线 MA
    df['MA5'] = ta.trend.sma_indicator(df['close'], window=5)
    df['MA20'] = ta.trend.sma_indicator(df['close'], window=20)
    
    # RSI
    df['RSI'] = ta.momentum.rsi(df['close'], window=14)
    
    # MACD
    macd = ta.trend.MACD(df['close'])
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['MACD_diff'] = macd.macd_diff()
    
    # KDJ (Stochastic Oscillator)
    # ta 库中 stoch 是 K, stoch_signal 是 D
    stoch = ta.momentum.StochasticOscillator(df['high'], df['low'], df['close'], window=9, smooth_window=3)
    df['K'] = stoch.stoch()
    df['D'] = stoch.stoch_signal()
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    return df

def get_latest_indicators(df: pd.DataFrame) -> dict:
    """
    获取最近一天的指标摘要
    """
    if df.empty:
        return {}
        
    latest = df.iloc[-1]
    return {
        "date": latest['date'],
        "close": latest['close'],
        "volume": latest['volume'],
        "MA5": latest.get('MA5'),
        "MA20": latest.get('MA20'),
        "RSI": latest.get('RSI'),
        "MACD": latest.get('MACD_diff')
    }
