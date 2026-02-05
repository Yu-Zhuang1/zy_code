# 子智能体日志分析报告（factor：`entertainment.consensus_tracker_calibration.calibrate`）

## 1) 子智能体目标与产出概述
该子智能体的分配任务是：**评估 2026-02-04（as-of）窗口内，猫眼“想看榜”7–9名在不同快照来源之间的一致性（agreement）与数据覆盖率（coverage），并给出用于下调最终置信度的校准因子**。

最终输出为一段 IR JSON（summary/data_gap/evidence/claims/signals/confidence），其中核心结论：
- **桌面端 vs 移动端/Asgard 页面在 7–9 名完全一致**；
- 但**缺少 2026-02-03 等前序日快照**、且**缺少独立第三方对 7–9 名的验证**；
- 因此建议对总体信心做**中等幅度下调**，并给出 **recommended confidence_calibration_factor ≈ 0.50**（在 claims 中提出），整体 `confidence=0.6`。

> 注意：子智能体虽然在 claims 中提出“校准因子≈0.50”，但在 signals 中并未显式输出 skill 规范里提到的 `confidence_calibration_factor` 字段，而是以文字形式给出建议。

---

## 2) 识别到的关键指标与数值（从日志提取）

### 2.1 快照一致性（agreement）
子智能体实际计算/使用的“第三方一致性”是**代理指标**：
- **`third_party_snapshot_agreement_rate = 1.0`**
  - 依据：2026-02-04 当天，
    - 桌面端 `https://www.maoyan.com/board/6`
    - 移动端 `https://m.maoyan.com/board/6`
    - 移动端 asgard `https://m.maoyan.com/asgard/board/6`
  - **7–9 名完全一致（3/3 matched）**：
    - #7《星河入梦》
    - #8《喜欢上“欠欠”的你》
    - #9《爱乐之城》

关键点：该一致性严格来说是“**跨猫眼不同端页面一致性**”，并非“独立第三方 tracker 一致性”。子智能体在 note 中明确标注了“Proxy”。

### 2.2 覆盖率（coverage）
- **`source_coverage_rate = 0.5`（Proxy）**
  - 子智能体设定一个“最小 48h lookback 预期应有 2 个日快照（2/03 与 2/04）”，但实际仅成功获取/解析到 2/04，所以覆盖率=1/2=0.5。
  - 依据：其尝试通过工具/接口获取历史快照失败（见后述 fetch_ranking_data 与搜索结果）。

### 2.3 权威校验差异率（verification discrepancy）
- **`authoritative_verification_discrepancy_rate = null`**
  - 理由：未找到独立于猫眼自身页面、且能覆盖 7–9 名的“权威核验”材料。

### 2.4 类似任务历史命中率（backtest hit rate）
- **`historical_forecast_hit_rate_on_similar_tasks = null`**
  - 理由：本次运行未提供/未能检索到 pipeline 的历史回测指标。

### 2.5 子智能体给出的总体把握度
- 输出顶层 **`confidence = 0.6`**
- 并在 claims 中给出**“建议校准因子≈0.50”**（但未作为信号字段返回）。

---

## 3) 决策依据与推理链条是否合理

### 3.1 合理之处
1. **一致性判定直接、可验证**：
   - 通过 `read_webpage` 拉取桌面/移动/Asgard 三个页面文本，三方均出现“2026-02-04更新”，并且 7–9 名一致。
   - 对“agreement=1.0（3/3）”的计算在此范围内成立。

2. **对第三方缺失与覆盖不足进行了显式降权**：
   - 发现 google_search / exa_search 未检索到可复核 7–9 名的第三方快照；
   - 同时指出抓取器 `fetch_ranking_data` 结果异常，不纳入验证证据；
   - 由此将覆盖率设为 0.5，并在 summary/claims 中建议下调整体置信度。

3. **对 proxy 使用有标注**：
   - `third_party_snapshot_agreement_rate`、`source_coverage_rate` 都明确说明是代理口径；这是合规的“缺数据时的替代策略”。

### 3.2 主要问题/偏差
1. **指标口径与技能定义存在偏离**：
   - skill 明确要求“third_party_snapshot_agreement_rate”是“primary vs third-party snapshots”的一致率。
   - 本次用“桌面 vs 移动/Asgard”替代，实质是“同一平台不同展现层”的一致性，不等同于第三方。
   - 虽然有 proxy 注释，但会导致校准结果偏乐观（agreement=1.0 但实际上没有 third-party）。

2. **覆盖率的“预期快照数”设定较武断**：
   - `source_coverage_rate=0.5`基于“至少 2 天、2 个快照”的假设。
   - skill 里要求的是“窗口内 expected snapshot timestamps 的成功解析比例”，但窗口长度/期望频率在日志中未被系统性定义（例如 lookback=7d、每日 1 次、或每日多次）。
   - 该 0.5 更像“最低限度”的启发式，而非严格的 coverage_report。

