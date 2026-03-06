# zy_code

多智能体日志分析工具集，当前包含三条分析链路：
- `galaxy_assistant`：Galaxy 风格任务日志分析
- `miroflow_assistant`：MiroFlow JSON 日志分析（已接入结构化压缩）
- `shiyu_assistant`：Shiyu 风格任务日志分析（新增完整分析模块）

## 1. 环境准备

1. Python 3.10+
2. 安装依赖（按你本地项目方式安装）
3. 在项目根目录放置 `.env`

`.env` 至少需要：
- `OPENROUTER_BASE_URL`
- `OPENROUTER_API_KEY`

可选：
- `LLM_TIMEOUT_SECONDS`（默认 10800）
- `LLM_CLIENT_MAX_RETRIES`（默认 2）
- `WEB_SEARCH_TOOL_TYPE`（默认 `web_search,web_search_preview`）

## 2. Galaxy 分析

入口：`galaxy_assistant/galaxy_main.py`

单任务：
```bash
python galaxy_assistant/galaxy_main.py -f "log/ourbench/20260301133201374226" -m "google/gemini-2.5-pro" --reasoning-effort low
```

批量任务：
```bash
python galaxy_assistant/galaxy_main.py -b -f "log/ourbench" -m "google/gemini-2.5-pro" -fc 5 -tc 3 --reasoning-effort low
```

参数：
- `-b, --batch`：批量模式（遍历 `-f` 下子目录）
- `-f, --folder`：日志目录（必填）
- `-a, --answers`：答案文件（可选，json，至少含 `id` 和 `ground_truth`）
- `-m, --model`：模型名，默认 `google/gemini-2.5-pro`
- `-fc, --factor-concurrency`：单任务内 factor 并发，默认 10
- `-tc, --task-concurrency`：批量任务并发，默认 5
- `-s, --if_shiyudev`：启用 shiyu_dev 风格提示词

输出：
- 每个任务目录下生成 `analysis/`
- 包含 factor 分析与 `expert_analysis.md`

## 3. MiroFlow 分析

入口：`miroflow_assistant/miroflow_main.py`

单文件：
```bash
python miroflow_assistant/miroflow_main.py test/long_text_C3FBBFA9-1F78-40CE-A535-E3B662A5DC24.json --model "google/gemini-2.5-pro" --reasoning-effort low
```

批量目录：
```bash
python miroflow_assistant/miroflow_main.py test --parallel --concurrency 5 --model "google/gemini-2.5-pro" --reasoning-effort low
```

参数：
- `path`：json 日志文件或目录路径
- `--parallel`：目录并行处理开关
- `--concurrency`：并发数，默认 5
- `--model`：模型名，默认 `google/gemini-2.5-pro`
- `--answer_file`：答案文件（可选）

输出：
- 与输入 json 同目录生成：
- `*_analysis.md`
- `*_compression_report.md`

## 4. Shiyu 分析

入口：`shiyu_assistant/shiyu_main.py`

单任务：
```bash
python shiyu_assistant/shiyu_main.py -f "test/shiyu_log" -m "google/gemini-2.5-pro" --reasoning-effort low
```

批量任务：
```bash
python shiyu_assistant/shiyu_main.py -b -f "test" -m "google/gemini-2.5-pro" -fc 5 -tc 3 --reasoning-effort low
```

参数与 Galaxy 基本一致，另外支持：
- `-re, --reasoning-effort`：传给 `LLMClient` 的 reasoning effort （可选项`low`、`medium`、`high`）

输出：
- 每个任务目录下生成 `analysis/`
- 包括 factor/expert 分析及压缩报告

## 5. LLMClient 能力（已合并）

`llm_client.py` 当前为并集接口：
- 支持 `reasoning_effort`
- 支持 timeout / retry 环境变量
- 支持 `use_web_search=True` 及搜索工具类型回退

## 6. 目录说明

- `galaxy_assistant/`：Galaxy 分析逻辑
- `miroflow_assistant/`：MiroFlow 分析逻辑
- `shiyu_assistant/`：Shiyu 分析逻辑
- `shiyu_dev_assistant/`：Shiyu 日志预处理工具
- `test/`：样例与测试数据
- `log/`：运行输出目录
