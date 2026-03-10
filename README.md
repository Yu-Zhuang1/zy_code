# zy_code

多智能体日志分析工具集，用于对 LLM-Agent 任务执行日志进行结构化分析和质量评估。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                      Shell Scripts                       │
│  run_galaxy_mytest_all.sh / script.sh                   │
└──────────────────────┬──────────────────────────────────┘
                       │ uv run
┌──────────────────────▼──────────────────────────────────┐
│              Analysis Pipelines (入口层)                  │
│  galaxy_main.py │ shiyu_main.py │ miroflow_main.py      │
└──────┬──────────────┬──────────────────┬────────────────┘
       │              │                  │
┌──────▼──────┐ ┌─────▼──────┐ ┌────────▼────────┐
│   Galaxy    │ │   Shiyu    │ │    MiroFlow     │
│ expert_     │ │ expert_    │ │ log_analysis.py │
│ analysis.py │ │ analysis.py│ │ log_process.py  │
│ factor_     │ │ factor_    │ │ log_compression │
│ analysis.py │ │ analysis.py│ │ _rules.py       │
│             │ │ log_       │ │                 │
│             │ │ compression│ │                 │
│             │ │ .py        │ │                 │
└──────┬──────┘ └─────┬──────┘ └────────┬────────┘
       │              │                  │
┌──────▼──────────────▼──────────────────▼────────────────┐
│                  共享基础设施层                            │
│  llm_client.py  │  schema.py  │  utils/                  │
│  (LLM 调用 +    │  (Pydantic  │  (file_utils.py +        │
│   联网搜索 +     │   结构化输出) │   serper_client.py)     │
│   结构化输出)    │             │                          │
└─────────────────────────────────────────────────────────┘
```

### 核心模块说明

| 模块 | 职责 |
|------|------|
| `llm_client.py` | 统一 LLM 调用接口，支持 chat / chat_structured / chat_stream，内置联网搜索（Serper）、Tool Loop、空响应自动重试、reasoning_effort 参数 |
| `schema.py` | Pydantic 结构化输出模型（`MarkdownResponse` 等） |
| `utils/file_utils.py` | JSONL/JSON/Markdown 文件读写 |
| `utils/serper_client.py` | Serper Web Search API 封装 |
| `shiyu_assistant/log_compression.py` | 日志压缩引擎（Section Budget、Key Field Hit Rate、Backfill） |

### 分析流程

```
日志输入 (JSONL/JSON)
  → 日志压缩 (section budgets + key field 保留)
  → Prompt 构建 (system + compressed log)
  → LLM 调用 (可选联网搜索验证事实)
  → 结构化输出 (MarkdownResponse)
  → 生成 analysis/ 目录 (factor 报告 + expert 报告)
```

## 环境准备

1. Python 3.10+，推荐使用 [uv](https://github.com/astral-sh/uv)
2. 安装依赖：`uv sync`
3. 在项目根目录创建 `.env`：

```env
OPENROUTER_BASE_URL=<your-openrouter-base-url>
OPENROUTER_API_KEY=<your-api-key>
SERPER_API_KEY=<your-serper-key>
```

可选环境变量：
- `LLM_TIMEOUT_SECONDS`（默认 10800）
- `LLM_CLIENT_MAX_RETRIES`（默认 2）
- `WEB_SEARCH_TOOL_TYPE`（默认 `web_search,web_search_preview`）

## Shell 脚本

### `run_galaxy_mytest_all.sh` — 批量分析

遍历 `log/mytest/` 下所有子文件夹，逐个跑 Galaxy 批量分析：

```bash
./run_galaxy_mytest_all.sh                    # 默认分析 log/mytest/
./run_galaxy_mytest_all.sh log/ourbench       # 指定目标目录
MODEL=openai/gpt-5.2 ./run_galaxy_mytest_all.sh  # 自定义模型
```

支持的环境变量覆盖：
- `MODEL`（默认 `google/gemini-2.5-pro`）
- `FACTOR_CONCURRENCY`（默认 5）
- `TASK_CONCURRENCY`（默认 3）
- `REASONING_EFFORT`（默认 `low`）

### `script.sh` — 单目录分析

只分析指定的单个目录（当前配置为 `log/mytest/0311_2`），用于快速测试：

```bash
./script.sh
```

## Galaxy 分析

入口：`galaxy_assistant/galaxy_main.py`

```bash
# 单任务
uv run galaxy_assistant/galaxy_main.py -f "log/ourbench/20260301133201374226" -m "google/gemini-2.5-pro" --reasoning-effort low

