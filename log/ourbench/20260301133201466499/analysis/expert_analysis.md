# 专家智能体执行日志分析报告（002049.SZ，预测 2026-03-02 UTC+8 成交量）

## 0. 总览结论（专家聚合是否“按技能框架”完成）
专家智能体整体遵循了技能给定管线：**guard → anchor → trend/seasonality → catalyst → market liquidity → calibrate**，并在最后给出单点数值预测：`\boxed{14962964}`。

- **优点**：
  - 因子调用顺序与覆盖面合理；关键锚定量做了**跨源校验**；更新因子均为**有界缩放**，符合“不能自由跳变”的方法论。
- **主要问题**：
  1) 最终输出只给了数字（符合用户硬要求），但专家在日志中没有展示任何**可审计的聚合计算**（例如各 scale、乘积、或任何 shrink/clip 规则）。
  2) `guard` 对“个股可交易性”证据不足仍给 `true`，偏**fail-open**；但专家没有进一步用校验因子或 verification 因子补强。

---

## 1. 子智能体输出的关键数值/指标（专家决策所用证据底座）

### 1.1 Anchor（基准成交量）
来自 `last_verified_volume_and_microtrend.anchor`：
- **anchor_volume_shares = 15,507,415**（2026-02-27）
- **volume_microtrend = +0.0141886**（约 +1.42%/交易日，log-volume Theil–Sen）
- **volume_dispersion = 0.0832050**（MAD/median）
- conf=0.76；gap：单源（yfinance）且无交易所官方 tape。

> 该 anchor 随后被 calibrate 因子强力背书（见 1.5），所以 anchor 的“可用性”在聚合中应视为较稳。

### 1.2 趋势/季节性更新（个股近端参与度）
来自 `recent_volume_trend_and_seasonality.update`：
- **bounded_update_scale = 0.9201715843**（核心输入，建议直接用于乘法）
- 解释信号：
  - **trend_signal = -1.2651**（zscore，近5 vs 前20 残差漂移）
  - **seasonality_residual = -0.7922**（zscore，近5残差水平）
- conf=0.56；关键 gap：存在 2025-12-30~2026-01-14 **zero-volume cluster**，因此施加质量收缩（w=0.7）。

### 1.3 市场系统性流动性/活跃度更新
来自 `broad_market_liquidity_and_activity_proxy.update`：
- **systemic_activity_scale = 0.98**
- **liquidity_pressure_score = -0.35**（轻度偏弱）
- **proxy_quality_score = 0.6**
- conf=0.58；gap：无 SZSE-only 成交额序列，创业板代理缺失。

> 其他分析师指出该因子内部可复算的简单均值 z 约 -0.41，而 IR 给 -0.35，存在轻微不可审计差异；但对最终 scale=0.98 的影响可能很小（本身接近中性）。

### 1.4 公司事件/公告催化（交易活跃度冲击）
来自 `company_specific_news_and_event_catalyst_intensity.update`：
- **volume_activity_impulse = 0.45**（中等偏正）
- **event_quality_score = 0.55**
- **price_direction_tilt = 0.15**（对本任务非核心）
- conf=0.57；gap：并购进展公告未完全拿到 CNINFO 原文，且存在二手页面错配风险。

### 1.5 Cross-source 校准（anchor 合理性/单位一致性）
来自 `cross_source_volume_reasonableness_check_szse.calibrate`：
- **volume_match_ratio = 0.9999990**（Eastmoney/Tencent “手→股”换算后与 Yahoo 仅差 15 股）
- **unit_mismatch_flag = false**
- **staleness_flag = false**
- conf=0.86

> 这一步显著提升了 anchor 的可信度，并削弱了 anchor 因子里“仅 yfinance”的 gap。

### 1.6 交易日/可交易性 Guard
来自 `market_calendar_and_trading_status_guard`：
- **is_trading_day_ok = true**（基于 SZSE 官方日历，证据强）
- **is_tradable_ok = true（proxy）**（证据弱：仅能证明 1/15 已复牌，缺少 3/2 前的权威状态快照）
- **is_normal_session_ok = true**（同样偏“未发现异常即正常”）
- conf=0.67；gap：无官方实时停牌/状态确认。

---

## 2. 专家智能体的聚合决策逻辑是否正确、依据是否充分

### 2.1 因子组合方式：应为乘法缩放，但专家未展示
技能指南要求：
> forecast_volume = anchor_volume × scale_trend × scale_catalyst × scale_market；并对大幅变动进行 clipping / shrink。

从日志可见专家确实获取了三类 scale 的原材料：
- `scale_trend ≈ 0.9202`
- `scale_market ≈ 0.98`
- `scale_catalyst`：未直接给出“catalyst_scale”，仅给出 `volume_activity_impulse=0.45`。

