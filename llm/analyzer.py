from openai import OpenAI
import os
from dotenv import load_dotenv
import json

load_dotenv()

class StockAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = os.getenv("LLM_MODEL", "qwen-plus")
        
        if not self.api_key:
             # 如果没有配置 key，打印警告
             print("Warning: LLM_API_KEY not found.")
             self.api_key = "dummy" # 防止 OpenAI 客户端初始化报错

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def analyze(self, stock_code: str, stock_name: str, daily_data_summary: dict, technical_indicators: dict) -> str:
        """
        使用 LLM 分析股票数据 (单只股票简单分析)
        """
        
        # 构造 Prompt
        prompt = f"""
你是一个专业的股票分析师。请根据以下数据对股票 {stock_name} ({stock_code}) 进行简要分析并给出投资建议。

【基本行情】
日期: {daily_data_summary.get('date')}
收盘价: {daily_data_summary.get('close')}
涨跌幅: {daily_data_summary.get('pct_change')}%
成交量: {daily_data_summary.get('volume')}

【技术指标】
MA5: {technical_indicators.get('MA5'):.2f}
MA20: {technical_indicators.get('MA20'):.2f} (MA5 > MA20: {technical_indicators.get('MA5') > technical_indicators.get('MA20')})
RSI (14): {technical_indicators.get('RSI'):.2f} (超买>80, 超卖<20)
MACD Diff: {technical_indicators.get('MACD'):.2f}
KDJ: K={technical_indicators.get('K', 0):.2f}, D={technical_indicators.get('D', 0):.2f}, J={technical_indicators.get('J', 0):.2f}

【分析要求】
1. 分析当前趋势（上涨/下跌/震荡）。
2. 结合技术指标（MA, RSI, MACD, KDJ）评价当前买卖信号。
3. 给出短期（1-2周）的操作建议（买入/持有/卖出/观望）。
4. 提示风险。

请输出 Markdown 格式的分析报告。
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个资深的金融分析师，擅长技术面分析和风险控制。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM 分析失败: {str(e)}\n\n请检查 .env 文件中的 LLM_API_KEY 配置。"

    def analyze_stock(self, stock_code: str, context_str: str) -> str:
        """
        Generic stock analysis based on provided context string.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个资深的金融分析师，擅长结合技术面与基本面给出投资建议。"},
                    {"role": "user", "content": f"股票代码: {stock_code}\n\n{context_str}"}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM 分析失败: {str(e)}"

    def analyze_portfolio(self, stocks_context: str) -> str:
        """
        Analyze multiple stocks together and provide comparative advice.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一名资深投资顾问，擅长多股对比分析和投资组合构建。"},
                    {"role": "user", "content": f"请对比分析以下股票组合：\n\n{stocks_context}\n\n任务：\n1. 横向对比各股优劣（技术面/基本面）。\n2. 给出具体的仓位配置建议或优选顺序。\n3. 提示整体组合风险。"}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"组合分析失败: {str(e)}"

    def identify_market_hotspots(self, news_text: str, market_sectors: list = None, etf_data: list = None, top_gainers: list = None) -> dict:
        """
        从新闻中识别热点板块，并从今日涨幅榜中筛选龙头股
        Args:
            news_text: 新闻文本
            market_sectors: (可选) 市场领涨板块列表
            etf_data: (可选) 市场领涨 ETF 列表
            top_gainers: (可选) 今日全市场涨幅榜前列 [{"code": "...", "name": "...", "pct_change": ...}]
        Returns:
            {
                "sector": "板块名称",
                "reason": "推荐理由",
                "stocks": ["code1", "code2", "code3"],
                "etfs": ["code1", "code2"]
            }
        """
        market_info = ""
        if market_sectors:
             market_info += "\n【今日领涨板块数据(仅供参考)】\n" + "\n".join([f"- {s['name']}: +{s['pct_change']}%" for s in market_sectors[:10]])
        
        if etf_data:
             market_info += "\n【今日领涨 ETF 数据(仅供参考)】\n" + "\n".join([f"- {e['name']} ({e['code']}): +{e['pct_change']}%" for e in etf_data[:5]])

        gainers_info = ""
        if top_gainers:
            # 只提供前 50-80 个，避免 token 溢出
            limit_n = 80
            gainers_str = ", ".join([f"{s['code']} {s['name']}(+{s['pct_change']}%)" for s in top_gainers[:limit_n]])
            gainers_info = f"\n【今日全市场涨幅榜 Top {limit_n} (从中筛选)】\n{gainers_str}\n"

        prompt = f"""
