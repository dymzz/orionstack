from __future__ import annotations

from collections.abc import Iterator
import os

from app.core.config import get_settings
from app.governance.user_context import Permission, UserContext
from app.integrations.builtin_tools import register_builtin_tools
from app.integrations.model_gateway import ModelGateway
from app.integrations.tool_gateway import ToolCallRequest, ToolGateway
from app.knowledge.retrieval.registry import RetrievalRegistry, RetrievalRuntime
from app.workflows.knowledge_assistant.state import KnowledgeAssistantState

try:
    from langgraph.graph import END, START, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # pragma: no cover - optional dependency fallback
    HAS_LANGGRAPH = False

try:
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_ollama import ChatOllama

    HAS_LANGCHAIN = True
except Exception:  # pragma: no cover - optional dependency fallback
    HAS_LANGCHAIN = False


class KnowledgeAssistantWorkflow:
    """Knowledge assistant orchestration with LangGraph/LangChain and safe fallbacks."""

    def __init__(self, retrieval_runtime: RetrievalRuntime | None = None) -> None:
        self.settings = get_settings()
        self.retrieval_backend = self.settings.qa.retrieval_backend
        self.retrieval_registry = RetrievalRegistry()
        self.retrieval_runtime = retrieval_runtime or self.retrieval_registry.resolve(self.retrieval_backend)
        self.model_gateway = ModelGateway()
        self.model_provider = "ollama"
        self.tool_gateway = ToolGateway()
        register_builtin_tools(self.tool_gateway)
        self.ollama_base_url = os.getenv("ORIONSTACK_OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("ORIONSTACK_OLLAMA_MODEL", "gemma3:1b")
        self.min_score = float(self.settings.qa.min_retrieval_score)

        self._graph = self._build_graph() if HAS_LANGGRAPH else None
        self._prompt = self._build_prompt_template() if HAS_LANGCHAIN else None
        self._llm = (
            ChatOllama(
                model=self.ollama_model,
                base_url=self.ollama_base_url,
                temperature=0.1,
            )
            if HAS_LANGCHAIN
            else None
        )

    def run(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        if self._graph is not None:
            return self._graph.invoke(state)

        prepared = self.prepare(state)
        if prepared.get("should_refuse"):
            return prepared
        answer = self.generate_answer(prepared)
        return self.finalize(prepared, answer)

    def prepare(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = self._retrieve(dict(state))
        current = self._plan_tools(current)
        current = self._execute_tools(current)
        current = self._guard(current)
        return current

    def generate_answer(self, state: KnowledgeAssistantState) -> str:
        if state.get("should_refuse"):
            return str(state.get("answer", "")).strip()

        if self._llm is not None and self._prompt is not None:
            try:
                chain = self._prompt | self._llm | StrOutputParser()
                answer = chain.invoke(
                    {
                        "question": state.get("question", ""),
                        "context": self._context_text(
                            state.get("citations", []),
                            state.get("tool_results", []),
                        ),
                    }
                )
                normalized = str(answer).strip()
                if normalized:
                    return normalized
            except Exception:
                pass

        return self._generate_with_ollama(state)

    def stream_generate_tokens(self, state: KnowledgeAssistantState) -> Iterator[str]:
        if state.get("should_refuse"):
            for token in self._tokenize_for_stream(str(state.get("answer", ""))):
                yield token
            return

        if self._llm is not None and self._prompt is not None:
            try:
                messages = self._prompt.format_messages(
                    question=state.get("question", ""),
                    context=self._context_text(
                        state.get("citations", []),
                        state.get("tool_results", []),
                    ),
                )
                yielded_any = False
                for chunk in self._llm.stream(messages):
                    token = self._chunk_to_text(chunk)
                    if token:
                        yielded_any = True
                        yield token
                if yielded_any:
                    return
            except Exception:
                pass

        for token in self._stream_with_ollama(state):
            yield token

    def finalize(self, state: KnowledgeAssistantState, answer: str) -> KnowledgeAssistantState:
        current = dict(state)
        citations = current.get("citations", [])
        text = answer.strip()
        if not text:
            text = self._fallback_answer(current)

        if citations:
            top_name = str(citations[0].get("document_name", "")).strip()
            if top_name and top_name not in text:
                text = f'Based on "{top_name}", {text}'

        current["answer"] = text
        current["need_human_review"] = bool(current.get("should_refuse", False))
        return current

    def build_fallback_answer(self, state: KnowledgeAssistantState) -> str:
        return self._fallback_answer(state)

    def _build_graph(self):
        builder = StateGraph(KnowledgeAssistantState)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("plan_tools", self._plan_tools)
        builder.add_node("execute_tools", self._execute_tools)
        builder.add_node("guard", self._guard)
        builder.add_node("generate", self._generate)
        builder.add_node("refuse", self._refuse)
        builder.add_node("validate", self._validate)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "plan_tools")
        builder.add_edge("plan_tools", "execute_tools")
        builder.add_edge("execute_tools", "guard")
        builder.add_conditional_edges("guard", self._route_after_guard)
        builder.add_edge("generate", "validate")
        builder.add_edge("validate", END)
        builder.add_edge("refuse", END)

        return builder.compile()

    def _build_prompt_template(self):
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are a concise enterprise knowledge assistant. "
                        "Answer in Chinese. "
                        "Only use the provided context. "
                        "If context is insufficient, clearly say so."
                    ),
                ),
                ("human", "问题：\n{question}\n\n可用上下文：\n{context}\n\n请给出答案："),
            ]
        )

    def _retrieve(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        user_context = self._user_context_from_state(current)
        chunks = self.retrieval_runtime.retrieve(
            question=str(current.get("question", "")),
            document_ids=current.get("document_ids", []),
            top_k=int(current.get("top_k", 5)),
            use_rerank=bool(current.get("use_rerank", True)),
            user_context=user_context,
        )

        citations = [
            {
                "document_id": item.get("document_id", ""),
                "document_name": item.get("document_name", ""),
                "chunk_id": item.get("chunk_id", ""),
                "snippet": item.get("snippet", ""),
                "score": float(item.get("score", 0.0)),
            }
            for item in chunks
        ]
        current["retrieved_chunks"] = chunks
        current["citations"] = citations
        current["retrieval_confidence"] = max((c.get("score", 0.0) for c in citations), default=0.0)
        return current

    def _plan_tools(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        raw_question = str(current.get("question", "")).strip()
        question = raw_question.lower()
        tool_plan = list(current.get("tool_plan", []))

        if any(keyword in question for keyword in ["哪些文档", "文档列表", "我的文档", "有哪些文档"]):
            tool_plan.append(
                {
                    "tool_name": "document.list_visible",
                    "arguments": {},
                    "required_permission": ("document", "read"),
                }
            )

        document_name = self._extract_document_name_for_status(raw_question)
        if document_name:
            tool_plan.append(
                {
                    "tool_name": "document.get_status_by_name",
                    "arguments": {"document_name": document_name},
                    "required_permission": ("document", "read"),
                }
            )

        current["tool_plan"] = tool_plan
        return current

    def _execute_tools(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        user_context = self._user_context_from_state(current)
        if user_context is None:
            current["tool_results"] = []
            return current

        tool_results = []
        for item in current.get("tool_plan", []):
            if not isinstance(item, dict):
                continue
            required_permission = item.get("required_permission")
            permission_tuple = None
            if (
                isinstance(required_permission, (list, tuple))
                and len(required_permission) == 2
            ):
                permission_tuple = (str(required_permission[0]), str(required_permission[1]))

            result = self.tool_gateway.execute(
                ToolCallRequest(
                    tool_name=str(item.get("tool_name", "")),
                    arguments=dict(item.get("arguments", {})),
                    required_permission=permission_tuple,
                    trace_id=str(current.get("trace_id", "")),
                ),
                user_context=user_context,
            )
            tool_results.append(
                {
                    "tool_name": str(item.get("tool_name", "")),
                    "ok": result.ok,
                    "data": result.data,
                    "error_code": result.error_code,
                    "error_message": result.error_message,
                }
            )

        current["tool_results"] = tool_results
        return current

    def _user_context_from_state(self, state: dict) -> UserContext | None:
        payload = state.get("user_context")
        if not isinstance(payload, dict):
            return None

        permissions_payload = payload.get("permissions", [])
        permissions = []
        if isinstance(permissions_payload, list):
            for item in permissions_payload:
                if not isinstance(item, dict):
                    continue
                resource = str(item.get("resource", "")).strip()
                action = str(item.get("action", "")).strip()
                if resource and action:
                    permissions.append(Permission(resource=resource, action=action))

        return UserContext(
            user_id=str(payload.get("user_id", "")),
            username=str(payload.get("username", "")),
            departments=[str(item) for item in payload.get("departments", []) if str(item)],
            roles=[str(item) for item in payload.get("roles", []) if str(item)],
            raw_attributes=dict(payload.get("raw_attributes", {})),
            permissions=permissions,
        )

    def _guard(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        citations = current.get("citations", [])
        tool_results = current.get("tool_results", [])
        has_tool_data = any(
            isinstance(item, dict) and item.get("ok") and item.get("data")
            for item in tool_results
        )
        if not citations:
            if has_tool_data:
                current["should_refuse"] = False
                current["refusal_reason"] = None
                return current
            current["should_refuse"] = True
            current["refusal_reason"] = "no_citations"
            current["answer"] = self._fallback_answer(current)
            return current

        confidence = float(current.get("retrieval_confidence", 0.0))
        if confidence < self.min_score:
            current["should_refuse"] = True
            current["refusal_reason"] = "low_confidence"
            current["answer"] = self._fallback_answer(current)
            return current

        current["should_refuse"] = False
        current["refusal_reason"] = None
        return current

    def _route_after_guard(self, state: KnowledgeAssistantState) -> str:
        if state.get("should_refuse"):
            return "refuse"
        return "generate"

    def _generate(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        current["answer"] = self.generate_answer(current)
        return current

    def _refuse(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        if not str(current.get("answer", "")).strip():
            current["answer"] = self._fallback_answer(current)
        current["need_human_review"] = True
        return current

    def _validate(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        return self.finalize(state, str(state.get("answer", "")))

    def _generate_with_ollama(self, state: KnowledgeAssistantState) -> str:
        prompt = self._ollama_prompt(state)
        try:
            answer = self.model_gateway.generate(
                provider=self.model_provider,
                model=self.ollama_model,
                prompt=prompt,
                timeout=30.0,
            )
            if answer:
                return answer
        except Exception:
            pass
        return self._fallback_answer(state)

    def _stream_with_ollama(self, state: KnowledgeAssistantState) -> Iterator[str]:
        prompt = self._ollama_prompt(state)
        try:
            yield from self.model_gateway.stream_generate(
                provider=self.model_provider,
                model=self.ollama_model,
                prompt=prompt,
                timeout=45.0,
            )
            return
        except Exception:
            pass

        for token in self._tokenize_for_stream(self._fallback_answer(state)):
            yield token

    def _ollama_prompt(self, state: KnowledgeAssistantState) -> str:
        return (
            "You are a concise enterprise knowledge assistant.\n"
            "Answer in Chinese.\n"
            "Only use the provided context.\n"
            "If context is insufficient, clearly say so.\n\n"
            f"Question:\n{state.get('question', '')}\n\n"
            f"Context:\n{self._context_text(state.get('citations', []), state.get('tool_results', []))}\n\n"
            "Answer:"
        )

    def _context_text(self, citations: list[dict], tool_results: list[dict] | None = None) -> str:
        if not citations and not tool_results:
            return "No indexed context available."
        lines: list[str] = []
        for idx, citation in enumerate(citations, start=1):
            lines.append(
                f"[{idx}] {citation.get('document_name', '')}#{citation.get('chunk_id', '')}: "
                f"{citation.get('snippet', '')}"
            )
        if tool_results:
            for item in tool_results:
                if not isinstance(item, dict) or not item.get("ok"):
                    continue
                if item.get("tool_name") == "document.list_visible":
                    documents = item.get("data", {}).get("documents", [])
                    if documents:
                        names = ", ".join(str(document.get("name", "")) for document in documents if document.get("name"))
                        lines.append(f"[tool] visible documents: {names}")
                if item.get("tool_name") == "document.get_status_by_name":
                    document = item.get("data", {}).get("document", {})
                    latest_job = item.get("data", {}).get("latest_index_job")
                    if document.get("name"):
                        status_line = (
                            f"[tool] document status: {document.get('name')} => {document.get('status', '')}"
                        )
                        if isinstance(latest_job, dict) and latest_job.get("status"):
                            status_line += (
                                f", latest index job {latest_job.get('status')} "
                                f"({latest_job.get('progress_pct', 0)}%)"
                            )
                        lines.append(status_line)
        return "\n".join(lines)

    def _fallback_answer(self, state: KnowledgeAssistantState) -> str:
        citations = state.get("citations", [])
        tool_results = state.get("tool_results", [])
        question = str(state.get("question", ""))
        for item in tool_results:
            if not isinstance(item, dict):
                continue
            if item.get("tool_name") == "document.get_status_by_name" and not item.get("ok"):
                if item.get("error_code") == "document_not_found":
                    return "当前没有找到你可见范围内匹配名称的文档。"
                continue
            if not item.get("ok"):
                continue
            if item.get("tool_name") == "document.list_visible":
                documents = item.get("data", {}).get("documents", [])
                if not documents:
                    return "当前你还没有可见文档。"
                document_names = ", ".join(
                    str(document.get("name", ""))
                    for document in documents
                    if document.get("name")
                )
                return f"当前你可见的文档有：{document_names}。"
            if item.get("tool_name") == "document.get_status_by_name":
                document = item.get("data", {}).get("document", {})
                latest_job = item.get("data", {}).get("latest_index_job")
                document_name = str(document.get("name", "")).strip()
                document_status = str(document.get("status", "")).strip() or "unknown"
                if not document_name:
                    continue
                if isinstance(latest_job, dict) and latest_job.get("status"):
                    return (
                        f'文档《{document_name}》当前状态为 {document_status}，'
                        f'最近一次索引任务状态为 {latest_job.get("status")}，'
                        f'进度 {latest_job.get("progress_pct", 0)}%。'
                    )
                return f'文档《{document_name}》当前状态为 {document_status}。'
        if not citations:
            return f'No relevant indexed content found for "{question}". Try uploading or reindexing a document first.'
        top_citation = citations[0]
        return (
            f'Based on "{top_citation.get("document_name", "")}", '
            f'the most relevant passage is: {top_citation.get("snippet", "")}'
        )

    def _extract_document_name_for_status(self, question: str) -> str | None:
        normalized = question.strip()
        if not normalized:
            return None
        normalized = normalized.rstrip("？?！!。.")

        markers = ["文档《", "《"]
        suffixes = ["》的状态", "》状态", "》现在是什么状态", "》当前状态", "》索引状态", "》怎么样"]
        for marker in markers:
            if marker not in normalized:
                continue
            start = normalized.find(marker) + len(marker)
            end = normalized.find("》", start)
            if end > start:
                return normalized[start:end].strip() or None

        plain_suffixes = ["文档状态怎么样", "文档状态", "状态怎么样", "索引状态", "现在是什么状态", "当前状态"]
        if "文档" in normalized and any(suffix in normalized for suffix in plain_suffixes):
            candidate = normalized
            for prefix in ["请问", "帮我看下", "帮我看看", "请帮我看下", "查询一下", "查一下", "看看"]:
                if candidate.startswith(prefix):
                    candidate = candidate[len(prefix):].strip()
            candidate = candidate.replace("文档", "", 1).strip()
            for suffix in plain_suffixes:
                if candidate.endswith(suffix):
                    candidate = candidate[: -len(suffix)].strip(" ：:，,?？")
                    break
            return candidate or None

        return None

    def _tokenize_for_stream(self, answer: str) -> Iterator[str]:
        for token in answer.split():
            yield token + " "

    def _chunk_to_text(self, chunk: object) -> str:
        content = getattr(chunk, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                text = getattr(item, "text", "")
                if text:
                    parts.append(str(text))
            return "".join(parts)
        return ""
