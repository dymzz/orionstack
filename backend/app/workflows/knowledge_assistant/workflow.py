from __future__ import annotations

from collections.abc import Iterator
import json
import os

import httpx

from app.core.config import get_settings
from app.knowledge.retrieval.retrieval_service import RetrievalService
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

    def __init__(self) -> None:
        self.settings = get_settings()
        self.retrieval_service = RetrievalService()
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
                        "context": self._context_text(state.get("citations", [])),
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
                    context=self._context_text(state.get("citations", [])),
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
        builder.add_node("guard", self._guard)
        builder.add_node("generate", self._generate)
        builder.add_node("refuse", self._refuse)
        builder.add_node("validate", self._validate)

        builder.add_edge(START, "retrieve")
        builder.add_edge("retrieve", "guard")
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
        chunks = self.retrieval_service.retrieve(
            question=str(current.get("question", "")),
            document_ids=current.get("document_ids", []),
            top_k=int(current.get("top_k", 5)),
            use_rerank=bool(current.get("use_rerank", True)),
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

    def _guard(self, state: KnowledgeAssistantState) -> KnowledgeAssistantState:
        current = dict(state)
        citations = current.get("citations", [])
        if not citations:
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
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                answer = str(data.get("response", "")).strip()
                if answer:
                    return answer
        except Exception:
            pass
        return self._fallback_answer(state)

    def _stream_with_ollama(self, state: KnowledgeAssistantState) -> Iterator[str]:
        prompt = self._ollama_prompt(state)
        try:
            with httpx.stream(
                "POST",
                f"{self.ollama_base_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": True,
                },
                timeout=45.0,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    packet = json.loads(line)
                    token = str(packet.get("response", ""))
                    if token:
                        yield token
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
            f"Context:\n{self._context_text(state.get('citations', []))}\n\n"
            "Answer:"
        )

    def _context_text(self, citations: list[dict]) -> str:
        if not citations:
            return "No indexed context available."
        lines: list[str] = []
        for idx, citation in enumerate(citations, start=1):
            lines.append(
                f"[{idx}] {citation.get('document_name', '')}#{citation.get('chunk_id', '')}: "
                f"{citation.get('snippet', '')}"
            )
        return "\n".join(lines)

    def _fallback_answer(self, state: KnowledgeAssistantState) -> str:
        citations = state.get("citations", [])
        question = str(state.get("question", ""))
        if not citations:
            return f'No relevant indexed content found for "{question}". Try uploading or reindexing a document first.'
        top_citation = citations[0]
        return (
            f'Based on "{top_citation.get("document_name", "")}", '
            f'the most relevant passage is: {top_citation.get("snippet", "")}'
        )

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
