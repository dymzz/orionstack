from __future__ import annotations

from collections.abc import Iterator
import json
import os

from app.core.config import get_settings
from app.governance.user_context import Permission, UserContext
from app.integrations.builtin_tools import register_builtin_tools
from app.integrations.model_gateway import ModelGateway
from app.integrations.tool_gateway import ToolCallRequest, ToolGateway
from app.knowledge.retrieval.evidence_extractor import EvidenceExtractor
from app.knowledge.retrieval.query_rewriter import QueryRewriter
from app.knowledge.retrieval.query_tokenizer import build_query_features, build_text_features, lexical_score
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
        self.evidence_extractor = EvidenceExtractor(
            model_gateway=self.model_gateway,
            provider=self.model_provider,
            model=self.ollama_model,
        )
        self.query_rewriter = QueryRewriter(
            model_gateway=self.model_gateway,
            provider=self.model_provider,
            model=self.ollama_model,
        )
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
        current = self._rewrite_retrieval_query(dict(state))
        current = self._retrieve(current)
        current = self._plan_tools(current)
        current = self._execute_tools(current)
        current = self._extract_evidence(current)
        current = self._guard(current)
        return current

    def generate_answer(self, state: KnowledgeAssistantState) -> str:
        if state.get("should_refuse"):
            return self._normalize_answer_text(answer=str(state.get("answer", "")), state=state)

        if self._is_lightweight_path(state):
            return self._fallback_answer(state)

        if self._llm is not None and self._prompt is not None:
            try:
                chain = self._prompt | self._llm | StrOutputParser()
                answer = chain.invoke(
                    {
                        "question": state.get("question", ""),
                        "context": self._context_text(
                            state.get("citations", []),
                            state.get("tool_results", []),
                            state.get("extracted_facts", []),
                        ),
                    }
                )
                normalized = self._normalize_answer_text(answer=str(answer), state=state)
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

        if self._is_lightweight_path(state):
            for token in self._tokenize_for_stream(self._fallback_answer(state)):
                yield token
            return

        if self._llm is not None and self._prompt is not None:
            try:
                messages = self._prompt.format_messages(
                    question=state.get("question", ""),
                    context=self._context_text(
                        state.get("citations", []),
                        state.get("tool_results", []),
                        state.get("extracted_facts", []),
                    ),
                )
                chunks: list[str] = []
                for chunk in self._llm.stream(messages):
                    token = self._chunk_to_text(chunk)
                    if token:
                        chunks.append(token)
                streamed = self._normalize_answer_text(answer="".join(chunks), state=state)
                if streamed:
                    for token in self._tokenize_for_stream(streamed):
                        yield token
                    return
            except Exception:
                pass

        answer = self._generate_with_ollama(state)
        for token in self._tokenize_for_stream(answer):
            yield token

    def finalize(self, state: KnowledgeAssistantState, answer: str) -> KnowledgeAssistantState:
        current = dict(state)
        text = self._normalize_answer_text(answer=answer, state=current)
        if not text:
            text = self._fallback_answer(current)

        current["answer"] = text
        current["need_human_review"] = bool(current.get("should_refuse", False))
        return current

    def build_fallback_answer(self, state: KnowledgeAssistantState) -> str:
        return self._fallback_answer(state)

    def _build_graph(self):
        builder = StateGraph(KnowledgeAssistantState)
        builder.add_node("rewrite_retrieval_query", self._rewrite_retrieval_query)
        builder.add_node("retrieve", self._retrieve)
        builder.add_node("plan_tools", self._plan_tools)
        builder.add_node("execute_tools", self._execute_tools)
        builder.add_node("extract_evidence", self._extract_evidence)
        builder.add_node("guard", self._guard)
        builder.add_node("generate", self._generate)
        builder.add_node("refuse", self._refuse)
        builder.add_node("validate", self._validate)

        builder.add_edge(START, "rewrite_retrieval_query")
        builder.add_edge("rewrite_retrieval_query", "retrieve")
        builder.add_edge("retrieve", "plan_tools")
        builder.add_edge("plan_tools", "execute_tools")
        builder.add_edge("execute_tools", "extract_evidence")
        builder.add_edge("extract_evidence", "guard")
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
                        "First judge whether the provided context directly answers the user's question. "
                        "If the user's question is broad, and the context provides a more specific workflow or subtype under the same topic, you may answer with that specific workflow as long as you keep the scope accurate. "
                        "Do not reject just because the wording is not identical. "
                        "If the context is about a neighboring topic, a different procedure, or only vaguely related, do not answer with that content. "
                        "If the context does not directly answer the question, reply exactly: 当前提供的内容不能直接回答这个问题。 "
                        "Do not expand with adjacent policies or administrative FAQ."
                    ),
                ),
                (
                    "human",
                    (
                        "用户问题：\n{question}\n\n"
                        "可用内容：\n{context}\n\n"
                        "请严格遵守：\n"
                        "1. 先判断这些内容是否直接回答用户问题。\n"
                        "2. 如果用户问得比较泛，而内容给的是同一主题下的具体流程或子类型，也可以回答，但要明确按当前内容回答，不要擅自扩展。\n"
                        "3. 只有内容讲的是别的事项、相邻制度、相邻流程时，才回复：当前提供的内容不能直接回答这个问题。\n"
                        "4. 不要因为都属于行政制度/流程，就把不相干内容当成答案。\n"
                        "5. 不要输出来源前缀，不要说 Based on。\n"
                        "6. 只输出最终自然语言答案，不要输出 JSON、字典、数组、代码块，也不要输出 relevant_chunk_ids、chunk_id、queries、facts、confidence、reason、provider 这类内部字段。\n"
                        "7. 不要重复用户问题本身。\n\n"
                        "请输出最终回答："
                    ),
                ),
            ]
        )

    def _retrieve(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        user_context = self._user_context_from_state(current)
        lightweight_path = self._is_lightweight_path(current)
        current["lightweight_path"] = lightweight_path
        retrieval_query = str(current.get("retrieval_query", "")).strip() or str(current.get("question", ""))
        chunks = self.retrieval_runtime.retrieve(
            question=retrieval_query,
            document_ids=current.get("document_ids", []),
            top_k=int(current.get("top_k", 5)),
            use_rerank=bool(current.get("use_rerank", False)) and not lightweight_path,
            user_context=user_context,
        )

        citations = [
            {
                "document_id": item.get("document_id", ""),
                "document_name": item.get("document_name", ""),
                "chunk_id": item.get("chunk_id", ""),
                "snippet": item.get("snippet", ""),
                "content": item.get("content", item.get("snippet", "")),
                "score": float(item.get("score", 0.0)),
            }
            for item in chunks
        ]
        if lightweight_path:
            chunks, citations = self._filter_lightweight_retrieval(
                question=str(current.get("question", "")),
                chunks=chunks,
                citations=citations,
            )
        current["retrieved_chunks"] = chunks
        current["citations"] = citations
        current["extracted_facts"] = []
        current["evidence_confidence"] = 0.0
        current["evidence_provider"] = None
        current["retrieval_confidence"] = max((c.get("score", 0.0) for c in citations), default=0.0)
        return current

    def _rewrite_retrieval_query(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        question = str(current.get("question", "")).strip()
        current["lightweight_path"] = self._should_use_lightweight_path(current)
        current["retrieval_query"] = self.query_rewriter.rewrite(question)
        return current

    def _extract_evidence(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        if self._is_lightweight_path(current) or not bool(current.get("use_rerank", False)):
            current["extracted_facts"] = []
            current["evidence_confidence"] = float(current.get("retrieval_confidence", 0.0) or 0.0)
            current["evidence_provider"] = None
            return current

        citations = list(current.get("citations", []))
        if not citations:
            current["extracted_facts"] = []
            current["evidence_confidence"] = 0.0
            current["evidence_provider"] = None
            return current

        extraction = self.evidence_extractor.extract(
            question=str(current.get("question", "")),
            citations=citations,
        )
        filtered_citations = list(extraction.get("citations", []))
        extracted_facts = [str(item).strip() for item in extraction.get("facts", []) if str(item).strip()]
        evidence_confidence = float(extraction.get("confidence", 0.0) or 0.0)
        current["extracted_facts"] = extracted_facts
        current["evidence_confidence"] = evidence_confidence
        current["evidence_provider"] = str(extraction.get("provider", "") or "")

        if filtered_citations:
            kept_chunk_ids = {
                str(item.get("chunk_id", "")).strip()
                for item in filtered_citations
                if str(item.get("chunk_id", "")).strip()
            }
            current["citations"] = filtered_citations
            current["retrieved_chunks"] = [
                item
                for item in current.get("retrieved_chunks", [])
                if str(item.get("chunk_id", "")).strip() in kept_chunk_ids
            ]
            base_confidence = max((item.get("score", 0.0) for item in filtered_citations), default=0.0)
            current["retrieval_confidence"] = min(float(base_confidence), evidence_confidence or float(base_confidence))
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
                normalized = self._normalize_answer_text(answer=answer, state=state)
                if normalized:
                    return normalized
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
            "First judge whether the provided context directly answers the user's question.\n"
            "If the user's question is broad, and the context provides a more specific workflow or subtype under the same topic, you may answer with that specific workflow as long as you keep the scope accurate.\n"
            "Do not reject just because the wording is not identical.\n"
            "If the context is about a neighboring topic, a different procedure, or only vaguely related, reply exactly: 当前提供的内容不能直接回答这个问题。\n"
            "Do not expand with adjacent policies or administrative FAQ.\n\n"
            f"Question:\n{state.get('question', '')}\n\n"
            "Rules:\n"
            "- 先判断是否直接回答问题。\n"
            "- 如果问题较泛，而当前内容提供的是同主题下的具体流程或子类型，可以直接按当前内容回答。\n"
            "- 只有在主题不一致、属于相邻事项时，才回复：当前提供的内容不能直接回答这个问题。\n"
            "- 不要因为都是制度或流程内容，就拿相邻事项来作答。\n"
            "- 不要输出 Based on 或来源前缀。\n"
            "- 只输出最终自然语言答案，不要输出 JSON、字典、数组、代码块，也不要输出 relevant_chunk_ids、chunk_id、queries、facts、confidence、reason、provider 这类内部字段。\n"
            "- 不要重复用户问题本身。\n\n"
            f"Context:\n{self._context_text(state.get('citations', []), state.get('tool_results', []), state.get('extracted_facts', []))}\n\n"
            "Answer:"
        )

    def _context_text(
        self,
        citations: list[dict],
        tool_results: list[dict] | None = None,
        extracted_facts: list[str] | None = None,
    ) -> str:
        if not citations and not tool_results and not extracted_facts:
            return "No indexed context available."
        lines: list[str] = []
        if extracted_facts:
            for idx, fact in enumerate(extracted_facts, start=1):
                lines.append(f"[fact {idx}] {fact}")
        for idx, citation in enumerate(citations, start=1):
            lines.append(
                f"[{idx}] {citation.get('document_name', '')}#{citation.get('chunk_id', '')}: "
                f"{citation.get('content', '') or citation.get('snippet', '')}"
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
        extracted_facts = state.get("extracted_facts", [])
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
            return (
                f'当前没有检索到可直接回答“{question}”的相关内容。'
                "请补充更具体的问题，或上传并索引对应制度文档后再试。"
            )
        if extracted_facts:
            return str(extracted_facts[0]).strip()
        top_citation = citations[0]
        return str(top_citation.get("content", "")).strip() or str(top_citation.get("snippet", "")).strip() or "当前提供的内容不能直接回答这个问题。"

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

    def _is_lightweight_path(self, state: KnowledgeAssistantState | dict) -> bool:
        if "lightweight_path" in state:
            return bool(state.get("lightweight_path", False))
        return self._should_use_lightweight_path(state)

    def _should_use_lightweight_path(self, state: KnowledgeAssistantState | dict) -> bool:
        question = "".join(str(state.get("question", "")).split()).strip()
        if not question:
            return True

        if any(keyword in question for keyword in ["哪些文档", "文档列表", "我的文档", "有哪些文档"]):
            return True

        if self._extract_document_name_for_status(question):
            return True

        if any(marker in question for marker in ["、", "/", "；", ";", "以及", "\n"]):
            return False

        if len(question) <= 16:
            return True

        if any(token in question for token in ["怎么", "如何", "怎样", "咋", "怎么办", "哪里看", "在哪看", "多久到账"]):
            return True

        return False

    def _filter_lightweight_retrieval(
        self,
        *,
        question: str,
        chunks: list[dict],
        citations: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        normalized_question = " ".join(str(question).split()).strip()
        if not normalized_question or not citations:
            return chunks, citations

        query_features = build_query_features(normalized_question)
        filtered_citations: list[dict] = []
        kept_chunk_ids: set[str] = set()

        for citation in citations:
            candidate_text = " ".join(
                [
                    str(citation.get("document_name", "")),
                    str(citation.get("content", "")) or str(citation.get("snippet", "")),
                ]
            ).strip()
            if not self._is_lightweight_relevant(query_features=query_features, candidate_text=candidate_text):
                continue
            filtered_citations.append(citation)
            chunk_id = str(citation.get("chunk_id", "")).strip()
            if chunk_id:
                kept_chunk_ids.add(chunk_id)

        if not filtered_citations:
            return [], []

        filtered_chunks = [
            item
            for item in chunks
            if str(item.get("chunk_id", "")).strip() in kept_chunk_ids
        ]
        return filtered_chunks, filtered_citations

    def _is_lightweight_relevant(self, *, query_features, candidate_text: str) -> bool:
        candidate_features = build_text_features(candidate_text)
        if not candidate_features.normalized:
            return False

        if query_features.compact and len(query_features.compact) >= 2 and query_features.compact in candidate_features.compact:
            return True

        return lexical_score(query=query_features, candidate=candidate_features) >= 2.0

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

    def _normalize_answer_text(self, *, answer: str, state: KnowledgeAssistantState | dict) -> str:
        normalized = str(answer).strip()
        if not normalized:
            return ""

        if self._looks_like_internal_structured_output(normalized):
            return self._fallback_answer(dict(state))

        question = " ".join(str(state.get("question", "")).split()).strip()
        candidate = normalized
        if question and candidate.startswith(question):
            candidate = candidate[len(question):].lstrip("：:，,。.!！？? \n\t")
        return candidate.strip()

    def _looks_like_internal_structured_output(self, text: str) -> bool:
        raw = str(text).strip()
        if not raw:
            return False

        lowered = raw.lower()
        internal_markers = [
            "relevant_chunk_ids",
            "chunk_id",
            "queries",
            "facts",
            "confidence",
            "reason",
            "provider",
        ]
        if any(marker in lowered for marker in internal_markers):
            return True

        if raw.startswith("```"):
            stripped = raw.strip("`").strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
            raw = stripped

        if (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]")):
            try:
                payload = json.loads(raw)
                if isinstance(payload, (dict, list)):
                    return True
            except json.JSONDecodeError:
                return True

        return False
