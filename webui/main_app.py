import streamlit as st
import sys
import os
import logging
import json
import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dotenv import load_dotenv

# Ensure root directory is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
# Ensure PyInstaller extract dir is available when frozen
if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
    sys.path.append(sys._MEIPASS)

try:
    from data import get_data_provider
    from utils.indicators import calculate_technical_indicators, get_latest_indicators
    from utils.news_collector import NewsCollector
    from utils.market_scanner import MarketScanner
    from llm.analyzer import StockAnalyzer
    from llm.pipeline_analyzer import PipelineAnalyzer
    from utils.sector_analyzer import SectorAnalyzer
    
    # App specific imports
    from app.version import get_version
    from app.paths import get_user_data_dir
    from app.updater import check_for_updates
    from app.logging_setup import setup_logging
except ImportError as e:
    # Fail fast so we don't hit NameError later in the app
    st.error(f"Import Error: {e}")
    st.stop()

# Load env
load_dotenv()

# Setup logging
setup_logging()

# Set page config (Must be first Streamlit command)
st.set_page_config(
    page_title="StockLLM - 股市分析助手",
    layout="wide"
)

# Disclaimer Warning
st.warning("**风险提示**：本工具仅供辅助分析与学习，**不构成任何投资建议**。市场有风险，投资需谨慎。AI 分析结果可能存在误差，请务必结合独立思考。")

# Initialize Session State
if 'analyzed_data' not in st.session_state:
    st.session_state.analyzed_data = {} 
if 'stock_info' not in st.session_state:
    st.session_state.stock_info = {} 

# Pipeline State
if 'pipeline_stage' not in st.session_state:
    st.session_state.pipeline_stage = 0 
if 'pipeline_data' not in st.session_state:
    st.session_state.pipeline_data = {}

# --- Functions from original main.py ---

def render_market_dashboard():
    st.header("市场全景看板")
    
    scanner = MarketScanner()
    
    # --- 1. 市场概况 (指数 + 情绪) ---
    st.subheader("市场概况")
    
    # Get timestamp for market indices
    ts = scanner.get_cache_timestamp("market_indices")
    time_str = ""
    if ts:
        time_str = f" | 更新于: {datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')}"
        
    st.caption(f"数据来源: 腾讯财经 (实时){time_str}")
    with st.spinner("正在获取市场全景数据..."):
        indices = scanner.get_market_indices()
        sentiment = scanner.get_market_sentiment()
        
        # Fallback for indices
        if not indices:
            st.info("实时指数接口响应超时，尝试获取 Baostock 历史行情(T-1)...")
            provider = get_data_provider()
            indices = provider.get_market_indices()

    # Display Indices
    if indices:
        # Filter indices to display (exclude sz399106 which is only for turnover calc)
        display_indices = [idx for idx in indices if idx.get('code') != 'sz399106']
        
        cols = st.columns(len(display_indices))
        
        # Calculate Total Turnover (SH Composite + SZ Composite)
        sh_comp = next((idx for idx in indices if idx.get('code') == 'sh000001'), None)
        sz_comp = next((idx for idx in indices if idx.get('code') == 'sz399106'), None) # sz399106 is SZ Composite
        
        total_turnover = 0
        if sh_comp and sz_comp:
            total_turnover = sh_comp['turnover'] + sz_comp['turnover']
        else:
            # Fallback: Sum available indices (might be inaccurate but better than 0)
            for idx in indices:
                if 'turnover' in idx:
                    total_turnover += idx['turnover']

        for i, idx in enumerate(display_indices):
            with cols[i]:
                st.metric(
                    label=idx['name'], 
                    value=f"{idx['current']:.2f}", 
                    delta=f"{idx['pct_change']:.2f}%",
                    delta_color="inverse"
                )
        
        # Display Market Stats (Turnover + Sentiment)
        st.divider() 
        col_stats = st.columns(4)
        with col_stats[0]:
            if total_turnover > 0:
                # Convert to 100 million (Yi)
                turnover_yi = total_turnover / 100000000
                st.metric("两市成交额", f"{turnover_yi:.0f} 亿")
            else:
                st.metric("两市成交额", "N/A")
        
        with col_stats[1]:
            # Up is Red (Inverse: Positive -> Red)
            up_count = sentiment.get('up', 0)
            st.metric("上涨家数", f"{up_count}", delta=int(up_count), delta_color="inverse")
        with col_stats[2]:
            # Down is Green (Inverse: Negative -> Green)
            # We negate the count for delta to make it negative -> Green
            down_count = sentiment.get('down', 0)
            st.metric("下跌家数", f"{down_count}", delta=int(-down_count), delta_color="inverse")
        with col_stats[3]:
            # Flat is Gray (delta_color="off" or 0)
            flat_count = sentiment.get('flat', 0)
            st.metric("平盘家数", f"{flat_count}", delta=None)
        
        st.divider() 
            
    else:
        st.warning("暂无法获取指数行情。")
        st.divider() 
        
    # --- 2. 热门板块 ---
    st.subheader("热门行业板块")
    st.caption("数据来源: 腾讯财经 (ETF 代理)")
    with st.spinner("正在扫描领涨板块..."):
        sectors = scanner.get_top_sectors()
        
    if sectors:
        cols = st.columns(5)
        for i, sec in enumerate(sectors[:5]):
            with cols[i]:
                st.metric(label=sec['name'], value=f"+{sec['pct_change']:.2f}%", delta=f"{sec['pct_change']:.2f}%", delta_color="inverse")
        st.divider() 
    else:
        st.info("暂无板块数据")
        st.divider() 

    # --- 3. 涨幅榜 (ETF + 个股) ---
    col_stocks, col_etfs = st.columns(2)
    
    with col_stocks:
        st.subheader("个股涨幅榜 (Top 10)")
        st.caption("数据来源: 新浪财经")
        with st.spinner("获取个股排行..."):
            top_stocks = scanner.get_top_stocks(limit=10)
            if top_stocks:
                display_data = []
                for s in top_stocks:
                    display_data.append({
                        "代码": s['code'],
                        "名称": s['name'],
                        "最新价": s['price'],
                        "涨跌幅%": s['pct_change']
                    })
                st.dataframe(display_data, hide_index=True)
            else:
                st.info("暂无数据")

    with col_etfs:
        st.subheader("ETF 涨幅榜")
        st.caption("数据来源: 新浪财经")
        with st.spinner("获取 ETF 排行..."):
            top_etfs = scanner.get_top_etfs(limit=10)
            if top_etfs:
                display_data = []
                for s in top_etfs:
                    display_data.append({
                        "代码": s['code'],
                        "名称": s['name'],
                        "最新价": s['price'],
                        "涨跌幅%": s['pct_change']
                    })
                st.dataframe(display_data, hide_index=True)
            else:
                st.info("暂无数据")

