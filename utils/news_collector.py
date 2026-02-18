import requests
import datetime

class NewsCollector:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.sina_api_url = "https://zhibo.sina.com.cn/api/zhibo/feed?callback=&page=1&page_size={limit}&zhibo_id=152"

    def get_latest_news(self, limit=30) -> list:
        """
        获取新浪财经 7x24 小时快讯
        """
        try:
            # page_size increased to allow filtering
            url = self.sina_api_url.format(limit=max(limit, 50))
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'result' in data and 'data' in data['result']:
                    raw_list = data['result']['data']['feed']['list']
                    news_items = []
                    for item in raw_list:
                        # 简单的清洗
                        content = item.get('rich_text', '').strip()
                        time_str = item.get('create_time', '')
                        
                        # 过滤掉过于简短或无关的信息（可选）
                        if len(content) > 10:
                            news_items.append(f"【{time_str}】{content}")
                    
                    return news_items[:limit]
            return []
        except Exception as e:
            print(f"Error fetching news: {e}")
            return []

    def get_stock_news(self, stock_name, limit=5) -> list:
        """
        获取特定股票的相关新闻 (通过过滤全市场快讯)
        """
        all_news = self.get_latest_news(limit=100) # Fetch more to filter
        related_news = []
        for news in all_news:
            if stock_name in news:
                related_news.append(news)
        
        return related_news[:limit]

    def get_news_summary(self, limit=30) -> str:
        """
        获取新闻并合并为字符串供 LLM 分析
        """
        news_list = self.get_latest_news(limit)
        return "\n".join(news_list)
