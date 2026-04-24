# 2.9 下一条聚焦线决策（开新线，不开新阶段）

> 状态：**已决策**  
> 前置收口：`docs/2_8_smoke_results.md`、`docs/2_1_progress.md`  
> 目的：回答当前 `2_8` 收口后，下一步应该按**新线**推进还是升级为**新阶段**

---

## 1. 结论

**下一步应开 Phase 2 内的新线，不开新阶段。**

当前最合适的命名是：

**Phase 2 Provider 主链真实坏例审计与闭环线**

---

## 2. 为什么不是新阶段

判断标准不是“是否还有事可做”，而是“目标链是否发生了阶段级变化”。按这个标准，当前还不满足开新阶段的条件。

### 2.1 当前目标链没有变

`docs/designs/2_system_design.md` 定义的 Phase 2 目标链仍然成立，当前默认全开链路已经进入：

- planner
- fast track
- hybrid
- rerank / evidence
- clarification
- trace / hard cases

也就是说，下一步不是换目标架构，而是在**现有 Phase 2 架构内继续验证、审计和收口**。

### 2.2 `2_8` 刚收口，属于同一阶段内的验证闭环

`2_8` 这条线回答的是：

> 云端 `qwen-plus` 作为 planner provider，是否已经满足 `2_6 §5` 的契约债关闭要求。

当前结果已经收口：

- cloud live smoke `19/19` 全绿
- `B2` 已通过通用规则修复关闭
- `fusion_score / retrieval_score` 观测语义已拆清

所以下一步自然衔接的是：

> 在**同一个 Phase 2 主链**上继续看真实坏例，而不是定义一个新阶段目标。

### 2.3 剩余事项仍是 Phase 2 内部事项

当前剩余事项主要是：

- Provider 主链真实 bad case 审计与闭环
- 按需 API fallback（仍未作为默认服务链接入）

这两类都属于 **Phase 2 的完善/收尾/验证事项**，不是 Phase 3 级别的新目标。

---

## 3. 下一条新线建议范围

### 3.1 推荐新线

**Provider 主链真实坏例审计与闭环**

优先级：**P1**

输入：

- `backend/app/storage/retrieval_traces/retrieval_traces.jsonl`
- `backend/app/storage/hard_cases/hard_cases.jsonl`
- 云端 `qwen_api` 主链下新增 trace

目标：

- 只看当前配置的 provider 主链上的真实坏例
- 分类识别问题属于哪一层：
  - 语料缺口
  - clarification 边界
  - rerank / evidence 阈值
  - planner 真实边界
- 只允许通用修复，不允许 query 特判

### 3.2 作为第二优先级的新线

**按需 API fallback 接入线**

优先级：**P2**

说明：

- 这是 Phase 2 完整度上的剩余实现项
- 但它不是当前最有信息增益的验证线
- 应排在 provider 真实坏例审计之后

---

## 4. 显式不作为下一条线的事项

以下内容当前不应升级为主线：

- 本地 fallback 深化
- LocalRule 深化
- 单 query / 单词的补丁规则
- 围绕某个单独 hard case 的定向权重修补

---

## 5. 什么时候才算该开新阶段

只有在满足以下任一条件时，才应考虑从“新线”升级到“新阶段”：

1. `2_system_design.md` 之外出现新的目标链或新的主能力边界
2. Phase 2 目标链已经验收完成，需要进入下一个架构目标
3. 需要新增一组不属于 Phase 2 收尾性质的长期职责（例如新的产品面、独立前端检索体验层、生产级在线 fallback 体系等）

当前不满足上述条件，因此**不开新阶段**。

---

## 6. 最终决策

**现在应开新线，不开新阶段。**

下一条线按优先级排序为：

1. Provider 主链真实坏例审计与闭环
2. 按需 API fallback 接入
