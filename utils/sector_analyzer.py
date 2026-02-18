
import pandas as pd
import baostock as bs
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.market_scanner import MarketScanner
from utils.indicators import calculate_technical_indicators
import time
import json
import os

# import akshare as ak # Removed

class SectorAnalyzer:
    def __init__(self):
        self.scanner = MarketScanner()
        # MarketScanner.sector_etfs is {code: name}
        # e.g. "sh512480": "半导体"
        self.etf_map = self.scanner.sector_etfs
        self.cache = {}
        self.cache_expiry = 3600 # 1 hour
        
        # 静态成分股映射 (Fallback for Baostock environment)
        # 由于 Baostock 缺乏实时板块成分股接口，这里维护一个核心成分股列表
        self.static_constituents = {
            # Removed static lists as we use dynamic fetching now
        }

    def get_sector_constituents(self, sector_name):
        """
        Get constituent stocks for a given sector name.
        Returns list of dicts: [{'code': '600xxx', 'name': 'Name'}, ...]
        """
        # 1. Try Baostock Index Constituents (for broad indices)
        if sector_name in ["沪深300", "上证50", "中证500"]:
            return self._get_index_stocks_baostock(sector_name)

        # 2. Dynamic Fetch via ETF Holdings (Data-Driven)
        # Find ETF code for sector name
        # self.etf_map is {code: name}, we need name -> code
        etf_code = None
        for code, name in self.etf_map.items():
            if name == sector_name:
                # Remove prefix (sh/sz) to get 6 digit code
                import re
                match = re.search(r'\d{6}', code)
                if match:
                    etf_code = match.group(0)
                break
        
        if etf_code:
            holdings = self._fetch_etf_holdings_dynamic(etf_code)
            if holdings:
                return [{"code": c, "name": f"Code_{c}"} for c in holdings]

        # 3. Fallback: Static Map (if any left) or Empty
        print(f"Could not fetch constituents for {sector_name}")
        return []

    def _fetch_etf_holdings_dynamic(self, etf_code):
        """
        Fetch top holdings from Eastmoney JS data.
        http://fund.eastmoney.com/pingzhongdata/{code}.js
        """
        import requests
        import re
        
        url = f"http://fund.eastmoney.com/pingzhongdata/{etf_code}.js"
        try:
            # Short timeout to avoid blocking
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                content = response.text
                # var stockCodes=["6882561","6889811",...]
                match = re.search(r'var stockCodes=\[(.*?)\];', content)
                if match:
                    codes_str = match.group(1)
                    raw_codes = [c.strip('"\'') for c in codes_str.split(',')]
                    
                    # Clean codes: "6882561" -> "688256" (Remove last digit which is market ID?)
                    # Actually, Eastmoney fund codes often have a suffix.
                    # 1 = SH, 2 = SZ? No, let's just take the first 6 digits.
                    clean_codes = []
                    for rc in raw_codes:
                        if len(rc) >= 6:
                            clean_codes.append(rc[:6])
                    
                    return clean_codes[:10] # Top 10 holdings
        except Exception as e:
            print(f"Error fetching ETF holdings for {etf_code}: {e}")
            
        return []

    def _get_index_stocks_baostock(self, index_name):
        lg = bs.login()
        # map name to code
        idx_map = {
            "沪深300": "sh.000300",
            "上证50": "sh.000016",
            "中证500": "sh.000905"
        }
        code = idx_map.get(index_name)
        if not code: return []
        
        rs = bs.query_hs300_stocks() if index_name == "沪深300" else \
             bs.query_sz50_stocks() if index_name == "上证50" else \
             bs.query_zz500_stocks() if index_name == "中证500" else None
             
        if not rs: return []
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            # code, code_name
            # Baostock returns sh.600000
            raw_code = row[1]
            name = row[2]
            clean_code = raw_code.split('.')[1]
            data_list.append({"code": clean_code, "name": name})
            
        return data_list[:50] # Limit to top 50 to avoid too many requests

    def _fetch_all_sectors(self):
        """
        Fetch data for all sectors.
        """
        current_time = time.time()
        if self.cache.get('all_sectors_data'):
            data, timestamp = self.cache['all_sectors_data']
            if current_time - timestamp < 600: # 10 minutes cache
                return data

        results = []
        lg = bs.login()
        if lg.error_code != '0':
            print(f"Baostock login failed: {lg.error_msg}")
            return []
            
        try:
            for code, name in self.etf_map.items():
                try:
                    data = self._fetch_etf_performance_baostock(code, name)
                    if data:
                        results.append(data)
                except Exception as e:
                    print(f"Error analyzing ETF {code} ({name}): {e}")
        except Exception as e:
            print(f"Error in _fetch_all_sectors: {e}")
        # Do not logout here as it breaks the global session for other components
        
        self.cache['all_sectors_data'] = (results, current_time)
        return results

    def get_top_sectors_performance(self, period_days=14, limit=5):
        """
        Get top performing sectors over the last period_days (using ETF proxies).
        Returns a list of dicts with sector name, etf code, change, and technical indicators.
        """
        results = self._fetch_all_sectors()
        
        # Sort by pct_change descending
        results.sort(key=lambda x: x['pct_change'], reverse=True)
        return results[:limit]

    def get_sector_ranking_by_days(self, days=14, top_n=5):
        """
        Rank sectors by number of days they were in the top N gainers in the last 'days'.
        Returns list of (sector_name, count).
        """
        # Check cache for ranking result
        cache_key = f"ranking_{days}_{top_n}"
        current_time = time.time()
        if self.cache.get(cache_key):
            data, timestamp = self.cache[cache_key]
            # Use same expiry as data cache (or slightly shorter/longer)
            if current_time - timestamp < 600: 
                return data

        all_data = self._fetch_all_sectors()
        
        # Organize data by date
        # date_map: { "2023-10-01": [ {sector: "A", pct: 1.2}, ... ] }
        date_map = {}
        
        for sector_data in all_data:
            kline = sector_data['kline_data'] # list of dicts with date, close
            
            # Need at least 2 days to calculate change
            if len(kline) < 2:
                continue
                
            for i in range(1, len(kline)):
                curr = kline[i]
                prev = kline[i-1]
                date = curr['date']
                
                if prev['close'] == 0:
                    change = 0
                else:
                    change = (curr['close'] - prev['close']) / prev['close'] * 100
                
                if date not in date_map:
                    date_map[date] = []
                date_map[date].append({
                    "sector": sector_data['sector_name'],
                    "change": change
                })
        
        # Now find top sectors for each day
        sector_counts = {}
        
        sorted_dates = sorted(date_map.keys())
        # Filter for last N days (approx, since kline is 20 days)
        target_dates = sorted_dates[-days:] if days < len(sorted_dates) else sorted_dates
        
        for date in target_dates:
            daily_list = date_map[date]
            if not daily_list:
                continue
                
            # Sort by change desc
            daily_list.sort(key=lambda x: x['change'], reverse=True)
            
            # Top N Leaders
            # Get up to top_n sectors
            current_leaders = daily_list[:top_n]
            
            for leader in current_leaders:
                sec_name = leader['sector']
                sector_counts[sec_name] = sector_counts.get(sec_name, 0) + 1
                
        # Sort sectors by count
        ranked_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Save to cache
        self.cache[cache_key] = (ranked_sectors, current_time)
        
        return ranked_sectors


    def get_sector_data_by_name(self, sector_name_query):
        """
        Try to find and fetch data for a specific sector by name.
        """
        matched_code = None
        matched_name = None
        
        # 1. Exact matching first (Priority)
        for code, name in self.etf_map.items():
            if name == sector_name_query:
                matched_code = code
                matched_name = name
                break
        
        # 2. Fuzzy matching fallback (Only if exact match fails)
        if not matched_code:
            for code, name in self.etf_map.items():
                if (name in sector_name_query) or (sector_name_query in name):
                    matched_code = code
                    matched_name = name
                    break
        
        if not matched_code:
            return None
            
        lg = bs.login()
        if lg.error_code != '0':
            return None
            
        try:
            return self._fetch_etf_performance_baostock(matched_code, matched_name)
        except Exception as e:
            print(f"Error in get_sector_data_by_name: {e}")
            return None
        # Do not logout here

    def _fetch_etf_performance_baostock(self, code, name):
        """
        Helper to fetch single ETF data from Baostock and calculate performance.
        """
        try:
            # Parse code: sh512480 -> sh.512480, sz159995 -> sz.159995
            if code.startswith('sh'):
                bs_code = f"sh.{code[2:]}"
            elif code.startswith('sz'):
                bs_code = f"sz.{code[2:]}"
            else:
                return None
            
            end_date = datetime.date.today().strftime("%Y-%m-%d")
            # Get enough data for MA20 + 2 weeks change (approx 10 trading days)
            start_date = (datetime.date.today() - datetime.timedelta(days=60)).strftime("%Y-%m-%d")
            
            # Use adjustflag="1" (QFQ)
            rs = bs.query_history_k_data_plus(bs_code,
                "date,open,high,low,close,volume,amount,turn",
                start_date=start_date, end_date=end_date,
                frequency="d", adjustflag="1")
            
            if rs.error_code != '0':
                return None
                
            data_list = []
            while rs.next():
                data_list.append(rs.get_row_data())
            
            if not data_list:
                return None
                
            df = pd.DataFrame(data_list, columns=rs.fields)
            
            # Convert columns to numeric
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col])
            
            df['date'] = pd.to_datetime(df['date'])
            
            if len(df) < 5:
                return None

            # Calculate technical indicators
            df = calculate_technical_indicators(df)
            
            latest = df.iloc[-1]
            
            # Calculate 2-week change (approx 10 trading days)
            lookback_idx = -11 if len(df) >= 11 else 0
            base_close = df.iloc[lookback_idx]['close']
            
            if base_close == 0:
                pct_change = 0
            else:
                pct_change = (latest['close'] - base_close) / base_close * 100
            
            # Format technical indicators for context
            indicators = {
                "MA5": round(latest['MA5'], 3) if pd.notna(latest['MA5']) else None,
                "MA20": round(latest['MA20'], 3) if pd.notna(latest['MA20']) else None,
                "RSI": round(latest['RSI'], 2) if pd.notna(latest['RSI']) else None,
                "MACD": round(latest['MACD_diff'], 3) if pd.notna(latest['MACD_diff']) else None,
                "K": round(latest['K'], 2) if pd.notna(latest['K']) else None,
                "D": round(latest['D'], 2) if pd.notna(latest['D']) else None,
                "J": round(latest['J'], 2) if pd.notna(latest['J']) else None,
            }
            
            # K-line data for plotting (last 20 days)
            kline_data = df.tail(20).copy()
            kline_data['date'] = kline_data['date'].dt.strftime("%Y-%m-%d")
            
            return {
                "sector_name": name,
                "etf_code": code,
                "pct_change": round(pct_change, 2),
                "close": latest['close'],
                "amount": latest['amount'],
                "turnover_rate": latest['turn'] if 'turn' in latest else 0,
                "date": latest['date'].strftime("%Y-%m-%d"),
                "indicators": indicators,
                "kline_data": kline_data.to_dict(orient='records')
            }
            
        except Exception as e:
            print(f"Error fetching {code}: {e}")
            return None

if __name__ == "__main__":
    analyzer = SectorAnalyzer()
    print("Fetching top sectors...")
    top = analyzer.get_top_sectors_performance()
    for t in top:
        print(f"{t['sector_name']} ({t['etf_code']}): {t['pct_change']}%")
        print(f"  Indicators: {t['indicators']}")