然而：
- 专家最终只输出 **14962964**，没有给出中间 scale、也没有说明 `volume_activity_impulse` 如何映射为 `scale_catalyst`（例如 1.00~1.10 之类）。
- 这使得“专家是否严格按技能框架计算”在审计层面**不可验证**。

### 2.2 用现有因子倒推专家隐含的 catalyst scale（用于检查一致性）
用技能公式反推：
- 预测/anchor 比值：14962964 / 15507415 ≈ **0.965**
- 已知 trend×market：0.9201716 × 0.98 ≈ **0.9018**
- 则隐含 catalyst_scale ≈ 0.965 / 0.9018 ≈ **1.070**

含义：专家在 trend 与市场偏弱的情况下，仍引入了约 **+7%** 的事件催化上调。

这与子智能体事件结论（“moderately positive activity impulse”）**方向一致**，且幅度属于“温和上调”，不违反“bounded update”原则。因此：
- **数值层面**：最终预测与各因子信号在量级上是可协调的。
- **证据层面**：catalyst 的证据质量中等（0.55），因此 +7% 属于相对保守。

### 2.3 Guard 处理：专家采纳了偏乐观的可交易性判断
- guard 给 `is_tradable_ok=true` 但明确写了“未获得权威实时状态快照”。
- 按技能文档“Guard fail -> NO_FORECAST”以及 guard 的性质，本应更偏保守。

不过本次 guard 并未 fail，而是“proxy true”。专家直接继续预测是符合系统总体策略（不要因软缺口拒绝），但：
- 专家**未调用** `factor_verification` 来弥补这一关键缺口。
- 这使得最终预测的置信度（如果有对外输出）应被下调；但用户强制只输出数字，专家无法表达置信区间。

### 2.4 Anchor 的可靠性处理：专家做得正确且充分
专家在初批因子后追加了 `cross_source_volume_reasonableness_check`，这是本次决策中最“关键且正确”的补强动作：
- 明确解决了 anchor 的“单源/单位”不确定性。
- 给出了 match_ratio≈1，且确认单位“手/股”转换正确。

这一步证据充分，且显著提升聚合可用性。

---

## 3. 充分性与一致性评估（子因子之间是否冲突、专家是否合理化解）

### 3.1 因子之间总体不冲突
- trend/seasonality：0.92（偏弱）
- market liquidity：0.98（轻微偏弱）
- catalyst：正向（需要上调）

组合后预测略低于 anchor（0.965×），符合“系统与个股短期走弱抵消部分事件热度”的叙事。

### 3.2 已知的局部一致性问题与专家处理
- **市场因子 liquidity_pressure_score 可复算不一致**：对最终 0.98 影响较小，专家未处理也可接受。
- **事件因子存在二手信息错配风险**：专家未显式降权；但从反推得到的 catalyst_scale≈1.07 看，专家实际没有给出很激进的上调，属于隐含的“降权处理”。
- **trend 因子 zero-volume cluster**：trend 因子自身已做 shrink（w=0.7），专家无需重复处理。

---

## 4. 对专家最终数值预测的“合理性”结论
在不考虑额外未知信息的情况下，专家给出的 **14962964** 与因子信号匹配：
- 以 2026-02-27 的 **15,507,415** 为 anchor；
- trend/seasonality 下调到约 **-8%**；
- 市场再轻微下调 **-2%**；
- 事件催化温和上调约 **+7%**；
- 合成后得到约 **-3.5%** 的净变化，落在合理范围。

因此：
- **决策方向与数值量级：基本正确且自洽**。
- **主要不足：缺少可审计的聚合过程展示；guard 的“可交易性”证据仍偏弱且未进一步 verification**。

---

## 5. 可改进点（站在“专家聚合”角度）
1. **在内部日志中记录聚合公式与中间 scale**（即使最终对用户只输出数字）：
   - 明确写出 anchor、trend_scale、market_scale、catalyst_scale，以及 clipping/shrink 规则。
2. **对 guard 的证券状态缺口**，优先用一次 verification/权威状态快照补强（尤其该标的曾在 2025-12~2026-01 停牌）。
3. **事件催化映射函数透明化**：把 `volume_activity_impulse` 映射到 `catalyst_scale` 的函数（例如 1 + 0.15×impulse 再 clip）应固定并输出到内部审计轨迹。

---

## 6. 本次专家输出的关键数字清单（便于复核）
- Anchor：15507415
- Trend/seasonality scale：0.9201715843
- Market scale：0.98
- 隐含 catalyst scale（由结果反推）：≈1.070
- 最终预测：14962964