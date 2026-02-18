# StockLLM - AI 驱动的 A 股分析助手

StockLLM 是一个基于 Python 的智能股票分析工具，结合了 Streamlit 的交互式界面、Baostock 的实时数据以及大语言模型 (LLM) 的深度分析能力。它可以作为 Windows 桌面应用运行，也可以作为 Python 脚本直接运行。

## 主要功能

*   **数据源支持**: 集成 Baostock，确保数据获取的稳定性。
*   **专业技术指标**: 自动计算 MA (均线), RSI (相对强弱), MACD (平滑异同移动平均), KDJ 等核心指标。
*   **交互式图表**: 使用 Plotly 绘制专业的 K 线图和成交量图，支持缩放和平移。
*   **AI 智能分析**: 集成通义千问 (DashScope) 或 OpenAI 兼容模型，根据技术指标和新闻面提供投资建议。
*   **桌面级体验**: 提供单文件 Windows 可执行程序，开箱即用。

## 快速开始 (Windows 用户)

如果您只是想使用本软件，推荐下载最新的 Windows 可执行程序。

1.  **下载**: 前往 [Releases 页面](https://github.com/zyfan42/stock-llm/releases) 下载最新版本的 `StockLLM.exe`。
2.  **运行**: 双击 `StockLLM.exe` 启动。
3.  **配置**:
    *   首次运行时，请在设置界面或配置文件中填入您的 LLM API Key (如 DashScope/OpenAI Key)。
    *   配置文件路径: `%APPDATA%\StockLLM\config.toml`

## 开发者指南 (源码运行与构建)

> [!NOTE]
> 如果您是开发者，希望修改代码或自行构建，请按以下步骤操作。

### 环境要求

*   Python 3.10+
*   Windows 10/11 (推荐)

### 1. 安装依赖

```bash
# 创建虚拟环境 (可选)
python -m venv venv
.\venv\Scripts\Activate.ps1

# 安装项目依赖
pip install -r requirements.txt
```

### 2. 配置环境

复制 `.env.example` 为 `.env`，并配置您的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件:

```ini
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-max
```

### 3. 运行应用

> [!TIP]
> **方式一：Web 模式 (推荐开发调试)**
>
> 直接启动 Streamlit 服务，并在浏览器中访问。
>
> ```bash
> streamlit run webui/main_app.py
> ```

> [!TIP]
> **方式二：桌面模式 (测试封装效果)**
>
> 模拟打包后的桌面应用运行方式 (基于 PyWebView)。
>
> ```bash
> python -m app.main
> ```

### 4. 构建 Windows 可执行程序

> [!IMPORTANT]
> 使用 PowerShell 运行构建脚本:
>
> ```powershell
> .\scripts\build_windows.ps1
> ```
>
> 构建产物将生成在 `packaging/dist/` 目录下：
> *   `StockLLM.exe`: 单文件可执行程序

## 项目结构

*   `app/`: 桌面应用主程序及配置管理
*   `webui/`: Streamlit 界面逻辑 (`main_app.py` 为入口)
*   `data/`: 数据获取层 (AkShare/Baostock)
*   `llm/`: LLM 调用与分析逻辑
*   `utils/`: 通用工具 (指标计算、新闻收集等)
*   `scripts/`: 构建与辅助脚本
*   `packaging/`: 打包配置文件 (PyInstaller spec)

## 贡献与反馈

欢迎提 Issue、提交 PR，或基于本项目进行二次开发与其他应用场景落地。

## License

本项目采用 MIT License，详见 [LICENSE](LICENSE)。

## 免责声明

> [!WARNING]
> **本软件仅供学习和研究使用，不构成任何投资建议。**
>
> *   股市有风险，投资需谨慎。
> *   本软件提供的所有数据、分析和建议均由 AI 生成或来自第三方接口，可能存在延迟、误差或错误。
> *   开发者不对因使用本软件而产生的任何盈亏负责。
> *   请务必结合独立思考和专业机构意见进行投资决策。
