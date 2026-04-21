"""Probe local llama-server to see the raw content it returns.

Replicates the exact request QwenApiProvider sends (system prompt, temperature,
max_tokens, response_format) and prints the un-sanitized content so we can see
what the parser is actually receiving. Uses Settings() so it reads the same
.env / environment that the backend would.

Usage:
    uv run python scripts/probe_llama_server.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402

from app.config.settings import Settings  # noqa: E402
from app.query.providers.qwen_api_provider import _SYSTEM_PROMPT  # noqa: E402


QUERIES = [
    "系统权限",                      # A1: failed with empty content
    "如何申请年假",                  # C1: truncated at char 44
    "请假审批进度在哪里查看",        # A3: failed with empty content
    "报销流程",                      # A4: passed (control)
]


def main() -> None:
    s = Settings()
    base = s.qwen_api_base.rstrip("/")
    url = f"{base}/chat/completions"
    print(f"api_base = {base}")
    print(f"api_model = {s.qwen_api_model}")
    print()

    for q in QUERIES:
        print("=" * 72)
        print(f"QUERY: {q}")
        print("=" * 72)
        payload = {
            "model": s.qwen_api_model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"查询：{q}"},
            ],
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
        }
        try:
            r = httpx.post(
                url,
                headers={
                    "Authorization": "Bearer dummy",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
        except Exception as exc:
            print(f"HTTP EXCEPTION: {exc!r}")
            continue

        print(f"status     : {r.status_code}")
        try:
            env = r.json()
        except Exception as exc:
            print(f"JSON DECODE FAIL: {exc}")
            print(f"raw body: {r.text[:400]!r}")
            continue

        choice = (env.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = msg.get("content")
        reasoning = msg.get("reasoning_content")
        print(f"finish_reason      : {choice.get('finish_reason')}")
        print(f"usage              : {env.get('usage')}")
        print(f"message keys       : {sorted(msg.keys())}")
        print(
            f"content len        : "
            f"{len(content) if isinstance(content, str) else 'n/a'}"
        )
        print(
            f"reasoning_content len : "
            f"{len(reasoning) if isinstance(reasoning, str) else 'n/a'}"
        )
        print("----- content -----")
        print(content if isinstance(content, str) else repr(content))
        print("----- reasoning_content (first 400) -----")
        if isinstance(reasoning, str):
            print(reasoning[:400] + ("\n[...truncated]" if len(reasoning) > 400 else ""))
        else:
            print(repr(reasoning))
        print()


if __name__ == "__main__":
    main()