3. **最终校准因子没有按说明公式落地**：
   - 规范计算：weighted mean(calibrate signals) × coverage × (1 - discrepancy) 后 clamp。
   - 子智能体：
     - 没有输出 `confidence_calibration_factor`，只是口头建议≈0.50；
     - discrepancy 为 null，hit rate 为 null，实际应说明如何在缺项时取默认权重/忽略项；
     - 其数值（≈0.50）与给出的 `confidence=0.6` 之间也缺少明确映射关系。

4. **证据中混入“与目标 slice 无关”的材料**：
   - 读取了 PDF（生活报 2026-02-03），内容与猫眼 7–9 名快照核验关系弱，未对 calibration 贡献实质信号。

---

## 4) 工具调用质量与效果评估（含错误/异常）

### 4.1 工具选择与执行总体评价
- **核心抓取工具使用得当**：优先使用 `read_webpage` 获取静态文本（桌面/移动/Asgard），与系统指引一致。
- **检索工具用于第三方核验**：使用 `google_search` 与 `exa_search` 尝试查找第三方快照，方向正确。

### 4.2 明确的异常/失败点
1. **`fetch_ranking_data(website="maoyan_want")` 返回结构明显异常**：
   - 返回的 ranking 中出现诸如“`3 万新增想看`”作为 name，且 rank 值杂乱（47/20/13/7/3/2/1），数量只有 7 条。
   - 子智能体正确判断为“malformed / parsing instability”，并未将其当作可信第三方快照。
   - 这属于**工具/解析链路质量问题**，但子智能体处理方式合理（记录为 data_gap 并降权）。

2. **搜索结果有效性不足**：
   - google_search 最初对包含 2/04 的查询返回“no relevant”，后续改 query 才搜到新浪关于“春节档累计想看榜Top6”的文章。
   - 但该第三方文章无法覆盖 7–9 名核验需求。

3. **对“被拦截的历史 JSON 接口”未在本子任务中复现验证**：
   - 先验线索中提到 `mmdb/v1/wish.json` 返回 `wish:false`（疑似阻断），本次 calibration agent 并未再次调用该接口验证（而是通过 coverage proxy 表达“拿不到 2/03”）。
   - 不算错误，但属于“未闭环”——若能最小成本复现，会更利于解释 coverage 缺失原因。

---

## 5) 工作流程合理性检查

### 5.1 流程结构
1. **先抓取主源（猫眼三个页面）→确立 anchor 快照一致性**：合理。
2. **再用搜索尝试第三方核验→失败则记录 data_gap 并降权**：合理。
3. **尝试内部/封装抓取器 fetch_ranking_data → 发现异常 → 作为风险点记录**：合理。

### 5.2 可改进之处
- **缺少“窗口定义”与“期望快照频率”**：导致 coverage_rate 的 0.5 假设不够稳。
- **缺少轻量对齐表/结构化产物**：skill 建议形成 alignment/coverage 报告类 artifact（CSV/JSON）。本次仅在 signals 中给出结论，没有输出对齐明细（如匹配的 title-rank 列表及匹配率计算过程）。
- **未按 skill 输出 `confidence_calibration_factor`**：影响专家智能体聚合时的可用性。

---

## 6) 对专家智能体聚合的可用结论（从本子智能体角度）

### 6.1 可以直接复用的“硬信息”
- 2026-02-04（as-of）猫眼想看榜 **7–9 名在桌面、移动、Asgard 三页面一致**：
  - #7《星河入梦》
  - #8《喜欢上“欠欠”的你》
  - #9《爱乐之城》
- 跨端一致性在该 slice 上是 **100%（3/3）**。

### 6.2 需要在聚合时显式降权的原因
- **无独立第三方快照**能核验 7–9 名；检索到的媒体材料多为“春节档累计想看Top6”。
- **历史/多日覆盖不足**：至少缺 2026-02-03 的可解析快照。
- **自动抓取器 fetch_ranking_data 本次表现不稳定**。

---

## 7) 总体评价
- **关键指标抓取与一致性判定：准确且证据链清晰**。
- **对数据缺口与工具异常的风险提示：到位**。
- **主要不足在于：指标口径（third_party）与 coverage 的严格定义未完全符合技能规范、以及缺少规范要求的校准因子字段输出与结构化对齐产物**。

若要给本子智能体的执行质量打分：
- 数据抓取与核验执行：较好
- 方法学契合 skill 的程度：中等（proxy 较多、公式未落地）
- 工具链稳定性：存在明显异常（但被正确识别并隔离）