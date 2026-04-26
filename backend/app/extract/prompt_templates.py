from __future__ import annotations

import json
from typing import Any

_EXTRACTION_SYSTEM_PROMPT = """\
你是一个知识抽取组件。任务是从给定的原始资料中抽取结构化的知识单元。

你可以抽取以下三类候选：

1. **faq** — 常见问答对
   格式：{"candidate_type": "faq", "question": "...", "answer": "...", "keywords": [...], "business_domain": "..."}

2. **action_link** — 原系统操作入口链接
   格式：{"candidate_type": "action_link", "label": "...", "url": "...", "resource_type": "..."}

3. **dynamic_query** — 可查询的动态状态定义
   格式：{"candidate_type": "dynamic_query", "query_key": "...", "resource_type": "...", "scope_type": "self|org|role", "allowed_roles": ["..."], "description": "..."}

已知的业务领域（business_domain）：hr / finance / admin / it / ops / legal / product / sales

规则：
1. 只从资料中抽取确实存在的知识，不编造内容
2. 每条候选必须完整填写所有字段
3. faq 的 question 应该是自然问句，answer 应该是完整回答
4. keywords 最多 5 个，必须是完整语义词
5. action_link 的 url 必须是可访问的完整 URL
6. dynamic_query 的 query_key 使用 snake_case 命名
7. 如果资料中没有可抽取的内容，返回空数组

输出格式（严格 JSON，不要任何前后缀文字）：
{
  "candidates": [...]
}
"""

FAQ_EXTRACTION_HINT = """\
请重点从以下资料中抽取 FAQ 问答对。每个 FAQ 应包含：
- question: 用户可能问的自然语言问题
- answer: 从资料中提取的完整回答
- keywords: 3-5 个关键词
- business_domain: 从 [hr, finance, admin, it, ops, legal, product, sales] 中选择最匹配的
"""

ACTION_LINK_EXTRACTION_HINT = """\
请重点从以下资料中抽取系统操作入口链接。每个 ActionLink 应包含：
- label: 中文标签，如"去请假系统"
- url: 完整的 URL 地址
- resource_type: 资源类型标识，如 leave_form / expense_form / attendance_record
"""

DYNAMIC_QUERY_EXTRACTION_HINT = """\
请重点从以下资料中抽取可查询的动态状态定义。每个 DynamicQuery 应包含：
- query_key: snake_case 查询标识，如 leave_status / expense_status
- resource_type: 对应的资源类型
- scope_type: self（仅自己）/ org（组织）/ role（角色）
- allowed_roles: 当 scope_type 为 role 时填写允许执行的角色；其他范围可为空数组
- description: 中文说明
"""


def build_extraction_messages(
    raw_content: str,
    candidate_types: list[str] | None = None,
) -> list[dict[str, str]]:
    hints: list[str] = []
    types = candidate_types or ["faq", "action_link", "dynamic_query"]

    if "faq" in types:
        hints.append(FAQ_EXTRACTION_HINT)
    if "action_link" in types:
        hints.append(ACTION_LINK_EXTRACTION_HINT)
    if "dynamic_query" in types:
        hints.append(DYNAMIC_QUERY_EXTRACTION_HINT)

    hint_text = "\n".join(hints)
    user_content = f"{hint_text}\n\n--- 资料开始 ---\n{raw_content}\n--- 资料结束 ---"

    return [
        {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def parse_extraction_response(content: str) -> list[dict[str, Any]]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []

    candidates = payload.get("candidates", [])
    if not isinstance(candidates, list):
        return []

    return candidates
