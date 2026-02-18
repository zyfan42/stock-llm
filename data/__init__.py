from .base import StockDataProvider
from .baostock_provider import BaostockProvider
import os
from dotenv import load_dotenv

load_dotenv()

def get_data_provider() -> StockDataProvider:
    """
    Factory function to get data provider.
    Currently enforced to BaostockProvider.
    """
    return BaostockProvider()
