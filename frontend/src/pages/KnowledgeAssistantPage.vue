<template>
  <section>
    <div class="panel">
      <h2>会话</h2>
      <div class="row">
        <input v-model.trim="sessionTitle" placeholder="新会话标题" />
        <button class="primary" :disabled="creatingSession" @click="handleCreateSession">
          {{ creatingSession ? "创建中..." : "创建会话" }}
        </button>
      </div>
      <div class="row" style="margin-top: 10px">
        <select v-model="selectedSessionId">
          <option value="">请选择会话</option>
          <option v-for="item in sessions" :key="item.session_id" :value="item.session_id">
            {{ item.title }} ({{ formatTime(item.created_at) }})
          </option>
        </select>
        <button class="secondary" @click="loadSessions">刷新会话</button>
      </div>
    </div>

    <div class="panel">
      <h2>提问</h2>
      <textarea v-model.trim="question" placeholder="输入问题..." />
      <div class="quick-actions">
        <button class="secondary" type="button" @click="applyQuickQuestion('我有哪些文档？')">
          查看我的文档
        </button>
        <button class="secondary" type="button" @click="applyQuickQuestion('文档列表里有哪些内容？')">
          文档列表
        </button>
        <button class="secondary" type="button" @click="applyQuickQuestion('请总结一下我当前可见的文档。')">
          总结可见文档
        </button>
      </div>
      <p class="muted quick-hint">
        “查看我的文档 / 文档列表”会优先走只读工具查询，更适合快速确认当前可见数据。
      </p>
      <h3>限定文档（可选）</h3>
      <div v-if="documents.length" class="checkbox-grid">
        <label v-for="doc in documents" :key="doc.document_id" class="checkbox-item">
          <input type="checkbox" :value="doc.document_id" v-model="selectedDocumentIds" />
          <span>{{ doc.name }}</span>
        </label>
      </div>
      <p v-else class="muted">暂无可选文档，请先在“文档管理”上传。</p>

      <div class="row" style="margin-top: 10px">
        <label class="checkbox-item">
          <input type="checkbox" v-model="streamMode" />
          <span>流式回答（/qa/ask-stream）</span>
        </label>
        <button class="primary" :disabled="asking" @click="handleAsk">
          {{ asking ? "请求中..." : "发送问题" }}
        </button>
        <button class="secondary" :disabled="historyLoading || !selectedSessionId" @click="loadHistory">
          刷新历史
        </button>
      </div>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    </div>

    <div class="panel" v-if="asking && streamMode">
      <h2>流式输出中</h2>
      <p style="white-space: pre-wrap">{{ streamText || "..." }}</p>
    </div>

    <div class="panel" v-if="lastAnswer">
      <h2>最新回答</h2>
      <div v-if="isToolStyleAnswer" class="tool-result-banner">
        当前结果来自权限受控的只读工具查询，适合确认“我能看到什么”这类信息。
      </div>
      <p style="white-space: pre-wrap">{{ lastAnswer.answer }}</p>
      <p class="muted">
        trace_id: {{ lastAnswer.trace_id }} |
        latency: {{ lastAnswer.latency_ms }} ms
      </p>
      <p class="muted">
        召回置信度: {{ formatConfidence(lastAnswer.retrieval_confidence) }} |
        答复策略: {{ formatProvider(lastAnswer.answer_provider) }}
      </p>
      <p v-if="lastAnswer.need_human_review" class="error">
        当前答案可靠性偏低（{{ formatRefusalReason(lastAnswer.refusal_reason) }}），建议补充文档后重试。
      </p>
    </div>

    <CitationList :citations="lastAnswer?.citations || []" />

    <div class="panel">
      <h2>历史问答</h2>
      <p class="muted" v-if="historyTotal > 0">
        已加载 {{ historyItems.length }} / {{ historyTotal }} 条（最新优先）
      </p>
      <p v-if="historyLoading" class="muted">历史加载中...</p>
      <p v-else-if="!historyItems.length" class="muted">当前会话暂无历史。</p>
      <div v-else class="list">
        <article v-for="item in historyItems" :key="item.trace_id" class="list-item">
          <h4>Q: {{ item.question }}</h4>
          <p>A: {{ item.answer }}</p>
          <p class="muted">
            {{ formatTime(item.created_at) }} | latency {{ item.latency_ms }} ms
          </p>
          <p class="muted">
            召回置信度: {{ formatConfidence(item.retrieval_confidence) }} |
            答复策略: {{ formatProvider(item.answer_provider) }}
          </p>
          <p v-if="item.need_human_review" class="error">
            低置信度保护（{{ formatRefusalReason(item.refusal_reason) }}）
          </p>
        </article>
      </div>
      <div class="row" style="margin-top: 10px" v-if="historyHasMore">
        <button class="secondary" :disabled="historyLoadingMore" @click="loadMoreHistory">
          {{ historyLoadingMore ? "加载中..." : "加载更多" }}
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import CitationList from "../components/CitationList.vue";
import {
  askQuestion,
  askQuestionStream,
  createSession,
  getQaHistory,
  listDocuments,
  listSessions,
} from "../services/api";

const sessions = ref([]);
const selectedSessionId = ref("");
const sessionTitle = ref("");
const creatingSession = ref(false);

