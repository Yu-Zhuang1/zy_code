# zy_code_any


####Galaxy分析：

运行命令python galaxy_assistant/galaxy_main.py -b -f "test" -a "test.json" -m "openai/gpt-5.2" -fc 5 -tc 3

-b：是否批量。

-f：日志文件夹路径。如果批量（有-b）则日志路径需要传入任务日志文件夹的父文件夹路径，如test，其下包含两个任务日志文件夹。不加-b则不批量，日志路径需要传入任务日志文件夹路径，如test/685e489b6e8dbd006cdc6f70

-a：答案文件路径，需要是一个形如test.json的json文件路径，每个元素的字典至少包含'id'和'ground_truth’两个键。不传入则默认为空，分析时不参照答案。

-m：模型名称，默认"openai/gpt-5.2"

fc：处理每个任务时内部分析factor的并发数，默认为10，如果遇到并发量限制可调小。

tc：同时处理任务数量的并发数，默认为5，如果遇到并发量限制可调小。

分析报告自动保存到任务日志文件夹下面新建的analysis文件夹下，保存为.md文件。

如果想要调整指示LLM分析的重点，可以在galaxy_assistant\expert_analysis.py中的galaxy_task_analysis_prompt；以及galaxy_assistant\factor_analysis.py中的factor_analysis_prompt函数中编辑提示词。


####MiroFlow分析：
运行命令：
python miroflow_assistant/miroflow_main.py test --parallel --concurrency 10 --model "openai/gpt5.2"
python miroflow_assistant/miroflow_main.py test\long_text_8D33B3FB-6CB4-4133-BA1F-98B8242BC7BB.json --model "openai/gpt-5.2"

--parallel：是否批量，若省略，则传入的路径应当是单独的json日志文件路径；若不省略，则传入的路径应当是文件夹路径，文件夹下应包含需要分析的日志文件。生成的分析报告将保存在日志相同目录下。

--concurrency：批量模式并发数，默认为5

--model：模型名称，默认为"openai/gpt-5.2"

支持超长日志（4万+行），消息记录截断长度参数可在miroflow_assistant\log_process.py中自行调整，分为普通和激进模式。

生成的分析报告将保存在日志相同目录下。

如果希望调整报告的分析内容，可在miroflow_assistant\log_analysis.py的analysis_prompt函数中自行调整提示词。