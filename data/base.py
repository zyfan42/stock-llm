from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, Dict

class StockDataProvider(ABC):
    """
    股票数据提供者抽象基类
    """
    
    @abstractmethod
    def get_stock_list(self) -> pd.DataFrame:
        """
        获取所有股票列表
        Returns:
            DataFrame: 包含 code, name 等列
        """
        pass

    @abstractmethod
    def get_daily_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取日线数据
        Args:
            code: 股票代码
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
        Returns:
            DataFrame: 包含 date, open, high, low, close, volume 等列
        """
        pass
    
    @abstractmethod
    def get_stock_info(self, code: str) -> Dict:
        """
        获取股票基本信息
        """
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """
        获取数据源名称
        """
        pass
