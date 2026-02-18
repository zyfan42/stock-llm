from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import logging
import difflib
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ValidationError

load_dotenv()
logger = logging.getLogger(__name__)

# --- Data Models ---

class SectorScore(BaseModel):
    name: str = Field(..., description="Sector name")
    score: int = Field(..., ge=0, le=100, description="Score from 0-100")
    reason: str = Field(..., description="Brief reason for the score")

class SectorSelectionResponse(BaseModel):
    sector_scores: List[SectorScore] = Field(..., description="List of scores for all candidate sectors")
    selected_sector: str = Field(..., description="The name of the single selected sector (must be the one with highest score)")
    score: int = Field(..., ge=0, le=100, description="Score of the selected sector")
    reason: str = Field(..., description="Detailed reason for selection in Chinese")
    risk_warning: str = Field(..., description="Risk warning in Chinese")

class StockCandidate(BaseModel):
    code: str = Field(..., description="Stock code")
    name: str = Field(..., description="Stock name")
    reason: str = Field(..., description="Reason for inclusion in Chinese")

class StockScreeningResponse(BaseModel):
    candidates: List[StockCandidate] = Field(..., min_items=5, max_items=5, description="List of exactly 5 candidate stocks")

class StockSelectionResponse(BaseModel):
    selected_stock_code: str = Field(..., description="The code of the final selected stock")
    selected_stock_name: str = Field(..., description="The name of the final selected stock")
    score: int = Field(..., ge=0, le=100, description="Score from 0-100")
    reason: str = Field(..., description="Detailed investment logic in Chinese")
    risk_factors: str = Field(..., description="Specific risk factors in Chinese")
    suggested_action: Literal["Buy", "Wait", "Observe"] = Field(..., description="Suggested action")

# --- Analyzer Class ---

