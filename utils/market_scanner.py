
import requests
import json
import time
import os
import sys
import glob

class MarketScanner:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Referer": "http://quote.eastmoney.com/"
        }
        self.timeout = 5
        
        # Determine cache directory
        if getattr(sys, 'frozen', False):
            # Running in a bundle
            app_data = os.getenv('APPDATA')
            if app_data:
                self.cache_dir = os.path.join(app_data, 'StockLLM', 'cache')
            else:
                self.cache_dir = os.path.join(os.path.expanduser("~"), '.stockllm', 'cache')
        else:
            # Running in a normal Python environment
            self.cache_dir = "cache"
            
        self._ensure_cache_dir()
        self._clean_old_cache()
        
        # Predefined Sector ETFs for Ranking (since Sector API is blocked)
        self.sector_etfs = {
            "sh512480": "半导体",
            "sz159995": "芯片",
            "sh512690": "酒ETF",
            "sh515030": "新能车",
            "sh515790": "光伏",
            "sh512880": "证券",
            "sh512010": "医药",
            "sh515050": "5G",
            "sh512400": "有色",
            "sh512100": "1000ETF",
            "sh512000": "券商",
            "sh516160": "新能源",
            "sh512660": "军工",
            "sh515000": "科技",
            "sz159928": "消费",
            "sh510300": "沪深300",
            "sh588000": "科创50",
            "sz159915": "创业板",
            "sh510500": "中证500",
            "sh510050": "上证50",
            "sh512760": "芯片龙头",
            "sh512980": "传媒",
            "sh515220": "煤炭",
            "sh512200": "地产",
            "sh512800": "银行",
            "sh515210": "钢铁",
            "sh512580": "环保",
            "sh515020": "银行ETF",
            "sh512670": "国防",
            "sh515700": "新能车ETF"
        }

    def _ensure_cache_dir(self):
        if os.path.exists(self.cache_dir):
            if not os.path.isdir(self.cache_dir):
                try:
                    os.remove(self.cache_dir)
                    print(f"Removed file blocking cache directory: {self.cache_dir}")
                except Exception as e:
                    print(f"Error removing file blocking cache directory: {e}")
                    # Try to proceed anyway, maybe os.makedirs will work now?
        
        os.makedirs(self.cache_dir, exist_ok=True)

    def _clean_old_cache(self):
        """Clean cache files older than 24 hours"""
        try:
            now = time.time()
            for f in glob.glob(os.path.join(self.cache_dir, "*.json")):
                if os.stat(f).st_mtime < now - 86400: # 1 day
                    os.remove(f)
        except Exception as e:
            print(f"Error cleaning cache: {e}")

    def _save_to_cache(self, key, data):
        try:
            file_path = os.path.join(self.cache_dir, f"{key}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                # Add timestamp to cached data
                if isinstance(data, dict):
                    data['_cached_at'] = time.time()
                elif isinstance(data, list):
                    # Wrap list in a dict to store metadata
                    data = {"_data": data, "_cached_at": time.time(), "_is_list_wrapper": True}
                
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving to cache {key}: {e}")

    def _get_from_cache(self, key):
        try:
            file_path = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.exists(file_path):
                # Return cached data even if it's a bit old, better than nothing when API fails
                # But we can check if it's *too* old (e.g. > 12 hours) if we want stricter rules
                # User requirement is to handle "API cannot be connected", so we should be lenient.
                with open(file_path, 'r', encoding='utf-8') as f:
                    print(f"Using cached data for {key}")
                    data = json.load(f)
                    
                    # Unwrap if it's a list wrapper
                    if isinstance(data, dict) and data.get("_is_list_wrapper"):
                        return data.get("_data")
                        
                    return data
        except Exception as e:
            print(f"Error reading from cache {key}: {e}")
        return None

    def get_cache_timestamp(self, key):
        """Get the timestamp of a cached item"""
        try:
            file_path = os.path.join(self.cache_dir, f"{key}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('_cached_at')
        except:
            pass
        return None

    def get_quotes(self, codes: list):
        """
        Fetch real-time quotes from Tencent API (qt.gtimg.cn)
        codes: list of stock codes with prefix (e.g. ['sh600519', 'sz000001'])
        Returns: dict {code: {name, price, pct_change, ...}}
        """
        return self._get_tencent_quotes(codes)

    def _get_tencent_quotes(self, codes: list):
        """
        Fetch real-time quotes from Tencent API (qt.gtimg.cn)
        codes: list of stock codes with prefix (e.g. ['sh600519', 'sz000001'])
        Returns: dict {code: {name, price, pct_change, ...}}
        """
        if not codes:
            return {}
            
        # Split into chunks of 50 to avoid URL length limits
        chunk_size = 50
        results = {}
        
        for i in range(0, len(codes), chunk_size):
            chunk = codes[i:i+chunk_size]
            code_str = ",".join(chunk)
            url = f"http://qt.gtimg.cn/q={code_str}"
            
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                if response.status_code != 200:
                    continue
                    
                # Parse Tencent format: v_sh600519="1~贵州茅台~600519~1700.00~..."
                content = response.text
                lines = content.split(';')
                for line in lines:
                    line = line.strip()
                    if not line: continue
                    
                    # line: v_sh600519="1~贵州茅台~..."
                    if '=' not in line: continue
                    
                    key_part, val_part = line.split('=', 1)
                    code = key_part.replace('v_', '').strip() # sh600519
                    val = val_part.strip('"')
                    
                    parts = val.split('~')
                    if len(parts) < 30: continue
                    
                    # 1: Name, 3: Price, 32: PctChange (%)
                    # Index might be different for Index vs Stock
                    # For Stock/ETF:
                    # 1: Name
                    # 3: Current Price
                    # 31: Change Amount
                    # 32: Change Percent
                    # 36: Volume (Hand)
                    # 37: Amount (Wan)
                    
                    try:
                        name = parts[1]
                        price = float(parts[3])
                        pct = float(parts[32])
                        change = float(parts[31])
                        volume = float(parts[36])
                        amount = float(parts[37]) * 10000 # Convert to Yuan
                        
                        # New fields for better sorting
                        turnover_rate = float(parts[38]) if len(parts) > 38 and parts[38] else 0.0
                        pe = float(parts[39]) if len(parts) > 39 and parts[39] else 0.0
                        market_cap = float(parts[45]) if len(parts) > 45 and parts[45] else 0.0 # Total Cap
                        
                        results[code] = {
                            "name": name,
                            "current": price,
                            "pct_change": pct,
                            "change": change,
                            "volume": volume,
                            "turnover": amount,
                            "turnover_rate": turnover_rate,
                            "pe": pe,
                            "market_cap": market_cap
                        }
                    except (ValueError, IndexError):
                        continue
                        
            except Exception as e:
                print(f"Error fetching Tencent quotes for chunk: {e}")
                
        return results

    def get_market_indices(self):
        """
        获取主要指数 (上证, 深证, 创业板, 科创50, 沪深300) + 深证综指 (用于计算成交额)
        Using Tencent API
        """
        # Codes: sh000001 (上证), sz399001 (深证), sz399006 (创业板), sh000688 (科创50), sh000300 (沪深300), sz399106 (深证综指)
        # Note: Tencent uses sh000300 for CSI300
        codes = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300", "sz399106"]
        cache_key = "market_indices_real"
        
        try:
            quotes = self._get_tencent_quotes(codes)
            indices = []
            
            # Map codes to display names if needed, or use API names
            code_map = {
                "sh000001": "上证指数",
                "sz399001": "深证成指",
                "sz399006": "创业板指",
                "sh000688": "科创50",
                "sh000300": "沪深300",
                "sz399106": "深证综指"
            }
            
            for code in codes:
                if code in quotes:
                    q = quotes[code]
                    indices.append({
                        "code": code, # Keep code for identification
                        "name": code_map.get(code, q['name']),
                        "current": q['current'],
                        "pct_change": q['pct_change'],
                        "change": q['change'],
                        "volume": q['volume'],
                        "turnover": q['turnover']
                    })
            
            if indices:
                self._save_to_cache(cache_key, indices)
                return indices
                
        except Exception as e:
            print(f"Error fetching indices (Tencent): {e}")
            
        # Fallback to cache
        cached = self._get_from_cache(cache_key)
        return cached if cached else []


    def get_market_sentiment(self):
        """
        获取市场情绪 (涨跌家数)
        Returns: {"up": 1000, "down": 2000, "flat": 100}
        Uses Index Constituent Counts (f104/f105/f106) from SH and SZ Indices.
        """
        cache_key = "market_sentiment_index"
        try:
            ts = int(time.time() * 1000)
            # 1.000001 = SH Index, 0.399001 = SZ Index
            # f104: Up Count, f105: Down Count, f106: Flat Count
            url = f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001&fields=f104,f105,f106&_={ts}"
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            
            if response.status_code != 200:
                print(f"Error fetching sentiment: HTTP {response.status_code}")
                cached = self._get_from_cache(cache_key)
                return cached if cached else {"up": 0, "down": 0, "flat": 0}

            data = response.json()
            up, down, flat = 0, 0, 0
            
            if data and 'data' in data and data['data'] and 'diff' in data['data']:
                diff = data['data']['diff']
                for item in diff:
                    up += item.get('f104', 0)
                    down += item.get('f105', 0)
                    flat += item.get('f106', 0)
                        
            result = {"up": up, "down": down, "flat": flat}
            if up + down + flat > 0:
                self._save_to_cache(cache_key, result)
            return result
        except Exception as e:
            print(f"Error fetching sentiment: {e}")
            cached = self._get_from_cache(cache_key)
            return cached if cached else {"up": 0, "down": 0, "flat": 0}

    def get_top_sectors(self, limit=5):
        """
        获取领涨板块 (Using ETF Performance as proxy)
        Since Sector API is blocked, we use a basket of Sector ETFs to approximate sector performance.
        Returns: [{"name": "白酒", "pct_change": 2.5}, ...]
        """
        cache_key = "top_sectors_etf_proxy"
        
        try:
            # 1. Fetch ETF quotes
            codes = list(self.sector_etfs.keys())
            quotes = self._get_tencent_quotes(codes)
            
            sectors = []
            for code, name in self.sector_etfs.items():
                if code in quotes:
                    q = quotes[code]
                    sectors.append({
                        "name": name,
                        "pct_change": q['pct_change']
                    })
            
            # 2. Sort by pct_change descending
            sectors.sort(key=lambda x: x['pct_change'], reverse=True)
            
            # Filter out CacheSector_A/B just in case (though not in our list)
            sectors = [s for s in sectors if s['name'] not in ["CacheSector_A", "CacheSector_B"]]
            
            result = sectors[:limit]
            
            if result:
                self._save_to_cache(cache_key, result)
                return result
                
        except Exception as e:
            print(f"Error fetching top sectors (ETF proxy): {e}")
            
        # Fallback to cache
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached[:limit]

        # Final Fallback to Mock Data (if even Tencent fails)
        print("Using mock data for sectors due to API failure")
        return [
            {"name": "半导体(演示)", "pct_change": 3.25},
            {"name": "人工智能(演示)", "pct_change": 2.84},
            {"name": "新能源车(演示)", "pct_change": 1.95},
            {"name": "生物医药(演示)", "pct_change": 1.42},
            {"name": "消费电子(演示)", "pct_change": 1.10}
        ][:limit]

    def _get_sina_rank(self, node, limit=5):
        """
        Helper to fetch ranking from Sina
        """
        cache_key = f"sina_rank_{node}"
        try:
            url = f"http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num={limit}&sort=changepercent&asc=0&node={node}"
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            # Sina sometimes returns non-strict JSON keys, but v2 usually returns valid JSON.
            # If it fails, we might need a safer parser, but requests.json() is usually fine for v2.
            data = response.json()
            if data:
                self._save_to_cache(cache_key, data)
            return data
        except Exception as e:
            print(f"Error fetching Sina rank for {node}: {e}")
            cached = self._get_from_cache(cache_key)
            if cached:
                return cached
                
            # Fallback Mock Data
            if node == 'hs_a': # A-share stocks
                return [
                    {"code": "600519", "name": "贵州茅台(演示)", "trade": "1700.00", "changepercent": "2.5"},
                    {"code": "300750", "name": "宁德时代(演示)", "trade": "200.00", "changepercent": "1.8"},
                    {"code": "002594", "name": "比亚迪(演示)", "trade": "250.00", "changepercent": "1.5"}
                ][:limit]
            elif node == 'etf_hq_fund': # ETFs
                return [
                    {"code": "510300", "name": "沪深300ETF(演示)", "trade": "3.500", "changepercent": "1.2"},
                    {"code": "588000", "name": "科创50ETF(演示)", "trade": "0.900", "changepercent": "2.1"},
                    {"code": "512480", "name": "半导体ETF(演示)", "trade": "0.800", "changepercent": "3.5"}
                ][:limit]
            return []

    def get_top_stocks(self, limit=5):
        """
        获取涨幅榜 (Sina)
        """
        data = self._get_sina_rank('hs_a', limit)
        stocks = []
        for item in data:
            stocks.append({
                "code": item['code'],
                "name": item['name'],
                "price": float(item['trade']),
                "pct_change": float(item['changepercent'])
            })
        return stocks
            
    def get_top_etfs(self, limit=5):
        """
        获取 ETF 涨幅榜 (Using Predefined List)
        """
        # We can reuse the sector ETFs list, but maybe we want a broader list?
        # For now, let's just return the top performing ones from our sector list
        # plus maybe some others if we had them.
        
        # We can just reuse get_top_sectors logic but return code/name
        try:
            codes = list(self.sector_etfs.keys())
            quotes = self._get_tencent_quotes(codes)
            
            etfs = []
            for code, name in self.sector_etfs.items():
                if code in quotes:
                    q = quotes[code]
                    etfs.append({
                        "code": code[2:], # Remove sh/sz prefix
                        "name": name,
                        "price": q['current'],
                        "pct_change": q['pct_change']
                    })
            
            etfs.sort(key=lambda x: x['pct_change'], reverse=True)
            return etfs[:limit]
            
        except Exception as e:
            print(f"Error fetching top ETFs: {e}")
            
        # Fallback
        return [
            {"code": "512480", "name": "半导体(演示)", "price": 0.800, "pct_change": 3.5},
            {"code": "512690", "name": "酒ETF(演示)", "price": 0.700, "pct_change": 2.8}
        ][:limit]
