from __future__ import annotations


QUESTION_PREFIXES: tuple[str, ...] = (
    "请问",
    "我想问一下",
    "我想问",
    "想问一下",
    "想问",
    "咨询一下",
    "咨询下",
    "咨询",
    "怎么",
    "怎样",
    "如何",
    "该怎么",
    "该如何",
    "要怎么",
    "要如何",
)

QUESTION_SUFFIXES: tuple[str, ...] = (
    "怎么办",
    "怎么操作",
    "如何操作",
    "怎么处理",
    "如何处理",
    "怎么弄",
    "怎么搞",
    "怎么申请",
    "如何申请",
    "在哪看",
    "去哪看",
)

GENERIC_FUNCTION_TERMS: frozenset[str] = frozenset(
    {
        "怎么",
        "怎样",
        "如何",
        "请问",
        "吗",
        "呢",
        "呀",
        "啊",
        "吧",
        "下",
        "一下",
    }
)
