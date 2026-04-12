<template>
  <section>
    <div class="panel">
      <h2>上传文档</h2>
      <div class="row">
        <input v-model.trim="uploadName" placeholder="文档名称" />
        <input type="file" accept=".txt,.md,.markdown,.pdf,.docx" @change="onFileChange" />
        <button class="primary" :disabled="submitting" @click="submitUpload">
          {{ submitting ? "上传中..." : "上传并索引" }}
        </button>
      </div>
      <p class="muted">支持 txt / md / pdf / docx，上传后会自动触发后端 reindex。</p>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    </div>

    <div class="panel">
      <div class="row" style="justify-content: space-between; align-items: center">
        <h2>文档列表</h2>
        <button class="secondary" :disabled="loading" @click="loadDocuments">
          刷新
        </button>
      </div>
      <p v-if="loading" class="muted">加载中...</p>
      <p v-else-if="!documents.length" class="muted">还没有文档。</p>
      <div v-else class="list">
        <article v-for="doc in documents" :key="doc.document_id" class="list-item">
          <div class="row" style="justify-content: space-between; align-items: center">
            <div>
              <h4>{{ doc.name }}</h4>
              <p class="muted">ID: {{ doc.document_id }}</p>
              <p class="muted">
                状态: <span class="badge">{{ doc.status }}</span> |
                创建时间: {{ formatTime(doc.created_at) }}
              </p>
              <p v-if="doc.latest_index_job" class="muted">
                任务: {{ doc.latest_index_job.status }} |
                进度: {{ doc.latest_index_job.progress_pct }}%
              </p>
              <p v-if="doc.latest_index_job?.error_message" class="error">
                {{ formatIndexError(doc.latest_index_job) }}
              </p>
            </div>
            <div class="row">
              <button class="secondary" @click="handleReindex(doc.document_id)">重建索引</button>
              <button class="danger" @click="handleDelete(doc.document_id)">删除</button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import {
  deleteDocument,
  getDocument,
  listDocuments,
  reindexDocument,
  streamIndexJob,
  uploadDocument,
} from "../services/api";

const documents = ref([]);
const uploadName = ref("");
const selectedFile = ref(null);
const loading = ref(false);
const submitting = ref(false);
const errorMessage = ref("");
const indexErrorHints = {
  chunk_generation_failed: "切块失败",
  chunk_persist_failed: "切块写入失败",
  embedding_generation_failed: "向量生成失败",
  embedding_persist_failed: "向量元数据写入失败",
  vector_sync_failed: "向量库同步失败",
  document_snapshot_failed: "文档快照写入失败",
  document_missing: "文档不存在",
  indexing_failed: "索引失败",
};

function onFileChange(event) {
  const file = event.target.files?.[0] || null;
  selectedFile.value = file;
  if (file && !uploadName.value) {
    uploadName.value = file.name;
  }
}

function formatTime(isoString) {
  if (!isoString) return "-";
  return new Date(isoString).toLocaleString();
}

function formatIndexError(job) {
  if (!job) return "";
  const code = job.error_code || "indexing_failed";
  const hint = indexErrorHints[code] || "索引异常";
  const details = job.error_message || "请检查后端日志。";
  return `${hint}（${code}）：${details}`;
}

async function loadDocuments() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const data = await listDocuments();
    documents.value = data.items || [];
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    loading.value = false;
  }
}

async function submitUpload() {
  if (!selectedFile.value) {
    errorMessage.value = "请选择文件";
    return;
  }
  if (!uploadName.value) {
    errorMessage.value = "请输入文档名称";
    return;
  }
  submitting.value = true;
  errorMessage.value = "";
  try {
    const created = await uploadDocument({
      file: selectedFile.value,
      name: uploadName.value,
    });
    uploadName.value = "";
    selectedFile.value = null;
    await loadDocuments();
    await waitForIndexing(created.document_id, created.latest_index_job?.job_id);
  } catch (error) {
    errorMessage.value = String(error.message || error);
  } finally {
    submitting.value = false;
  }
}

async function waitForIndexing(documentId, jobId) {
  if (jobId) {
    try {
      await waitForIndexingStream(documentId, jobId);
      return;
    } catch {
      // Fall back to polling if the streaming channel is unavailable.
    }
  }

  for (let attempt = 0; attempt < 12; attempt += 1) {
    const current = await getDocument(documentId);
    await loadDocuments();
    const latestJob = current.latest_index_job;
    if (latestJob?.status === "failed" && latestJob.error_message) {
      errorMessage.value = formatIndexError(latestJob);
      return;
    }
    if (current.status === "indexed" || current.status === "failed") {
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
  }
}

async function waitForIndexingStream(documentId, jobId) {
  await streamIndexJob(jobId, {
    onEvent: async (event) => {
      const currentList = documents.value.map((item) =>
        item.document_id === documentId
          ? {
              ...item,
              status: event.status,
              latest_index_job: event,
            }
          : item
      );
      documents.value = currentList;

      if (event.status === "failed" && event.error_message) {
        errorMessage.value = formatIndexError(event);
      }
    },
  });
  await loadDocuments();
}

async function handleReindex(documentId) {
  errorMessage.value = "";
  try {
    const result = await reindexDocument(documentId);
    await loadDocuments();
    await waitForIndexing(documentId, result.job?.job_id);
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

async function handleDelete(documentId) {
  if (!window.confirm("确认删除该文档吗？")) return;
  errorMessage.value = "";
  try {
    await deleteDocument(documentId);
    await loadDocuments();
  } catch (error) {
    errorMessage.value = String(error.message || error);
  }
}

onMounted(loadDocuments);
</script>
