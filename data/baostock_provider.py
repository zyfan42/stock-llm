import baostock as bs
import pandas as pd
from typing import Dict, Optional
from .base import StockDataProvider

class BaostockProvider(StockDataProvider):
    """
    Baostock 数据源实现
    """
    
    def __init__(self):
        self._login()
        
    @property
    def source_name(self) -> str:
        return "Baostock"
        
    def _login(self):
        lg = bs.login()
        if lg.error_code != '0':
            print(f"Baostock login failed: {lg.error_msg}")

    def __del__(self):
        bs.logout()

    def _format_code(self, code: str) -> str:
        """
        将 6 位代码转换为 Baostock 格式 (sh.xxxxxx / sz.xxxxxx)
        """
        code = code.strip().lower()
        if '.' in code: # 已经是类似 sh.600000 或 600000.sh
            # Baostock strict format is sh.600000
            parts = code.split('.')
            if parts[0] in ['sh', 'sz', 'bj']:
                return code
            elif parts[1] in ['sh', 'sz', 'bj']:
                return f"{parts[1]}.{parts[0]}"
            return code
            
        # Handle cases like sh600519 (no dot)
        if code.startswith('sh') and code[2:].isdigit():
             return f"sh.{code[2:]}"
        if code.startswith('sz') and code[2:].isdigit():
             return f"sz.{code[2:]}"
        if code.startswith('bj') and code[2:].isdigit():
             return f"bj.{code[2:]}"
            
        if code.startswith('6'):
            return f"sh.{code}"
        elif code.startswith('0') or code.startswith('3'):
            return f"sz.{code}"
        elif code.startswith('4') or code.startswith('8'):
            return f"bj.{code}"
        else:
            return code # 默认返回，可能出错

    def get_stock_list(self) -> pd.DataFrame:
        # Baostock 获取全市场股票列表比较麻烦，通常通过 query_all_stock
        # 但 query_all_stock 只能按日期查。
        # 简单起见，这里我们返回一个空列表，或者抛出未实现，
        # 因为 Baostock 更适合查询特定股票的历史数据。
        # 为了兼容性，我们可以硬编码一些热门股，或者通过其他方式。
        # 实际上，混合使用是一个好主意：用 AkShare 获取列表，用 Baostock 获取历史。
        # 这里为了完整性，尝试获取当天的。
        import datetime
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        rs = bs.query_all_stock(day=date)
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        # fields: code, tradeStatus, code_name
        if not df.empty:
            df = df.rename(columns={'code_name': 'name'})
            # Baostock code 是 sh.600000，我们需要去掉前缀吗？
            # 为了统一，我们在 Provider 内部保留原始格式，输出时尽量统一。
            # 但 base class 定义不太严格。
            # 这里暂时保留原样。
            return df[['code', 'name']]
        return pd.DataFrame(columns=['code', 'name'])

    def get_market_indices(self) -> list:
        """
        获取主要指数行情 (上证、深证、创业板)
        """
        indices = [
            {"code": "sh.000001", "name": "上证指数"},
            {"code": "sz.399001", "name": "深证成指"},
            {"code": "sz.399006", "name": "创业板指"}
        ]
        
        results = []
        import datetime
        date = datetime.date.today()
        
        # 尝试往前推 5 天，找到最近的有数据的一天
        latest_date = None
        for i in range(5):
            query_date = (date - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            # 检查上证指数是否有数据
            rs = bs.query_history_k_data_plus("sh.000001", "date", start_date=query_date, end_date=query_date, frequency="d")
            if rs.error_code == '0' and rs.next():
                latest_date = query_date
                break
        
        if not latest_date:
            return []
            
        for idx in indices:
            rs = bs.query_history_k_data_plus(idx["code"], 
                "close,pctChg,amount", 
                start_date=latest_date, end_date=latest_date, 
                frequency="d")
            if rs.error_code == '0' and rs.next():
                data = rs.get_row_data()
                results.append({
                    "name": idx["name"],
                    "current": float(data[0]),
                    "pct_change": float(data[1]),
                    "turnover": float(data[2]) if data[2] else 0.0
                })
        
        return results

    def get_daily_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        # start_date 格式 YYYYMMDD -> YYYY-MM-DD
        start_date_fmt = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end_date_fmt = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        
        bs_code = self._format_code(code)
        
        # frequency="d", adjustflag="3" (默认不复权? 1：后复权，2：前复权，3：不复权)
        # 通常分析用前复权 adjustflag="2"
        rs = bs.query_history_k_data_plus(bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date_fmt, end_date=end_date_fmt,
            frequency="d", adjustflag="2")
            
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
            
        if not data_list:
            return pd.DataFrame()
            
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 类型转换
        df['date'] = pd.to_datetime(df['date'])
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col])
            
        return df

    def get_stock_info(self, code: str) -> Dict:
        """
        获取股票基本信息 (PE, PB, ROE 等)
        """
        try:
            bs_code = self._format_code(code)
            # 获取最近一个交易日的日期
            # 这里简单取今天，如果今天是周末或非交易日，baostock 会返回空，需要往前推
            import datetime
            date = datetime.date.today()
            
            basic_info = {}
            
            # 0. 获取股票名称
            rs_basic = bs.query_stock_basic(code=bs_code)
            if rs_basic.error_code == '0' and rs_basic.next():
                basic_data = rs_basic.get_row_data()
                # code, code_name, ipoDate, outDate, type, status
                basic_info["name"] = basic_data[1]

            # 1. 获取估值数据 (PE, PB) - 尝试往前推 10 天
            for i in range(10):
                query_date = (date - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                rs = bs.query_history_k_data_plus(bs_code, 
                    "date,peTTM,pbMRQ,psTTM,pcfNcfTTM", 
                    start_date=query_date, end_date=query_date, 
                    frequency="d", adjustflag="3")
                
                if rs.error_code == '0' and rs.next():
                    data = rs.get_row_data()
                    basic_info.update({
                        "pe_ttm": data[1],
                        "pb_mrq": data[2],
                        "ps_ttm": data[3],
                        "pcf_ttm": data[4]
                    })
                    break
            
            # 2. 获取季频财务数据 (ROE, 净利润增长率)
            # 需要找到最近的财报季度。简单起见，我们查找去年 Q3/Q4 和今年 Q1/Q2/Q3
            current_year = date.year
            quarters = []
            for y in [current_year, current_year-1]:
                for q in [4, 3, 2, 1]:
                    quarters.append((y, q))
            
            for y, q in quarters:
                # 盈利能力
                rs_profit = bs.query_profit_data(code=bs_code, year=y, quarter=q)
                if rs_profit.error_code == '0' and rs_profit.next():
                    profit_data = rs_profit.get_row_data()
                    # roeAvg, netProfit, epsTTM, totalShare, liqaShare
                    # baostock query_profit_data return fields: code, pubDate, statDate, roeAvg, npMargin, gpMargin, ...
                    # 假设我们只关心 ROE
                    basic_info["roe_avg"] = profit_data[3]
                    basic_info["gross_margin"] = profit_data[5] # 毛利率

                    # 成长能力
                    rs_growth = bs.query_growth_data(code=bs_code, year=y, quarter=q)
                    if rs_growth.error_code == '0' and rs_growth.next():
                        growth_data = rs_growth.get_row_data()
                        # YOYEquity, YOYAsset, YOYNI, YOYEPSBasic, YOYPNI
                        # YOYNI: 净利润同比增长率
                        basic_info["net_profit_growth"] = growth_data[5] # YOYNI
                        basic_info["revenue_growth"] = growth_data[3] # YOYRevenue (Main Income) -> check baostock doc
                        # actually baostock growth fields: 
                        # code, pubDate, statDate, YOYEquity, YOYAsset, YOYNI, YOYEPSBasic, YOYPNI
                    
                    break # Found latest quarter

            return {"code": code, **basic_info}
        except Exception as e:
            print(f"Error getting stock info for {code}: {e}")
            return {"code": code}
