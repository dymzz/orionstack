from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RewriteRule:
    group: str
    canonical: str
    aliases: tuple[str, ...]
    expansions: tuple[str, ...] = ()
    keep_original: bool = True


@dataclass(frozen=True, slots=True)
class RewrittenQuery:
    original_text: str
    rewritten_text: str
    extra_terms: tuple[str, ...]
    intent_groups: tuple[str, ...]


REWRITE_RULES: tuple[RewriteRule, ...] = (
    RewriteRule(
        group="question",
        canonical="如何",
        aliases=(
            "怎么",
            "怎样",
            "如何",
            "该怎么",
            "该如何",
            "要怎么",
            "要如何",
            "怎么办",
            "怎么弄",
            "如何做",
            "如何操作",
            "怎么操作",
            "怎么处理",
        ),
    ),
    RewriteRule(
        group="action",
        canonical="申请",
        aliases=(
            "申请",
            "提交",
            "发起",
            "办理",
            "提报",
            "提单",
            "提交申请",
            "发起申请",
            "走流程",
            "走什么流程",
        ),
        expansions=("流程",),
    ),
    RewriteRule(
        group="entry",
        canonical="入口",
        aliases=(
            "在哪",
            "在哪里",
            "哪儿",
            "去哪",
            "去哪里",
            "入口在哪",
            "哪个模块",
            "哪个页面",
            "哪个菜单",
            "从哪进",
            "在oa哪里",
            "在系统哪里",
            "从哪里发起",
        ),
        expansions=("模块", "页面"),
    ),
    RewriteRule(
        group="query",
        canonical="查询",
        aliases=(
            "查看",
            "查询",
            "查",
            "看",
            "获取",
            "显示",
            "导出",
            "怎么看",
            "去哪看",
        ),
    ),
    RewriteRule(
        group="rule",
        canonical="规定",
        aliases=(
            "是什么",
            "什么意思",
            "怎么规定",
            "如何规定",
            "有什么要求",
            "有什么限制",
            "标准是什么",
            "条件是什么",
        ),
        expansions=("要求", "条件"),
    ),
    RewriteRule(
        group="time",
        canonical="时间",
        aliases=(
            "多久",
            "多长时间",
            "什么时候",
            "何时",
            "哪天",
            "几号",
            "何时到账",
            "什么时候发",
            "什么时候生效",
        ),
    ),
    RewriteRule(
        group="permission",
        canonical="是否允许",
        aliases=(
            "能不能",
            "可不可以",
            "可以吗",
            "是否可以",
            "能否",
            "是否允许",
            "支不支持",
            "行不行",
        ),
    ),
    RewriteRule(
        group="exception",
        canonical="异常处理",
        aliases=(
            "失败了怎么办",
            "提交不了",
            "提交失败",
            "审批卡住了",
            "被退回怎么办",
            "查不到怎么办",
            "没到账怎么办",
        ),
    ),
)

_ALIAS_TO_RULE: dict[str, RewriteRule] = {}
_SORTED_ALIASES: tuple[str, ...] = ()


def _dedupe(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item).strip().lower()
        if not value or value in seen:
            continue
        result.append(value)
        seen.add(value)
    return tuple(result)


def _normalize_text(text: str) -> str:
    return " ".join(str(text).lower().split())


def _build_alias_index() -> None:
    global _SORTED_ALIASES

    alias_to_rule: dict[str, RewriteRule] = {}
    aliases: list[str] = []
    for rule in REWRITE_RULES:
        for alias in rule.aliases:
            key = _normalize_text(alias)
            if not key:
                continue
            alias_to_rule[key] = rule
            aliases.append(key)

    _SORTED_ALIASES = tuple(sorted(set(aliases), key=len, reverse=True))
    _ALIAS_TO_RULE.update(alias_to_rule)


_build_alias_index()


def rewrite_query_for_retrieval(text: str) -> RewrittenQuery:
    original = _normalize_text(text)
    rewritten = original
    extra_terms: list[str] = []
    intent_groups: list[str] = []

    for alias in _SORTED_ALIASES:
        if alias not in rewritten:
            continue

        rule = _ALIAS_TO_RULE[alias]
        if rule.keep_original:
            extra_terms.append(alias)

        rewritten = rewritten.replace(alias, rule.canonical)
        extra_terms.append(rule.canonical)
        extra_terms.extend(rule.expansions)
        intent_groups.append(rule.group)

    rewritten = _normalize_text(rewritten)

    return RewrittenQuery(
        original_text=original,
        rewritten_text=rewritten,
        extra_terms=_dedupe(extra_terms),
        intent_groups=_dedupe(intent_groups),
    )