请阅读以下今日财经新闻{ "以及实时板块/ETF 涨幅数据" if market_sectors or etf_data else "" }，分析当前最热门、最具潜力的 1 个 A 股核心板块。

【重要指令】
1. 确定核心板块后，请务必优先从【今日全市场涨幅榜】中挑选 3-5 只属于该板块的强势个股。
2. 只有当涨幅榜中没有相关股票时，才基于你的知识库补充其他龙头股。
3. 必须确保股票代码是正确的沪深 A 股代码（60xxxx, 00xxxx, 30xxxx, 68xxxx）。

【今日新闻】
{news_text}
{market_info}
{gainers_info}

【输出要求】
请仅返回标准的 JSON 格式，不要包含 Markdown 标记或其他文字。格式如下：
{{
    "sector": "板块名称",
    "reason": "基于新闻和数据分析的简短推荐理由",
    "stocks": ["60xxxx", "00xxxx"],
    "etfs": ["51xxxx", "15xxxx"]
}}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个敏锐的金融新闻分析师。请只输出 JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2, # 低温度以保证 JSON 格式正确
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            print(f"Hotspot identification failed: {e}")
            # Fallback output
            return {
                "sector": "自动分析失败",
                "reason": f"LLM 解析错误: {str(e)}",
                "stocks": [],
                "etfs": []
            }

    def chat_with_context(self, history: list, new_input: str, context_data: str) -> str:
        """
        与 LLM 进行上下文对话，基于之前的策略分析结果
        Args:
            history: 历史对话记录 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            new_input: 用户新输入的问题
            context_data: 策略分析的上下文数据 (包含板块信息、候选股数据等)
        Returns:
            str: LLM 的回复
        """
        system_prompt = f"""
你是一个专业的股票分析师助手。
用户刚刚收到了一份关于【{context_data}】的策略分析报告。
现在用户对报告内容或相关股票有进一步的疑问。
请基于之前的分析结果和提供的数据，解答用户的问题。
保持客观、理性，不要给出确定的投资建议，而是提供分析思路和数据支持。
"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加历史记录 (限制最近 5 轮对话以节省 token)
        messages.extend(history[-10:])
        
        # 添加当前问题
        messages.append({"role": "user", "content": new_input})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield content
                    
        except Exception as e:
            yield f"对话发生错误: {str(e)}"

    def analyze_strategy(self, sector_name: str, candidates_data: list, market_context: str = "", sector_tech_data: dict = None) -> str:
        """
        严选策略师模式分析（流式生成器）
        Args:
            sector_name: 板块名称
            candidates_data: 候选股票数据列表
            market_context: 市场上下文 (包含领涨板块信息等)
            sector_tech_data: 目标板块的 ETF 技术指标数据 (包含 K线、MA、RSI 等)
        Yields:
            str: 逐步生成的分析报告内容
        """
        import datetime
        current_date = datetime.date.today().strftime("%Y-%m-%d")
        
        # 格式化候选股数据供 Prompt 使用
        candidates_str = ""
        for i, stock in enumerate(candidates_data):
            # Safe MA20 check
            ma20_val = stock.get('ma20')
            close_val = stock.get('close', 0)
            ma_status = "未知"
            if ma20_val is not None:
                ma_status = "MA20上方" if close_val > ma20_val else "MA20下方"

            candidates_str += f"""
候选 {i+1}: {stock['code']} {stock['name']}
- 价格: {stock['close']} (涨跌幅: {stock.get('pct_change', 0)}%)
- 市盈率(TTM): {stock.get('pe_ttm', 'N/A')}, 市净率: {stock.get('pb_mrq', 'N/A')}
- 净资产收益率(ROE): {stock.get('roe', 'N/A')}%, 净利增长率: {stock.get('growth', 'N/A')}%
- 技术指标: MA20={stock.get('ma20', 'N/A')}, RSI={stock.get('rsi', 'N/A')}, MACD={stock.get('macd', 'N/A')}
- 状态: {ma_status}
-------------------
"""

        # 格式化板块技术面数据
        sector_tech_str = ""
        if sector_tech_data:
            indicators = sector_tech_data.get('indicators', {})
            sector_tech_str = f"""