# 批量任务
uv run galaxy_assistant/galaxy_main.py -b -f "log/ourbench" -m "google/gemini-2.5-pro" -fc 5 -tc 3 --reasoning-effort low
```

参数：
- `-b, --batch`：批量模式（遍历 `-f` 下子目录）
- `-f, --folder`：日志目录（必填）
- `-a, --answers`：答案文件（可选，json，至少含 `id` 和 `ground_truth`）
- `-m, --model`：模型名，默认 `google/gemini-2.5-pro`
- `-re, --reasoning-effort`：`low` / `medium` / `high`
- `-fc, --factor-concurrency`：单任务内 factor 并发，默认 10
- `-tc, --task-concurrency`：批量任务并发，默认 5
- `-s, --if_shiyudev`：启用 shiyu_dev 风格提示词

输出：每个任务目录下生成 `analysis/`，包含 factor 分析报告与 `expert_analysis.md`

## MiroFlow 分析

入口：`miroflow_assistant/miroflow_main.py`

```bash
# 单文件
uv run miroflow_assistant/miroflow_main.py test/long_text.json --model "google/gemini-2.5-pro" --reasoning-effort low

# 批量目录
uv run miroflow_assistant/miroflow_main.py test --parallel --concurrency 5 --model "google/gemini-2.5-pro" --reasoning-effort low
```

参数：
- `path`：json 日志文件或目录路径
- `--parallel`：目录并行处理开关
- `--concurrency`：并发数，默认 5
- `--model`：模型名
- `--answer_file`：答案文件（可选）

输出：与输入 json 同目录生成 `*_analysis.md` 和 `*_compression_report.md`

## Shiyu 分析

入口：`shiyu_assistant/shiyu_main.py`

```bash
# 单任务
uv run shiyu_assistant/shiyu_main.py -f "test/shiyu_log" -m "google/gemini-2.5-pro" --reasoning-effort low

# 批量任务
uv run shiyu_assistant/shiyu_main.py -b -f "test" -m "google/gemini-2.5-pro" -fc 5 -tc 3 --reasoning-effort low
```

参数与 Galaxy 基本一致。

输出：每个任务目录下生成 `analysis/`，包括 factor/expert 分析及压缩报告

## 目录说明

```
zy_code/
├── galaxy_assistant/        # Galaxy 分析链路
│   ├── galaxy_main.py       # 入口
│   ├── expert_analysis.py   # Expert 分析 & 流程编排
│   ├── factor_analysis.py   # Factor 分析（含错误容忍）
│   └── answer_process.py    # 答案处理
├── shiyu_assistant/         # Shiyu 分析链路
│   ├── shiyu_main.py
│   ├── expert_analysis.py
│   ├── factor_analysis.py
│   ├── log_compression.py   # 日志压缩引擎（共享）
│   └── compression_report.py
├── miroflow_assistant/      # MiroFlow 分析链路
│   ├── miroflow_main.py
│   ├── log_analysis.py
│   ├── log_process.py
│   └── log_compression_rules.py
├── shiyu_dev_assistant/     # Shiyu 日志预处理工具
│   └── document_process.py
├── utils/                   # 共享工具
│   ├── file_utils.py
│   └── serper_client.py
├── llm_client.py            # 统一 LLM 客户端
├── schema.py                # Pydantic 数据模型
├── run_galaxy_mytest_all.sh # 批量分析脚本
├── script.sh                # 单目录分析脚本
├── log/                     # 运行输出
└── test/                    # 样例与测试数据
```
