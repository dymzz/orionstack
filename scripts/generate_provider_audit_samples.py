from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.api.routes import chat as chat_route  # noqa: E402
from app.schemas.request import ChatAskRequest  # noqa: E402


SAMPLES: list[tuple[str, str]] = [
    # ── HR ──────────────────────────────────────────────────────────────────
    ("direct", "如何申请年假"),
    ("direct", "病假材料"),
    ("direct", "请假进度怎么看"),
    ("direct", "考勤异常怎么申诉"),
    ("direct", "入职第一天需要办理什么手续"),
    ("direct", "离职流程怎么走"),
    ("direct", "在职证明怎么申请"),
    ("direct", "公司福利信息在哪里查看"),
    ("direct", "调休余额在哪里看"),
    ("direct", "试用期考核结果在哪里确认"),
    ("clarification", "请假"),
    ("clarification", "怎么请假"),
    ("clarification", "如何请假"),
    ("clarification", "什么叫请假"),
    ("clarification", "请假流程"),
    ("boundary", "请假咋整"),
    ("boundary", "什么叫HR"),
    ("boundary", "如何年假"),
    ("boundary", "何年假"),
    # ── IT ──────────────────────────────────────────────────────────────────
    ("direct", "系统权限"),
    ("direct", "如何申请系统权限开通"),
    ("direct", "VPN无法连接怎么办"),
    ("direct", "如何安装办公软件"),
    ("direct", "新电脑怎么申请"),
    ("direct", "电脑故障怎么报修"),
    ("direct", "忘记登录密码怎么办"),
    ("direct", "账号被锁定后怎么处理"),
    ("direct", "共享盘没有权限怎么办"),
    ("direct", "邮箱签名怎么修改"),
    ("direct", "收不到验证码怎么办"),
    ("direct", "打印机无法使用怎么办"),
    ("boundary", "公司 Wi-Fi 怎么连接？"),
    ("boundary", "Vpn无法连接"),
    ("boundary", "vpn无法连接'"),
    # ── Admin ───────────────────────────────────────────────────────────────
    ("direct", "门禁权限怎么申请"),
    ("direct", "会议室怎么预订"),
    ("direct", "访客来访需要怎么登记"),
    ("direct", "办公用品怎么申领"),
    ("direct", "工位怎么申请或调整"),
    ("direct", "工牌丢了怎么补办"),
    ("direct", "快递收发在哪里处理"),
    ("direct", "停车位怎么申请"),
    ("direct", "名片怎么申请"),
    ("direct", "办公区设备报修怎么提"),
    ("direct", "前台电话或服务入口在哪里看"),
    # ── Finance ─────────────────────────────────────────────────────────────
    ("direct", "如何提交日常报销"),
    ("direct", "报销需要上传什么票据"),
    ("direct", "差旅报销怎么提交"),
    ("direct", "报销流程"),
    ("direct", "报销单据怎么提交"),
    ("direct", "付款申请提交后在哪里查看进度"),
    ("direct", "借款申请怎么走"),
    ("direct", "发票抬头和税号在哪里查看"),
    ("direct", "报销被退回后怎么处理"),
    ("direct", "工资条在哪里查看"),
    ("direct", "个税信息在哪里查看"),
    ("direct", "对公付款需要准备哪些材料"),
    ("direct", "备用金怎么申请或核销"),
    ("clarification", "报销"),
    # ── Ops ─────────────────────────────────────────────────────────────────
    ("direct", "服务告警在哪里查看"),
    ("direct", "值班安排在哪里确认"),
    ("direct", "生产变更需要怎么申请"),
    ("direct", "发布窗口在哪里查看"),
    ("direct", "环境异常应该先看什么"),
    ("direct", "工单处理进度在哪里看"),
    ("direct", "日志应该去哪里查看"),
    ("direct", "服务状态页在哪里查看"),
    ("direct", "回滚方案一般在哪里填写"),
    ("direct", "资源申请需要提交什么信息"),
    ("direct", "备份恢复申请怎么提"),
    ("direct", "事故复盘记录在哪里看"),
    # ── Legal ───────────────────────────────────────────────────────────────
    ("direct", "合同送审在哪里提交"),
    ("direct", "用章申请怎么走"),
    ("direct", "NDA 模板在哪里获取"),
    ("direct", "法务咨询应该找谁"),
    ("direct", "哪些合同必须走法务审批"),
    ("direct", "合同审批一般需要多久"),
    ("direct", "合规问题应该怎么上报"),
    ("direct", "印章丢了怎么办"),
    ("direct", "保密协议到期了需要续签吗"),
    ("direct", "外部律师怎么申请"),
    ("direct", "知识产权归属问题怎么确认"),
    ("direct", "数据使用合规要求有哪些"),
    ("clarification", "合同"),
    # ── Product ─────────────────────────────────────────────────────────────
    ("direct", "产品需求应该在哪里提交"),
    ("direct", "版本计划在哪里查看"),
    ("direct", "功能上线后怎么反馈问题"),
    ("direct", "某个功能的定位是什么"),
    ("direct", "缺陷应该怎么提"),
    ("direct", "需求评审流程是什么"),
    ("direct", "上线验收需要做什么"),
    ("direct", "发布说明模板在哪里"),
    ("direct", "需求优先级怎么定的"),
    ("direct", "版本回滚怎么操作"),
    ("direct", "产品术语表在哪里查看"),
    ("direct", "某个模块的负责人是谁"),
    ("clarification", "需求"),
    # ── Sales ───────────────────────────────────────────────────────────────
    ("direct", "报价申请在哪里提交"),
    ("direct", "销售合同应该怎么走审批"),
    ("direct", "演示资料在哪里找"),
    ("direct", "商机信息填到哪里"),
    ("direct", "客户问题该找谁支持"),
    ("direct", "CRM 使用说明在哪里"),
    ("direct", "报价审批流程是什么"),
    ("direct", "销售资料目录在哪里"),
    ("direct", "客户拜访记录模板在哪里"),
    ("direct", "合同模板在哪里获取"),
    ("direct", "内部支持联系人清单在哪里看"),
    ("direct", "价格口径在哪里确认"),
    ("clarification", "报价"),
    # ── cross-domain / generic ──────────────────────────────────────────────
    ("clarification", "账号"),
    ("clarification", "密码"),
    ("boundary", "怎么提交申请"),
    ("direct", "如何上传文档？"),
]