def render_stock_analysis(provider, analyzer):
    st.header("个股深度分析")
    st.caption(f"历史数据来源: {provider.source_name}")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Stock List Input using Data Editor
        st.write("股票列表")
        
        # Initialize session state for stock list if not exists
        if 'stock_list_input' not in st.session_state:
            st.session_state.stock_list_input = [
                {"code": "600519", "active": True},
                {"code": "000858", "active": True}
            ]
            
        edited_df = st.data_editor(
            st.session_state.stock_list_input,
            column_config={
                "code": st.column_config.TextColumn("股票代码", required=True, validate="^\d{6}$"),
                "active": st.column_config.CheckboxColumn("启用", default=True)
            },
            num_rows="dynamic",
            key="stock_editor"
        )
        
        # 日期范围
        today = datetime.date.today()
        start_date = st.date_input("开始日期", today - datetime.timedelta(days=365))
        end_date = st.date_input("结束日期", today)
        
        analyze_btn = st.button("开始个股分析", type="primary")

    if analyze_btn:
        with st.spinner("正在获取数据并计算指标..."):
            # Clear previous data
            st.session_state.analyzed_data = {}
            st.session_state.stock_info = {}
            
            codes = []
            for item in edited_df:
                if item.get("active") and item.get("code"):
                    code = item["code"].strip()
                    if code:
                        codes.append(code)
            
            if not codes:
                st.warning("请在列表中添加至少一个启用的股票代码。")
            else:
                s_date_str = start_date.strftime("%Y%m%d")
                e_date_str = end_date.strftime("%Y%m%d")
                
                for stock_code in codes:
                    try:
                        # 获取股票名称
                        info = provider.get_stock_info(stock_code)
                        stock_name = info.get("name", stock_code)
                        
                        df = provider.get_daily_data(stock_code, s_date_str, e_date_str)
                        
                        if not df.empty:
                            # 计算指标
                            df = calculate_technical_indicators(df)
                            
                            # Store in session state
                            st.session_state.analyzed_data[stock_code] = df
                            st.session_state.stock_info[stock_code] = info
                    except Exception as e:
                        st.error(f"处理股票 {stock_code} 时出错: {e}")
            
            if st.session_state.analyzed_data:
                st.success(f"已成功获取 {len(st.session_state.analyzed_data)} 只股票数据。")
            else:
                st.warning("未能获取有效数据。")

    # Display Results if data exists
    if st.session_state.analyzed_data:
        # Create Tabs for each stock + Summary Tab
        stock_codes = list(st.session_state.analyzed_data.keys())
        stock_names = [st.session_state.stock_info[c].get('name', c) for c in stock_codes]
        
        tab_labels = [f"{n} ({c})" for n, c in zip(stock_names, stock_codes)]
        if len(stock_codes) > 1:
            tab_labels.insert(0, "综合对比分析")
            
        tabs = st.tabs(tab_labels)
        
        # Determine starting index for individual stocks
        start_idx = 1 if len(stock_codes) > 1 else 0
        
        # Summary Tab Logic
        if len(stock_codes) > 1:
            with tabs[0]:
                st.subheader("多股综合对比")
                
                # Comparison Table
                comp_data = []
                for code in stock_codes:
                    df = st.session_state.analyzed_data[code]
                    info = st.session_state.stock_info[code]
                    latest = df.iloc[-1]
                    pct = latest.get('pct_change', 0.0)
                    
                    comp_data.append({
                        "代码": code,
                        "名称": info.get('name'),
                        "最新价": f"{latest['close']:.2f}",
                        "涨跌幅": f"{pct:.2f}%",
                        "PE(TTM)": info.get('pe_ttm', 'N/A'),
                        "PB(MRQ)": info.get('pb_mrq', 'N/A'),
                        "RSI": f"{latest['RSI']:.1f}",
                        "MACD": f"{latest['MACD_diff']:.3f}"
                    })
                
                st.dataframe(pd.DataFrame(comp_data), hide_index=True)
                
                # Comparison Chart (Normalized)
                fig_comp = go.Figure()
                for code in stock_codes:
                    df = st.session_state.analyzed_data[code]
                    info = st.session_state.stock_info[code]
                    # Normalize to first day = 0%
                    base_price = df.iloc[0]['close']
                    norm_close = (df['close'] - base_price) / base_price * 100
                    
                    fig_comp.add_trace(go.Scatter(x=df['date'], y=norm_close, mode='lines', name=f"{info.get('name')}"))
                
                fig_comp.update_layout(title="累计收益率对比 (%)", hovermode="x unified")
                st.plotly_chart(fig_comp, use_container_width=True)
                
                # Portfolio Analysis Button
                st.subheader("AI 组合投资建议")
                if st.button("生成综合对比分析报告", type="primary"):
                    with st.spinner("AI 正在进行多维度横向评测..."):
                        # Prepare context
                        context_list = []
                        for code in stock_codes:
                            df = st.session_state.analyzed_data[code]
                            info = st.session_state.stock_info[code]
                            latest = get_latest_indicators(df)
                            context_list.append(f"""
                            股票: {info.get('name')} ({code})
                            指标: {latest}
                            估值: PE={info.get('pe_ttm')}, PB={info.get('pb_mrq')}
                            """)
                        
                        full_context = "\n---\n".join(context_list)
                        response = analyzer.analyze_portfolio(full_context)
                        st.markdown(response)

        # Individual Stock Tabs
        for i, code in enumerate(stock_codes):
            with tabs[i + start_idx]:
                df = st.session_state.analyzed_data[code]
                info = st.session_state.stock_info[code]
                
                st.subheader(f"{info.get('name')} ({info.get('code')})")
                
                latest = df.iloc[-1]
                m1, m2, m3, m4 = st.columns(4)
                pct_change = latest['pct_change'] if 'pct_change' in latest else 0.0
                m1.metric("最新收盘", f"{latest['close']:.2f}", f"{pct_change:.2f}%", delta_color="inverse")
                m2.metric("RSI (14)", f"{latest['RSI']:.2f}")
                m3.metric("MACD", f"{latest['MACD_diff']:.3f}")
                m4.metric("成交量", f"{latest['volume']/10000:.0f} 万")

                # Chart
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.03, subplot_titles=('K线 & 均线', '成交量 & MACD'), 
                                    row_width=[0.2, 0.7])

                # Candlestick
                fig.add_trace(go.Candlestick(x=df['date'],
                                open=df['open'], high=df['high'],
                                low=df['low'], close=df['close'], name='K线'), row=1, col=1)
                
                # MA
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA5'], line=dict(color='orange', width=1), name='MA5'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df['date'], y=df['MA20'], line=dict(color='blue', width=1), name='MA20'), row=1, col=1)

                # Volume
                fig.add_trace(go.Bar(x=df['date'], y=df['volume'], showlegend=False), row=2, col=1)
                
                st.plotly_chart(fig, use_container_width=True)
                
                # LLM Analysis
                st.subheader("AI 投资分析报告")
                if st.button(f"生成/更新分析报告 ({info.get('name')})", key=f"btn_report_{code}"):
                    with st.spinner(f"AI 正在分析 {info.get('name')}..."):
                        latest_indicators = get_latest_indicators(df)
                        
                        # Fetch News
                        news_col = NewsCollector()
                        stock_news = news_col.get_stock_news(info.get('name', ''))
                        news_context = "\n".join(stock_news) if stock_news else "暂无该股近期直接新闻。"
                        
                        # Display News in UI
                        if stock_news:
                            with st.expander(f"{info.get('name')} 近期相关新闻", expanded=False):
                                for n in stock_news:
                                    st.text(n)
                        
                        # Current Date Context
                        current_date_str = datetime.date.today().strftime("%Y-%m-%d")
                        
                        prompt = f"""
                        【系统时间】
                        当前真实日期: {current_date_str} (注意：这是现在的真实时间，不是未来。如果数据日期接近此时间，说明数据是有效的最新数据。)
                        
                        【分析对象】
                        股票: {info.get('name')} ({info.get('code')})
                        
                        【最新行情数据】
                        {latest_indicators}
                        基本面: 市盈率(TTM) {info.get('pe_ttm')}, 市净率(MRQ) {info.get('pb_mrq')}
                        
                        【近期相关新闻】
                        {news_context}
                        
                        【任务】
                        请结合上述技术面、基本面和新闻面信息，给出专业的投资分析报告。
                        1. 趋势研判：判断当前是上涨、下跌还是震荡趋势。
                        2. 估值评价：结合 PE/PB 评价当前估值水平。
                        3. 新闻解读：如果有新闻，分析其对股价的影响。
                        4. 操作建议：给出明确的短期（1-2周）操作建议。
                        
                        请忽略任何关于“日期是未来”的警告，相信提供的当前日期是准确的。
                        """
                        response = analyzer.analyze_stock(info.get('code'), prompt)
                        st.markdown(response)