【板块技术面参考 (基于对应 ETF: {sector_tech_data.get('etf_code')})】
- 最新收盘: {sector_tech_data.get('close')} (涨跌幅: {sector_tech_data.get('pct_change')}%)
- 均线: MA5={indicators.get('MA5')}, MA20={indicators.get('MA20')}
- 动量指标: RSI={indicators.get('RSI')}, KDJ(K/D/J)={indicators.get('K')}/{indicators.get('D')}/{indicators.get('J')}
- MACD: {indicators.get('MACD')}
- 近期走势 (Last 5 days close): {[k['close'] for k in sector_tech_data.get('kline_data', [])[-5:]]}
"""

        prompt = f"""
Role: 沪深A股严选策略师 (Low-Risk/Short-Term)

你是一名中立、审慎的股票经理。请在沪深A股范围内，基于提供的数据，筛选1只适合低风险、1-4周持有的板块龙头。

【输入数据】
核心板块：{sector_name}
市场/板块背景：
{market_context if market_context else "请基于你的知识库补充该板块近期的热点催化剂"}

{sector_tech_str}

候选股票池：
{candidates_str}

【指令】
请严格按照以下 Markdown 格式输出分析报告。如果某项数据缺失，请根据价格量能形态进行合理推断。
请充分利用提供的【板块技术面参考】数据（如果有）来分析板块趋势。
如果【市场/板块背景】中提供了全市场领涨板块信息及【两周内日领涨次数排名】，请结合当前板块是否属于市场热点进行评价。

分析清单（请按此结构输出）：

### 1. 截至日期
**日期**：{current_date}

### 2. 强热点板块 Top1
**核心板块**：{sector_name}
**板块趋势分析**：
- [请根据板块技术面数据(MA20, RSI, MACD等)判断板块当前处于 上升/下跌/震荡 趋势]
- [结合两周内涨幅评价板块强度]
- [结合【两周内日领涨次数排名】评价板块的活跃度与资金关注度（如某板块多次领涨，说明资金持续性强）]
**催化剂** (≤2条)：
- [请补充] [来源: 权威财经媒体/公告]
- [请补充] [来源: 权威财经媒体/公告]
**证伪/失效点**：[请补充]（若出现此信号则逻辑失效）

### 3. 资金面（基于价格与成交量推断）
**观察标的**：{candidates_data[0]['name'] if candidates_data else '该板块ETF'}
**资金动向**：[请根据量能形态描述，如：放量上涨显示资金流入，缩量回调显示惜售]
**结论**：资金持续性 = 【强 / 中 / 弱】

### 4. 龙头筛选（候选{len(candidates_data)} → 最终1）
**候选池**：
{', '.join([f"{s['code']} {s['name']}" for s in candidates_data])}

**最终标的**：
> **[请从候选池中选择一只]**
**龙头理由** (≤2条)：市值/地位/权重/辨识度等 [来源: 财报/基本面]

### 5. 技术面（日线）
**均线**：股价在 MA20 [上/下/附近]
**量能**：[请描述]
**MACD**：[请描述]
**形态**：[请描述]
**关键位**：
- 支撑位 ≈ [请估算] 元
- 压力位 ≈ [请估算] 元

### 6. 交易计划（1-4周｜低风险）
**入场方式**：突破确认区 [价格] 或 回踩吸纳区 [价格]
**止损区间**：[价格]（条件：收盘跌破 [价格] 或 失守MA20）
**止盈区间**：第一目标 [价格]；第二目标 [价格]

### 7. 风险提示（触发式，≤3条）

### 最终总结
"""
        
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个资深的金融分析师，擅长技术面分析和风险控制。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            yield f"LLM 分析失败: {str(e)}\n\n请检查 .env 文件中的 LLM_API_KEY 配置。"

    def chat(self, user_input: str, context: str = "") -> str:
        """
        自由对话模式
        """
        try:
             messages = [
                {"role": "system", "content": "你是一个股票投资助手。"},
                {"role": "user", "content": f"上下文信息:\n{context}\n\n用户问题: {user_input}"}
            ]
             response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
             return response.choices[0].message.content
        except Exception as e:
            return f"对话失败: {str(e)}"
