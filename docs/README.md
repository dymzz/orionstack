# docs 文档目录引导

## 1. 文档目标

`/docs` 是 OrionStack 当前正式文档目录。

本文件只承担**目录导航**职责，帮助人和 AI 快速判断：

1. 当前有哪些正式文档
2. 每份文档分别负责什么
3. 应该先读哪份，再读哪份
4. 当前实现基线、后续升级基线、接入边界与文档库标准分别落在哪组文档

本文件不承担以下职责：

- 不替代 `docs/designs/1_system_design.md`
- 不替代 `docs/designs/2_system_design.md`
- 不记录逐日开发流水
- 不冻结字段契约或接口细节
- 不替代子目录中的专用 README

---

## 2. 当前目录结构总览

```text
docs/
├── README.md
├── 1_1_progress.md
├── 1_2_file_responsibilities.md
├── 1_3_field_definitions.md
├── 2_1_progress.md
├── 2_2_file_responsibilities.md
├── 2_3_field_definitions.md
├── 2_4_test_strategy.md
└── designs/
   ├── 1_system_design.md
   ├── 2_system_design.md
   ├── document_ingestion_boundary.md
   └── document_library/
      ├── README.md
      ├── phase1_document_library_fields_freeze.md
      ├── domain_general_library_v1.md
      ├── domain_hr_library_v1.md
      ├── domain_finance_library_v1.md
      ├── domain_it_library_v1.md
      ├── domain_legal_library_v1.md
      ├── domain_ops_library_v1.md
      ├── domain_product_library_v1.md
      └── domain_sales_library_v1.md
```

---

## 3. 如何理解当前 `/docs` 分层

## 3.1 主线 1：当前真实实现基线

这一组文档描述**当前已经进入默认实现链路**的系统状态。

### `docs/designs/1_system_design.md`

职责：

- 定义当前真实实现基线
- 说明当前系统定位、范围、主链路、模块边界与不做什么
- 约束当前默认运行链路

### `docs/1_1_progress.md`

职责：

- 记录主线 1 当前真实进度
- 标记已完成、进行中与下一步工作
- 防止重复扩写已完成内容

### `docs/1_2_file_responsibilities.md`

职责：

- 说明当前默认链路下的文件职责与边界
- 帮助判断某段逻辑应放在哪个现有文件

### `docs/1_3_field_definitions.md`

职责：

- 解释主线 1 当前冻结字段的语义
- 对齐请求、响应、存储与调试字段含义

---

## 3.2 主线 2：后续升级设计基线

这一组文档描述**后续升级目标**，以及第二阶段已经开始落地的过渡模块。

### `docs/designs/2_system_design.md`

职责：

- 作为第二阶段升级设计基线
- 说明 Query Planner、Knowledge Unit、Elastic lexical-only、Hybrid Retrieval、RRF、Rerank、Evidence 等目标链路
- 约束升级顺序与目标边界

### `docs/2_1_progress.md`

职责：

- 记录第二阶段从设计到最小可执行改造的推进状态
- 说明哪些能力只是目标，哪些已经开始进入仓库

### `docs/2_2_file_responsibilities.md`

职责：

- 说明第二阶段新增文件、过渡文件与预留文件位的职责边界
- 避免把第二阶段新能力重新堆回第一阶段旧文件

### `docs/2_3_field_definitions.md`

职责：

- 解释第二阶段新增字段与结构化契约
- 对齐 Query Planner、Knowledge Unit、检索信号、Rerank、Trace 等字段含义

### `docs/2_4_test_strategy.md`

职责：

- 说明第二阶段当前最小测试策略
- 区分当前可执行的 smoke / regression 与后续目标测试位
- 为已落地 phase 2 过渡模块提供最小回归保护带

### 当前第二阶段已开始落地的过渡模块

当前仓库中已经出现、并应按第二阶段语义理解的文件主要包括：

- `backend/app/storage/repositories/knowledge_unit_repo.py`
- `backend/app/retrieval/lexical_retriever.py`
- `backend/app/indexing/elastic_indexer.py`
- `backend/app/indexing/index_health_checker.py`
- `backend/app/config/settings.py` 中的第二阶段配置项
- `backend/app/services/chat_service.py` 中的第二阶段过渡接线

因此：

- 主线 2 不是“纯未来文档”
- 但也不是“已经完全切换完成的默认链路”
- 具体已落地边界，应优先看 `docs/2_1_progress.md` 与 `docs/2_2_file_responsibilities.md`

---

## 3.3 文档接入边界补充

### `docs/designs/document_ingestion_boundary.md`

职责：

- 说明原始文档如何进入下游问答链路
- 冻结 direct ingest 与 cleaning-required 的边界
- 说明 ingestion / cleaning adapter 负责什么、不负责什么