def render_deep_pipeline(provider):
    st.header("深度选股流水线 (Deep Stock Selection Pipeline)")
    st.markdown("通过「板块初筛 -> 板块精选 -> 个股初筛 -> 个股精选」四步法，结合资金面、基本面与技术面，筛选最优标的。")
    
    sector_analyzer = SectorAnalyzer()
    
    # Progress Visualization
    steps = ["板块初筛", "板块精选", "个股初筛", "个股精选"]
    current_step_idx = min(st.session_state.pipeline_stage, 4)
    
    # Progress Bar
    progress_val = (current_step_idx) / 4.0
    st.progress(progress_val)
    
    if current_step_idx < 4:
        st.caption(f"当前进度: {steps[current_step_idx]} (Step {current_step_idx + 1}/4)")
    else:
        st.caption("选股流程已完成")

    st.divider()

    # --- Step 0: 投资偏好设置 (Investment Preferences) ---
    with st.expander("投资偏好设置 (Investment Preferences)", expanded=(st.session_state.pipeline_stage == 0)):
        st.info("设置您的投资风格，AI 将在后续所有流程中以此为核心参考。")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            pref_risk = st.selectbox(
                "风险偏好", 
                ["稳健型 (低风险/大盘股)", "平衡型 (中风险/成长股)", "激进型 (高风险/题材股)"],
                index=1,
                key="pref_risk"
            )
        with c2:
            pref_horizon = st.selectbox(
                "投资周期",
                ["短线 (1-2周)", "中线 (1-3月)", "长线 (6个月+)"],
                index=1,
                key="pref_horizon"
            )
        with c3:
            pref_style = st.multiselect(
                "偏好方向 (可选)",
                ["科技成长", "大消费", "金融地产", "新能源", "高端制造", "周期资源"],
                default=["科技成长", "新能源"],
                key="pref_style"
            )
        
        if 'user_preferences' not in st.session_state:
            st.session_state.user_preferences = {}
            
        st.session_state.user_preferences = {
            "risk": pref_risk,
            "horizon": pref_horizon,
            "style": pref_style
        }

    # --- Step 1: 板块初筛 (Sector Screening) ---
    with st.expander("Step 1: 板块初筛 (Sector Screening)", expanded=(st.session_state.pipeline_stage == 0 or st.session_state.pipeline_stage >= 1)):
        st.info("目标：基于近N日领涨排名（进入涨幅前5名次数），筛选出市场资金关注度最高的 Top 5 板块。")
        st.caption("**数据来源**: Baostock (历史日线数据) | **算法**: 统计过去 N 天内各行业 ETF 涨幅进入全市场前 5 名的频次")
        
        col_s1_1, col_s1_2 = st.columns([1, 3])
        with col_s1_1:
            lookback = st.slider("领涨统计天数 (N)", 5, 30, 10, key="pipe_lookback", help="统计过去N天内各板块进入单日涨幅前5名的次数")
        
        if st.button("开始板块初筛", key="btn_step1", disabled=(st.session_state.pipeline_stage > 0)):
            with st.spinner("正在分析全市场板块领涨数据 (Baostock)..."):
                rankings = sector_analyzer.get_sector_ranking_by_days(days=lookback, top_n=5)
                
                if not rankings:
                    st.error("未能获取板块排名数据，请检查网络或数据源。")
                    return

                top_sectors_data = []
                top_5_rankings = rankings[:5]
                
                for name, count in top_5_rankings:
                    data = sector_analyzer.get_sector_data_by_name(name)
                    if data:
                        data['leading_count'] = count
                        top_sectors_data.append(data)
                    else:
                        top_sectors_data.append({
                            "sector_name": name,
                            "leading_count": count,
                            "pct_change": 0,
                            "indicators": {}
                        })
                
                st.session_state.pipeline_data['stage1_result'] = top_sectors_data
                st.session_state.pipeline_stage = 1
                st.rerun()
                
    if st.session_state.pipeline_stage >= 1:
        res1 = st.session_state.pipeline_data.get('stage1_result', [])
        if res1:
            st.write("##### 领涨板块 Top 5")
            cols = st.columns(5)
            for i, s in enumerate(res1):
                with cols[i]:
                    display_label = s['sector_name']
                    if 'etf_code' in s:
                        display_label += f"\n({s['etf_code']})"
                        
                    st.metric(
                        label=display_label,
                        value=f"领涨 {s['leading_count']} 次",
                        delta=f"{s.get('pct_change', 0)}%",
                        delta_color="inverse"
                    )
            
            df_res1 = pd.DataFrame(res1)
            if not df_res1.empty and 'leading_count' in df_res1.columns:
                fig = go.Figure(data=[go.Bar(
                    x=df_res1['sector_name'], 
                    y=df_res1['leading_count'],
                    text=df_res1['leading_count'],
                    textposition='auto'
                )])
                fig.update_layout(title="近N日领涨次数分布", height=300)
                st.plotly_chart(fig, use_container_width=True)

    def check_and_toast_fallback(result_obj):
        if hasattr(result_obj, '_metadata'):
            meta = result_obj._metadata
            if meta.get('fallback_triggered'):
                used_model = meta.get('used_model')
                st.toast(f"原模型额度耗尽，已自动降级至 {used_model} 继续运行")

    # --- Step 2: 板块精选 (Sector Selection) ---
    if st.session_state.pipeline_stage >= 1:
        with st.expander("Step 2: 板块精选 (Sector Selection)", expanded=(st.session_state.pipeline_stage == 1 or st.session_state.pipeline_stage >= 2)):
            st.info("目标：基于基本面、资金持续流入及量价指标，利用 LLM 从 Top 5 中精选出唯一的最佳板块。")
            st.caption("**数据来源**: Baostock (量价/资金) | **算法**: LLM 综合分析板块近期表现、资金流向及市场热度，输出唯一优选")
            
            if st.button("开始板块精选", key="btn_step2", disabled=(st.session_state.pipeline_stage > 1)):
                with st.spinner("正在深度分析候选板块基本面与资金面..."):
                    candidates = st.session_state.pipeline_data.get('stage1_result', [])
                    candidate_names = [c['sector_name'] for c in candidates]
                    
                    news_col = NewsCollector()
                    for cand in candidates:
                        sector_news = news_col.get_stock_news(cand['sector_name'], limit=3)
                        cand['news_summary'] = "\n".join(sector_news) if sector_news else "暂无近期新闻"
                    
                    context_str = json.dumps(candidates, ensure_ascii=False, indent=2, default=str)
                    
                    try:
                        pipeline_llm = PipelineAnalyzer() 
                        user_prefs = st.session_state.get('user_preferences', {})
                        result = pipeline_llm.select_sector(context_str, candidate_names, user_preferences=user_prefs)
                        
                        check_and_toast_fallback(result)
                        
                        st.session_state.pipeline_data['stage2_result'] = result
                        st.session_state.pipeline_stage = 2
                        st.rerun()
                    except Exception as e:
                        st.error(f"Step 2 Analysis Failed: {e}")

            if st.session_state.pipeline_stage >= 2:
                res2 = st.session_state.pipeline_data.get('stage2_result')
                if res2:
                    st.write("### 优选板块")
                    col_res2_1, col_res2_2 = st.columns([1, 3])
                    with col_res2_1:
                        st.metric(label=res2.selected_sector, value=f"评分: {res2.score}")
                    with col_res2_2:
                        st.info(f"**推荐理由**: {res2.reason}")
                        st.warning(f"**风险提示**: {res2.risk_warning}")
                    
                    if hasattr(res2, 'sector_scores') and res2.sector_scores:
                        st.write("#### 候选板块评分详情")
                        scores_data = []
                        for s in res2.sector_scores:
                            scores_data.append({
                                "板块名称": s.name,
                                "评分": s.score,
                                "简评": s.reason
                            })
                        st.dataframe(pd.DataFrame(scores_data).sort_values(by="评分", ascending=False), hide_index=True)

    # --- Step 3: 个股初筛 (Stock Screening) ---
    if st.session_state.pipeline_stage >= 2:
        with st.expander("Step 3: 个股初筛 (Stock Screening)", expanded=(st.session_state.pipeline_stage == 2 or st.session_state.pipeline_stage >= 3)):
            st.info("目标：获取板块成分股，结合资金、量价及近期涨停记录，筛选出 5 只最强候选股。")
            
            user_prefs = st.session_state.get('user_preferences', {})
            risk_pref = user_prefs.get('risk', '平衡型')
            
            algo_logic = "按【成交额】流动性排序"
            if "激进" in risk_pref:
                algo_logic = "按【换手率】活跃度排序"
            elif "稳健" in risk_pref:
                algo_logic = "按【流通市值】规模排序"
                
            st.caption(f"**数据来源**: 东方财富 (ETF持仓) + Baostock (个股行情) | **算法**: 提取 ETF 前十大重仓 -> {algo_logic} -> LLM 结合量价形态筛选 Top 5")
            
            if st.button("开始个股初筛", key="btn_step3", disabled=(st.session_state.pipeline_stage > 2)):
                target_sector = st.session_state.pipeline_data['stage2_result'].selected_sector
                
                with st.spinner(f"正在获取 {target_sector} 板块成分股数据..."):
                    stocks = sector_analyzer.get_sector_constituents(target_sector)
                    
                    if not stocks:
                        st.warning(f"无法获取 {target_sector} 成分股，尝试使用全市场涨幅榜筛选...")
                        scanner = MarketScanner()
                        top_gainers = scanner.get_top_stocks(limit=100)
                        stocks = top_gainers
                    
                    if stocks:
                        codes = [s['code'] for s in stocks]
                        prefixed_codes = []
                        for c in codes:
                            if c.startswith('6'): prefixed_codes.append(f"sh{c}")
                            elif c.startswith('0') or c.startswith('3'): prefixed_codes.append(f"sz{c}")
                            else: prefixed_codes.append(f"sh{c}")
                        
                        scanner = MarketScanner()
                        quotes = scanner.get_quotes(prefixed_codes)
                        
                        enriched_stocks = []
                        for s in stocks:
                            c = s['code']
                            q = quotes.get(f"sh{c}") or quotes.get(f"sz{c}")
                            if q:
                                s.update(q)
                                pct = s.get('pct_change', 0)
                                s['is_limit_up'] = pct > 9.5
                                enriched_stocks.append(s)
                        
                        if enriched_stocks:
                            stocks = enriched_stocks
                    
                    if stocks:
                        sort_key = 'turnover'
                        sort_name = "成交额"
                        
                        if "激进" in risk_pref:
                            sort_key = 'turnover_rate'
                            sort_name = "换手率"
                        elif "稳健" in risk_pref:
                            sort_key = 'market_cap'
                            sort_name = "流通市值"
                            
                        stocks.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
                        stocks = stocks[:30]
                        st.toast(f"已根据您的【{risk_pref}】偏好，按【{sort_name}】筛选出前 30 只活跃个股进入 LLM 终选。")
                    
                    if stocks:
                        with st.spinner("正在分析近期涨停基因 (Baostock)..."):
                            today = datetime.date.today()
                            start_date_check = (today - datetime.timedelta(days=10)).strftime("%Y%m%d")
                            end_date_check = today.strftime("%Y%m%d")
                            
                            progress_bar = st.progress(0)
                            for i, s in enumerate(stocks):
                                try:
                                    df_hist = provider.get_daily_data(s['code'], start_date_check, end_date_check)
                                    if not df_hist.empty:
                                        limit_ups = df_hist[df_hist['pct_change'] > 9.5]
                                        s['recent_limit_up_count'] = len(limit_ups)
                                        s['recent_limit_up_dates'] = [d.strftime("%m-%d") for d in limit_ups['date']]
                                    else:
                                        s['recent_limit_up_count'] = 0
                                except Exception as e:
                                    s['recent_limit_up_count'] = 0
                                progress_bar.progress((i + 1) / len(stocks))
                            progress_bar.empty()

                    if not stocks:
                        st.error("无法获取有效个股数据。")
                    else:
                        stock_summary = json.dumps(stocks, ensure_ascii=False, indent=2)
                        valid_codes = [s['code'] for s in stocks]
                        
                        try:
                            pipeline_llm = PipelineAnalyzer() 
                            user_prefs = st.session_state.get('user_preferences', {})
                            result = pipeline_llm.screen_stocks(target_sector, stock_summary, valid_codes, user_preferences=user_prefs)
                            
                            check_and_toast_fallback(result)
                            
                            st.session_state.pipeline_data['stage3_result'] = result
                            st.session_state.pipeline_stage = 3
                            st.rerun()
                        except Exception as e:
                            st.error(f"Step 3 Analysis Failed: {e}")

            if st.session_state.pipeline_stage >= 3:
                res3 = st.session_state.pipeline_data.get('stage3_result')
                if res3:
                    st.write("##### 候选个股清单 (Top 5)")
                    cand_data = []
                    for cand in res3.candidates:
                        cand_data.append({
                            "代码": cand.code,
                            "名称": cand.name,
                            "入选理由": cand.reason
                        })
                    st.table(cand_data)

    # --- Step 4: 个股精选 (Final Selection) ---
    if st.session_state.pipeline_stage >= 3:
        with st.expander("Step 4: 个股精选 (Final Selection)", expanded=(st.session_state.pipeline_stage == 3 or st.session_state.pipeline_stage >= 4)):
            st.info("目标：对 5 只候选股进行深度技术与基本面挖掘，选出最终的 1 只标的。")
            st.caption("**数据来源**: Baostock (日线/基本面) | **算法**: 计算 RSI/MACD/KDJ 等技术指标 + 结合 PE/PB 估值 -> LLM 深度推理输出最终决策")
            
            if st.button("开始最终精选", key="btn_step4", disabled=(st.session_state.pipeline_stage > 3)):
                with st.spinner("正在进行深度挖掘 (获取日线、计算指标、搜索新闻)..."):
                    res3 = st.session_state.pipeline_data.get('stage3_result')
                    candidates = res3.candidates
                    candidate_codes = [c.code for c in candidates]
                    
                    detailed_data = []
                    today = datetime.date.today()
                    start_date = (today - datetime.timedelta(days=100)).strftime("%Y%m%d")
                    end_date = today.strftime("%Y%m%d")
                    
                    news_col = NewsCollector()
                    
                    for cand in candidates:
                        try:
                            df = provider.get_daily_data(cand.code, start_date, end_date)
                            if not df.empty:
                                df = calculate_technical_indicators(df)
                                latest = df.iloc[-1]
                                techs = {
                                    "close": latest['close'],
                                    "pct_change": latest['pct_change'] if 'pct_change' in latest else 0,
                                    "MA5": latest['MA5'],
                                    "MA20": latest['MA20'],
                                    "RSI": latest['RSI'],
                                    "MACD": latest['MACD_diff'],
                                    "KDJ": f"K:{latest.get('K',0):.1f} D:{latest.get('D',0):.1f}"
                                }
                                info = provider.get_stock_info(cand.code)
                                
                                stock_news = news_col.get_stock_news(cand.name, limit=3)
                                news_summary = "\n".join(stock_news) if stock_news else "暂无近期新闻"
                                
                                detailed_data.append({
                                    "code": cand.code,
                                    "name": cand.name,
                                    "technicals": techs,
                                    "fundamentals": {
                                        "pe": info.get('pe_ttm', 'N/A'),
                                        "pb": info.get('pb_mrq', 'N/A')
                                    },
                                    "news_summary": news_summary,
                                    "reason_step3": cand.reason
                                })
                        except Exception as e:
                            print(f"Error fetching {cand.code}: {e}")
                    
                    if not detailed_data:
                        st.error("无法获取候选股详细数据。")
                    else:
                        context_str = json.dumps(detailed_data, ensure_ascii=False, indent=2, default=str)
                        
                        try:
                            pipeline_llm = PipelineAnalyzer() 
                            user_prefs = st.session_state.get('user_preferences', {})
                            result = pipeline_llm.select_final_stock(context_str, candidate_codes, user_preferences=user_prefs)
                            
                            check_and_toast_fallback(result)
                            
                            st.session_state.pipeline_data['stage4_result'] = result
                            st.session_state.pipeline_data['stage4_detailed_data'] = detailed_data 
                            st.session_state.pipeline_stage = 4
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Step 4 Analysis Failed: {e}")

            if st.session_state.pipeline_stage >= 4:
                res4 = st.session_state.pipeline_data.get('stage4_result')
                if res4:
                    st.write("### 最终优选个股")
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.metric(
                            label=f"{res4.selected_stock_name}", 
                            value=f"{res4.selected_stock_code}",
                            delta=f"Score: {res4.score}"
                        )
                        st.info(f"建议操作: **{res4.suggested_action}**")
                    with c2:
                        st.success(f"**核心理由**: {res4.reason}")
                        st.error(f"**风险因素**: {res4.risk_factors}")
                    
                    detailed_data = st.session_state.pipeline_data.get('stage4_detailed_data', [])
                    selected_stock_data = next((d for d in detailed_data if d['code'] == res4.selected_stock_code), None)
                    
                    if selected_stock_data and selected_stock_data.get('news_summary') and selected_stock_data['news_summary'] != "暂无近期新闻":
                        with st.expander(f"{res4.selected_stock_name} 近期相关新闻"):
                            st.text(selected_stock_data['news_summary'])

