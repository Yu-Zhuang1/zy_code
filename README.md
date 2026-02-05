# zy_code_any


####Galaxy分析：

运行命令python galaxy_assistant/galaxy_main.py -b -f "test" -a "test.json" -m "openai/gpt-5.2" -fc 5 -tc 3

-b：是否批量。批量则日志路径传入任务日志文件夹的父文件夹路径，如test下面包含两个任务文件夹。不加-b则不批量，日志路径传入任务日志文件夹路径，如test/685e489b6e8dbd006cdc6f70

-f：日志文件夹路径。如果批量（有-b）则日志路径需要传入任务日志文件夹的父文件夹路径，如test，其下面包含两个任务日志文件夹。不加-b则不批量，日志路径需要传入任务日志文件夹路径，如test/685e489b6e8dbd006cdc6f70

-a：答案文件路径，需要是一个形如test.json的json文件路径，每个元素的字典至少包含'id'和'ground_truth’两个键。不传入则默认为空，分析时不参照答案。

-m：模型名称，默认"openai/gpt-5.2"

fc：处理每个任务时内部分析factor的并发数，默认为10，如果遇到并发量限制可调小。

tc：同时处理任务数量的并发数，默认为5，如果遇到并发量限制可调小。

分析报告自动保存到任务日志文件夹下面新建的analysis文件夹下，保存为.md文件。

如果想要调整指示LLM分析的重点，可以在galaxy_assistant\expert_analysis.py中的galaxy_task_analysis_prompt；以及galaxy_assistant\factor_analysis.py中的factor_analysis_prompt函数中编辑提示词。