适合优先阅读的场景：

- 判断某类文档能否直接入链路
- 判断复杂文档是否必须先清洗
- 设计接入与清洗服务时收口边界

---

## 3.4 文档库标准目录

### `docs/designs/document_library/README.md`

职责：

- 作为文档库标准目录说明
- 说明文档库标准的使用范围、目录结构与分类基线

### `docs/designs/document_library/phase1_document_library_fields_freeze.md`

职责：

- 冻结第一阶段文档库最小字段基线
- 服务于文档清洗、分类、入库与引用回源

### `docs/designs/document_library/domain_*_library_v1.md`

职责：

- 定义各业务域文档库边界与收录标准
- 说明适合纳入哪些文档、不纳入哪些文档、建议如何标记

当前目录已包含的业务域：

- `general`
- `hr`
- `finance`
- `it`
- `legal`
- `ops`
- `product`
- `sales`

---

## 4. 推荐阅读路径

## 4.1 想快速了解“当前系统已经做到什么”

推荐顺序：

1. `docs/designs/1_system_design.md`
2. `docs/1_1_progress.md`
3. `docs/1_2_file_responsibilities.md`
4. `docs/1_3_field_definitions.md`

## 4.2 想继续推进“第二阶段升级”

推荐顺序：

1. `docs/designs/2_system_design.md`
2. `docs/2_1_progress.md`
3. `docs/2_2_file_responsibilities.md`
4. `docs/2_3_field_definitions.md`
5. `docs/2_4_test_strategy.md`

## 4.3 想判断“第二阶段当前应该怎么测”

推荐顺序：

1. `docs/designs/2_system_design.md`
2. `docs/2_1_progress.md`
3. `docs/2_4_test_strategy.md`

## 4.4 想判断“某项能力到底是当前默认链路，还是第二阶段过渡能力”

推荐顺序：

1. `docs/designs/1_system_design.md`
2. `docs/designs/2_system_design.md`
3. `docs/1_1_progress.md`
4. `docs/2_1_progress.md`

## 4.5 想判断“文档接入与清洗”边界

推荐顺序：

1. `docs/designs/document_ingestion_boundary.md`
2. `docs/designs/document_library/README.md`
3. `docs/designs/document_library/phase1_document_library_fields_freeze.md`
4. 对应业务域的 `domain_*_library_v1.md`

## 4.6 想判断“当前改动应该落在哪份文档”

可按以下原则判断：

- 改系统边界、模块关系、In Scope / Out of Scope  
  -> 改 `docs/designs/*system_design.md`
- 改推进状态、已完成项、下一步顺序  
  -> 改 `docs/*_1_progress.md`
- 改文件级职责边界  
  -> 改 `docs/*_2_file_responsibilities.md`
- 改字段语义解释  
  -> 改 `docs/*_3_field_definitions.md`
- 改测试分层、smoke / regression 策略  
  -> 改 `docs/*_4_test_strategy.md`
- 改原始文档接入 / 清洗边界  
  -> 改 `docs/designs/document_ingestion_boundary.md`
- 改文档库分类标准、字段冻结或业务域收录边界  
  -> 改 `docs/designs/document_library/` 下对应文档

---

## 5. 当前维护原则

### 5.1 导航文档与正文文档分离

- `docs/README.md` 只负责导航
- `docs/designs/*.md` 负责设计基线
- `docs/*_progress.md` 负责推进状态
- `docs/*_file_responsibilities.md` 负责文件边界
- `docs/*_field_definitions.md` 负责字段解释
- `docs/*_test_strategy.md` 负责测试策略

### 5.2 主线 1 与主线 2 分开维护

- 主线 1 记录当前默认实现基线
- 主线 2 记录升级目标与过渡落地状态
- 不把第二阶段内容反向写进主线 1 文档里冒充“当前默认实现”

### 5.3 接入边界与文档库标准不回写系统主设计正文

- `document_ingestion_boundary.md` 只负责接入边界
- `document_library/` 只负责文档库标准
- 它们不替代主系统设计与进度文档

### 5.4 目录导航优先保持稳定

`docs/README.md` 应优先保持：

- 目录清楚
- 分组清楚
- 阅读顺序清楚
- 交叉引用清楚

而不应继续膨胀成新的系统设计正文。

---

## 6. 一句话收口

**`/docs` 当前应理解为：以 `docs/designs/1_system_design.md` 为当前默认实现基线、以 `docs/designs/2_system_design.md` 为第二阶段升级基线、以 `document_ingestion_boundary.md` 为接入边界补充、以 `document_library/` 为文档库标准目录的正式文档入口。**
