"""Seed a test SourceRecord with a policy document for extraction pipeline validation.

Run: python -m scripts.seed_test_source_record
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.storage.models.source_record import SourceRecord
from app.storage.repositories.source_record_repo import SourceRecordRepo

POLICY_TEXT = """\
员工考勤与请假管理制度（2026年版）

一、总则

本制度适用于公司全体正式员工，旨在规范考勤管理与请假流程。

二、考勤规定

1. 工作时间为每周一至周五，上午 9:00 至下午 18:00，午休 12:00-13:00。
2. 员工须在每日上班时签到、下班时签退，迟到超过 30 分钟视为旷工半天。
3. 月累计迟到 3 次及以上，扣减当月全勤奖。
4. 因公外出需提前在 OA 系统提交外出申请，经直属上级批准后生效。

三、请假类型与天数

1. 年假：入职满 1 年享有 5 天年假，满 3 年享有 10 天，满 5 年及以上享有 15 天。年假当年未休完可结转至次年一季度，逾期作废。
2. 病假：凭二级以上医院开具的病假证明申请，每年累计不超过 30 天。病假期间按基本工资的 80% 发放。
3. 事假：需提前 3 个工作日申请，每年累计不超过 10 天。事假期间无薪。
4. 调休：周末或法定节假日加班可申请调休，调休须在 3 个月内使用。
5. 婚假：法定 3 天，晚婚（男满 25 周岁、女满 23 周岁）额外增加 7 天。
6. 产假：女员工享受 158 天产假，男员工享受 15 天陪产假。
7. 丧假：直系亲属去世可请 3 天丧假。

四、请假审批流程

1. 1 天以内（含 1 天）：直属上级审批。
2. 1 天以上至 3 天：直属上级审批 + 部门经理审批。
3. 3 天以上：直属上级 + 部门经理 + HR 审批。
4. 所有请假须在 Odoo 系统中提交，审批通过后自动同步考勤。

五、报销规定

1. 差旅报销：出差产生的交通、住宿费用，须在返程后 5 个工作日内提交报销申请，附发票原件。
2. 日常报销：办公用品、通讯费等，每月 25 日前集中提交。
3. 报销审批：500 元以下部门经理审批，500 元以上需财务总监审批。
4. 报销到账：审批通过后 10 个工作日内打款至工资卡。

六、CRM 客户管理

1. 所有客户信息须录入 Odoo CRM 系统，包括联系人、商机金额、预计成交日期。
2. 商机阶段分为：初步接触、需求确认、方案报价、谈判中、成交/失败。
3. 每周须更新商机状态，月度复盘由销售总监主持。
4. 成交客户须在 3 个工作日内完成合同签署并归档。
"""


def main() -> None:
    repo = SourceRecordRepo()

    record = SourceRecord(
        source_record_id="sr-policy-attendance-leave-2026",
        tenant_id="default",
        source_system="internal_wiki",
        source_object_type="policy_doc",
        external_id="policy-attendance-2026",
        source_locator="wiki://policies/attendance-leave-2026",
        title="员工考勤与请假管理制度（2026年版）",
        raw_content=POLICY_TEXT,
        content_hash=SourceRecord.compute_content_hash(POLICY_TEXT),
        source_updated_at="2026-01-15T00:00:00Z",
        export_batch_id="batch-policy-seed",
        access_scope="internal",
        status="active",
        synced_at="2026-04-23T00:00:00Z",
    )

    repo.upsert(record)
    print(f"[seed] {record.source_record_id}: {record.title}")
    print(f"       raw_content length: {len(record.raw_content)} chars")
    print(f"       content_hash: {record.content_hash}")

    got = repo.get(record.source_record_id)
    assert got is not None, "Upsert failed"
    print(f"[verify] read back OK, content matches: {got.raw_content == POLICY_TEXT}")


if __name__ == "__main__":
    main()
