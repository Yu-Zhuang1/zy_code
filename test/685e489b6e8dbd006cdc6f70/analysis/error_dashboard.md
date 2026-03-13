# 🚨 集中错误速览 (Error Dashboard)
> **统计**: 共 5 个模块 — 🔴 致命 4 | 🟡 警告 1 | 🟢 正常 0

---

## 📋 Factor 级错误

### 🟡 `factor_common.chart_definition_stability_guard.guard`
- 🟡 警告：智能体多次生成无效Python代码（语法错误、引用未定义变量），导致不必要的工具调用失败和效率降低。

### 🔴 `factor_entertainment.chart_momentum_short_horizon.update`
- 🔴 致命：因尝试使用被安全策略禁止的代码库 (bs4) 而导致关键步骤失败，且未能正确诊断任务失败的根源在于请求了不存在的未来数据。

### 🔴 `factor_entertainment.chart_state_snapshot.anchor`
- 🔴 致命：在无法获取任何真实世界证据的情况下，完全采信了一个未来时间锚点（2026-02-04）作为分析基准，并给出了毫无根据的过高置信度，导致结论完全建立在虚构的前提上。

### 🔴 `factor_entertainment.ticketing_demand_proxy.update`
- 🔴 致命：智能体试图查询未来日期（2026-02-04）的实时票房数据，这是一个不符合现实世界逻辑且无法完成的任务，导致了必然的失败。

---

## 🧠 Expert 决策汇总

### 🔴 Expert
- 🔴 致命：专家智能体未能识别并处理子智能体之间相互矛盾的报告，盲目采信了一个基于未来日期的虚构高置信度结果，同时忽略了“榜单为年度性质”的关键事实和另外两个子智能体的执行失败信号。