class PipelineAnalyzer:
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = os.getenv("LLM_MODEL", "qwen-plus")
        
        if not self.api_key:
             print("Warning: LLM_API_KEY not found.")
             self.api_key = "dummy"

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _call_llm_with_retry(self, system_prompt: str, user_prompt: str, response_model: type[BaseModel], valid_names: Optional[List[str]] = None, name_field: str = None, max_retries: int = 3) -> BaseModel:
        """
        Generic method to call LLM with JSON validation and retry logic.
        """
        last_error = None
        current_model = self.model
        
        # Models to try in order if the first one fails with Quota/Auth errors
        fallback_models = []
        if "qwen" in current_model:
            # If using Qwen, try turbo as fallback
            if current_model != "qwen-turbo":
                fallback_models.append("qwen-turbo")
        
        # Combine attempts
        total_attempts = max_retries
        
        for attempt in range(total_attempts):
            try:
                logger.info(f"Calling LLM with model {current_model} (Attempt {attempt+1}/{total_attempts})")
                response = self.client.chat.completions.create(
                    model=current_model,
                    messages=[
                        {"role": "system", "content": system_prompt + "\nIMPORTANT: Return ONLY valid JSON matching the schema."},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.2, # Low temperature for structural stability
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from LLM")
                
                # 1. JSON Parse
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    raise ValueError("Invalid JSON format")
                
                # 2. Reference Correction (Anti-Hallucination & Typos)
                if valid_names and name_field:
                    try:
                        self._correct_references_in_dict(data, valid_names, name_field)
                    except ValueError as e:
                        logger.warning(f"Reference validation failed: {e}")
                        raise e

                # 3. Normalization & Pydantic Validation
                try:
                    if response_model == SectorSelectionResponse:
                        data = self._normalize_sector_selection_data(data)
                        
                    obj = response_model.model_validate(data)
                except ValidationError as ve:
                    raise ValueError(f"Schema validation failed: {ve}")
                
                # Attach metadata
                obj._metadata = {
                    "used_model": current_model,
                    "fallback_triggered": current_model != self.model
                }
                
                return obj

            except Exception as e:
                error_str = str(e)
                last_error = e
                logger.error(f"Attempt {attempt + 1} failed with {current_model}: {e}")
                
                # Check for Quota/403 errors
                if "403" in error_str or "FreeTier" in error_str or "Quota" in error_str:
                    if fallback_models:
                        next_model = fallback_models.pop(0)
                        logger.warning(f"Quota exhausted for {current_model}. Switching to fallback: {next_model}")
                        current_model = next_model
                        continue 
                    else:
                        raise ValueError(f"模型免费额度已耗尽 (Model: {current_model})。请在侧边栏切换模型或配置新的 API Key。\n\nError: {error_str}")
                
                # Add error context to next prompt (simplified retry)
                user_prompt += f"\n\nPrevious attempt failed with error: {str(e)}. Please correct the format/content."
                
        logger.error(f"All {total_attempts} attempts failed. Last error: {last_error}")
        raise last_error

    def _correct_references_in_dict(self, data: dict, valid_names: List[str], field_name: str):
        """
        Recursively check if fields match valid names and auto-correct typos.
        Modifies data in-place.
        """
        # Convert valid_names to set for O(1) lookup, normalize to string
        valid_set = {str(n) for n in valid_names}
        
        def check_and_correct(val):
            val_str = str(val)
            if val_str in valid_set:
                return val
            
            # Try fuzzy match
            matches = difflib.get_close_matches(val_str, valid_names, n=1, cutoff=0.6)
            if matches:
                corrected = matches[0]
                logger.warning(f"Auto-correcting '{val_str}' to '{corrected}' for field '{field_name}'")
                return corrected
            
            raise ValueError(f"Value '{val}' for field '{field_name}' not found in provided input list. Valid options: {valid_names}")

        def recursive_process(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k == field_name:
                        d[k] = check_and_correct(v)
                    elif isinstance(v, (dict, list)):
                        recursive_process(v)
            elif isinstance(d, list):
                for item in d:
                    recursive_process(item)
        
        recursive_process(data)

    def _normalize_sector_selection_data(self, data: dict) -> dict:
        """
        Normalize SectorSelectionResponse data to handle missing fields gracefully.
        Specifically, fill missing 'reason' in sector_scores with a default value.
        """
        if not isinstance(data, dict):
            return data
            
        scores = data.get("sector_scores")
        if isinstance(scores, list):
            for item in scores:
                if isinstance(item, dict) and "reason" not in item:
                    item["reason"] = "未提供评分原因"
        
        return data

    # --- Stage 2: Sector Selection ---
    def select_sector(self, sector_details: str, candidate_names: List[str], user_preferences: dict = None) -> SectorSelectionResponse:
        system_prompt = "你是一名资深基金经理。基于量化评分模型和市场情绪，从候选板块中精选出唯一的最佳板块。"
        
        pref_str = ""
        if user_preferences:
            pref_str = f"""
            【用户投资偏好】
            - 风险偏好: {user_preferences.get('risk', 'N/A')}
            - 投资周期: {user_preferences.get('horizon', 'N/A')}
            - 偏好方向: {', '.join(user_preferences.get('style', []))}
            
            请务必在评分和选择时，优先考虑符合用户【风险偏好】和【偏好方向】的板块。
            """

        user_prompt = f"""
        {pref_str}
        
        请分析以下候选板块数据：
        {sector_details}
        
        【评分参考标准 (总分100)】
        1. 领涨力度 (30分)：'leading_count' (领涨/入围Top5次数) 越高得分越高。这是核心指标，代表资金持续攻击意愿。
        2. 趋势强度 (30分)：
           - 价格 > MA20 得满分，否则减分。
           - RSI 在 50-75 区间为强势且安全；>80 有过热风险；<40 弱势。
           - MACD 金叉或红柱放大加分。
        3. 资金与基本面 (20分)：
           - 'amount' (成交额) 越大说明流动性越好，大资金进出容易。
           - 'pct_change' (最新涨幅) 适中为宜，过高可能追高。
           - PE/PB 在合理区间。
        4. 新闻舆情 (20分)：
           - 'news_summary' 中如果有重大利好政策或行业利好，大幅加分。
           - 如果有负面消息，大幅减分。
           - 无新闻则给中性分。

        【文案输出规范】
        - **严禁**在理由或风险提示中直接出现变量名（如 'leading_count', 'ma20', 'pct_change' 等）。
        - 请使用专业的金融术语将数据转化为自然语言。
          - 例子：`leading_count=5` -> "近期5次进入市场涨幅榜前列，资金关注度极高"。
          - 例子：`pct_change=2.5` -> "今日大涨2.5%"。
          - 例子：`close > ma20` -> "股价站稳20日均线，趋势向上"。
        - 必须在推荐理由中引用相关新闻（如果有）。

        任务：
        1. 综合上述标准为**每一个**候选板块计算评分（0-100）。
        2. 为**每一个**候选板块提供简短的中文评分理由（字段名：reason）。
        3. 选出【唯一】一个最高分的板块。
        4. 生成详细的中文推荐理由和风险提示。
        
        输出格式：JSON
        约束：'selected_sector' 字段必须是 {candidate_names} 中的一个。
        约束：'sector_scores' 列表必须包含所有候选板块的评分详情，且每个项目都必须包含 'reason' 字段。
        """
        return self._call_llm_with_retry(
            system_prompt, 
            user_prompt, 
            SectorSelectionResponse, 
            valid_names=candidate_names, 
            name_field="selected_sector"
        )

    # --- Stage 3: Stock Screening ---
    def screen_stocks(self, sector_name: str, stock_data_summary: str, valid_stock_codes: List[str], user_preferences: dict = None) -> StockScreeningResponse:
        system_prompt = f"你是一名专注于 {sector_name} 板块的选股专家。请筛选出5只最具潜力的候选个股。"
        
        pref_str = ""
        if user_preferences:
            pref_str = f"""
            【用户投资偏好】
            - 风险偏好: {user_preferences.get('risk', 'N/A')}
            - 投资周期: {user_preferences.get('horizon', 'N/A')}
            
            请在筛选时，根据用户的风险偏好调整策略（例如：稳健型优先选大市值/低估值，激进型优先选高弹性/小市值）。
            """

        user_prompt = f"""
        {pref_str}
        
        板块：{sector_name}
        个股池数据（包含基本面、资金流、量价配合、近期涨停记录）：
        {stock_data_summary}
        
        任务：
        1. 筛选出 5 只最强候选股。
        2. 优先考虑资金持续流入、量价配合好、近期有涨停记录的个股。
        3. 给出中文推荐理由。
        
        输出格式：JSON
        约束：'code' 字段必须是提供的股票代码之一。必须严格返回 5 只股票。
        """
        return self._call_llm_with_retry(
            system_prompt, 
            user_prompt, 
            StockScreeningResponse, 
            valid_names=valid_stock_codes, 
            name_field="code"
        )

    # --- Stage 4: Stock Selection ---
    def select_final_stock(self, stock_details: str, candidate_codes: List[str], user_preferences: dict = None) -> StockSelectionResponse:
        system_prompt = "你是一名投资组合经理，正在做最终的买入决策。"
        
        pref_str = ""
        if user_preferences:
            pref_str = f"""
            【用户投资偏好】
            - 风险偏好: {user_preferences.get('risk', 'N/A')}
            - 投资周期: {user_preferences.get('horizon', 'N/A')}
            
            请务必基于用户的投资周期给出操作建议（例如：短线关注爆发力，长线关注基本面和估值安全边际）。
            """

        user_prompt = f"""
        {pref_str}
        
        请深度分析以下候选个股：
        {stock_details}
        
        注意：数据中包含了“news_summary”字段，请务必结合**新闻舆情**对股价的潜在影响进行评估。
        
        任务：
        1. 选出【唯一】一只最佳个股。
        2. 给出评分（0-100）、详细的中文推荐理由、风险提示和建议操作（Buy/Wait/Observe）。
        
        输出格式：JSON
        约束：'selected_stock_code' 字段必须是 {candidate_codes} 中的一个。
        """
        return self._call_llm_with_retry(
            system_prompt, 
            user_prompt, 
            StockSelectionResponse, 
            valid_names=candidate_codes, 
            name_field="selected_stock_code"
        )