const documents = ref([]);
const selectedDocumentIds = ref([]);

const question = ref("");
const asking = ref(false);
const errorMessage = ref("");
const lastAnswer = ref(null);
const streamMode = ref(true);
const streamText = ref("");

const historyLoading = ref(false);
const historyLoadingMore = ref(false);
const historyItems = ref([]);
const historyTotal = ref(0);
const historyHasMore = ref(false);
const historyOffset = ref(0);
const historyPageSize = 10;
const historyOrder = "desc";
const toolQuestionKeywords = ["我有哪些文档", "文档列表", "我的文档", "可见文档"];

const isToolStyleAnswer = computed(() => {
  if (!lastAnswer.value?.answer) return false;
  const hasCitations = Array.isArray(lastAnswer.value.citations) && lastAnswer.value.citations.length > 0;
  if (hasCitations) return false;
  return isToolQuestion(question.value) || lastAnswer.value.answer.includes("当前你可见的文档有");
});

function formatTime(isoString) {
  if (!isoString) return "-";
  return new Date(isoString).toLocaleString();
}

function formatConfidence(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "-";
  return value.toFixed(3);
}

function formatRefusalReason(reason) {
  if (reason === "no_citations") return "未检索到有效内容";
  if (reason === "low_confidence") return "检索置信度不足";
  return "上下文不足";
}

function formatProvider(provider) {
  if (provider === "guard_refusal") return "低置信度保护";
  if (provider === "langchain_or_ollama") return "LangChain/Ollama";
  if (provider === "fallback") return "回退生成";
  return "-";
}

function applyQuickQuestion(text) {
  question.value = text;
}

function isToolQuestion(text) {
  const normalized = String(text || "").trim();
  return toolQuestionKeywords.some((keyword) => normalized.includes(keyword));
}

async function loadSessions() {
  errorMessage.value = "";
  try {
    const data = await listSessions();
    sessions.value = data.items || [];
    if (!selectedSessionId.value && sessions.value.length > 0) {
      selectedSessionId.value = sessions.value[0].session_id;
    }
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleCreateSession() {
  if (!sessionTitle.value) {
    errorMessage.value = "请输入会话标题";
    return;
  }
  creatingSession.value = true;
  errorMessage.value = "";
  try {
    const session = await createSession({ title: sessionTitle.value });
    sessionTitle.value = "";
    await loadSessions();
    selectedSessionId.value = session.session_id;
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    creatingSession.value = false;
  }
}

async function loadDocumentsForSelection() {
  try {
    const data = await listDocuments();
    documents.value = data.items || [];
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleAsk() {
  if (!selectedSessionId.value) {
    errorMessage.value = "请先选择会话";
    return;
  }
  if (!question.value) {
    errorMessage.value = "请输入问题";
    return;
  }

  asking.value = true;
  errorMessage.value = "";
  streamText.value = "";
  try {
    if (streamMode.value) {
      await askQuestionStream(
        {
          session_id: selectedSessionId.value,
          question: question.value,
          document_ids: selectedDocumentIds.value,
          top_k: 5,
          use_rerank: true,
        },
        {
          onEvent: (event) => {
            if (event?.type === "token") {
              streamText.value += event.token || "";
            }
            if (event?.type === "done") {
              lastAnswer.value = {
                answer: event.answer,
                citations: event.citations || [],
                trace_id: event.trace_id,
                latency_ms: event.latency_ms,
                retrieval_confidence: event.retrieval_confidence,
                refusal_reason: event.refusal_reason,
                need_human_review: event.need_human_review,
                answer_provider: event.answer_provider || event.stream_provider,
              };
            }
          },
        }
      );
    } else {
      const data = await askQuestion({
        session_id: selectedSessionId.value,
        question: question.value,
        document_ids: selectedDocumentIds.value,
        top_k: 5,
        use_rerank: true,
      });
      lastAnswer.value = data;
    }
    await loadHistory({ reset: true });
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    asking.value = false;
  }
}

async function loadHistory(options = { reset: true }) {
  if (!selectedSessionId.value) {
    historyItems.value = [];
    historyTotal.value = 0;
    historyHasMore.value = false;
    historyOffset.value = 0;
    return;
  }
  const reset = options.reset ?? true;
  if (reset) {
    historyLoading.value = true;
  } else {
    historyLoadingMore.value = true;
  }
  errorMessage.value = "";
  try {
    const nextOffset = reset ? 0 : historyOffset.value;
    const data = await getQaHistory(selectedSessionId.value, {
      limit: historyPageSize,
      offset: nextOffset,
      order: historyOrder,
    });
    const items = data.items || [];
    historyTotal.value = data.total || 0;
    historyOffset.value = nextOffset + items.length;
    historyHasMore.value = Boolean(data.has_more);
    historyItems.value = reset ? items : [...historyItems.value, ...items];
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    if (reset) {
      historyLoading.value = false;
    } else {
      historyLoadingMore.value = false;
    }
  }
}

async function loadMoreHistory() {
  await loadHistory({ reset: false });
}

watch(selectedSessionId, () => {
  loadHistory({ reset: true });
});

onMounted(async () => {
  await Promise.all([loadSessions(), loadDocumentsForSelection()]);
  await loadHistory({ reset: true });
});
</script>
