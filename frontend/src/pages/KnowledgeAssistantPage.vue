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
      <p style="white-space: pre-wrap">{{ lastAnswer.answer }}</p>
      <p class="muted">
        trace_id: {{ lastAnswer.trace_id }} |
        latency: {{ lastAnswer.latency_ms }} ms
      </p>
    </div>

    <CitationList :citations="lastAnswer?.citations || []" />

    <div class="panel">
      <h2>历史问答</h2>
      <p v-if="historyLoading" class="muted">历史加载中...</p>
      <p v-else-if="!historyItems.length" class="muted">当前会话暂无历史。</p>
      <div v-else class="list">
        <article v-for="item in historyItems" :key="item.trace_id" class="list-item">
          <h4>Q: {{ item.question }}</h4>
          <p>A: {{ item.answer }}</p>
          <p class="muted">
            {{ formatTime(item.created_at) }} | latency {{ item.latency_ms }} ms
          </p>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
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
const historyItems = ref([]);

function formatTime(isoString) {
  if (!isoString) return "-";
  return new Date(isoString).toLocaleString();
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
    await loadHistory();
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    asking.value = false;
  }
}

async function loadHistory() {
  if (!selectedSessionId.value) {
    historyItems.value = [];
    return;
  }
  historyLoading.value = true;
  errorMessage.value = "";
  try {
    const data = await getQaHistory(selectedSessionId.value);
    historyItems.value = data.items || [];
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    historyLoading.value = false;
  }
}

watch(selectedSessionId, () => {
  loadHistory();
});

onMounted(async () => {
  await Promise.all([loadSessions(), loadDocumentsForSelection()]);
  await loadHistory();
});
</script>