def main() -> None:
    status_counter: Counter[str] = Counter()
    router_counter: Counter[str] = Counter()
    fallback_counter: Counter[str] = Counter()

    print("[orionstack] generate provider audit samples")
    print(f"[orionstack] total samples={len(SAMPLES)}")

    for category, query in SAMPLES:
        response = chat_route.ask_chat(ChatAskRequest(raw_query=query, debug=True))
        debug_info = response.debug_info
        status_counter[response.response_status] += 1
        router_used = "" if debug_info is None else debug_info.router_used
        if router_used:
            router_counter[router_used] += 1
        fallback_reason = None if debug_info is None else debug_info.fallback_reason
        if fallback_reason:
            fallback_counter[fallback_reason] += 1

        citations = ",".join(c.citation_id for c in response.citations) or "-"
        print(
            "[sample] "
            f"{category:13} | {query:16} | {response.response_status:8} | "
            f"{router_used or '-':22} | "
            f"{(debug_info.retrieval_mode if debug_info else '-') or '-':14} | "
            f"{fallback_reason or '-':32} | {citations}"
        )

    print("[orionstack] status=", dict(status_counter))
    print("[orionstack] router_used=", dict(router_counter))
    print("[orionstack] fallback_reason=", dict(fallback_counter))


if __name__ == "__main__":
    main()