def main():
    st.title("LLM 驱动的 A 股分析助手")
    
    # --- Sidebar 配置区 ---
    with st.sidebar:
        st.header("设置")
        
        st.subheader("大模型配置")
        llm_providers = {
            "Aliyun Qwen (通义千问)": {
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long", "qwen-max-latest", "qwen2.5-72b-instruct", "qwen3-max"]
            },
            "DeepSeek (深度求索)": {
                "base_url": "https://api.deepseek.com",
                "models": ["deepseek-chat", "deepseek-reasoner"]
            },
            "Moonshot (Kimi)": {
                "base_url": "https://api.moonshot.cn/v1",
                "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
            },
            "Custom (自定义)": {
                "base_url": "",
                "models": []
            }
        }
        selected_provider = st.selectbox("选择模型厂商", list(llm_providers.keys()), index=0)
        
        if selected_provider == "Custom (自定义)":
            base_url = st.text_input("Base URL", value=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"))
            model_name = st.text_input("Model Name", value=os.getenv("LLM_MODEL", "gpt-3.5-turbo"))
        else:
            provider_config = llm_providers[selected_provider]
            base_url = provider_config["base_url"]
            model_name = st.selectbox("选择模型", provider_config["models"], index=0)
            
        os.environ["LLM_BASE_URL"] = base_url
        os.environ["LLM_MODEL"] = model_name

        api_key = st.text_input("API Key", value=os.getenv("LLM_API_KEY", ""), type="password")
        if api_key:
            os.environ["LLM_API_KEY"] = api_key
            
        st.caption(f"当前使用: {selected_provider.split(' ')[0]} / {model_name}")
        st.divider()

        # --- About / Settings / Update (Added) ---
        st.subheader("关于 / 系统")
        try:
            st.text(f"版本: v{get_version()}")
            log_dir = get_user_data_dir() / "logs"
            
            with st.expander("日志与隐私"):
                st.caption(f"日志路径: {log_dir}")
                st.caption("隐私: 数据仅保存在本地配置文件中。")
            
            if st.button("导出日志 (ZIP)"):
                import shutil
                if log_dir.exists():
                    shutil.make_archive(str(log_dir / "logs_export"), 'zip', log_dir)
                    zip_path = log_dir / "logs_export.zip"
                    if zip_path.exists():
                        with open(zip_path, "rb") as f:
                            st.download_button("下载日志 ZIP", f, "logs_export.zip", "application/zip")
                            
        except Exception as e:
            st.error(f"系统模块加载失败: {e}")

    # 初始化模块
    provider = get_data_provider()
    analyzer = StockAnalyzer()

    # --- Tabs 布局 ---
    tab1, tab2, tab3 = st.tabs(["深度选股流水线", "市场看板", "个股分析"])
    
    with tab1:
        render_deep_pipeline(provider)
    with tab2:
        render_market_dashboard()
    with tab3:
        render_stock_analysis(provider, analyzer)

if __name__ == "__main__":
    main()
