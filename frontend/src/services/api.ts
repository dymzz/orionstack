const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

async function request(path: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const raw = await response.text();
  const data = raw ? JSON.parse(raw) : null;
  if (!response.ok) {
    const message = data?.detail || `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return data;
}

export function listSessions() {
  return request("/sessions");
}

export function createSession(payload: { title: string; scene?: string }) {
  return request("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: payload.title,
      scene: payload.scene || "knowledge_assistant",
    }),
  });
}

export function listDocuments() {
  return request("/documents");
}

export function getDocument(documentId: string) {
  return request(`/documents/${documentId}`);
}

export function getIndexJob(jobId: string) {
  return request(`/index-jobs/${jobId}`);
}

export function uploadDocument(payload: { file: File; name: string; sourceType?: string }) {
  const form = new FormData();
  form.append("file", payload.file);
  form.append("name", payload.name);
  form.append("source_type", payload.sourceType || "upload");
  return request("/documents/upload", {
    method: "POST",
    body: form,
  });
}

export function reindexDocument(documentId: string) {
  return request(`/documents/${documentId}/reindex`, {
    method: "POST",
  });
}

export async function streamIndexJob(
  jobId: string,
  handlers: {
    onEvent: (event: any) => void;
    signal?: AbortSignal;
  }
) {
  const response = await fetch(`${API_BASE_URL}/index-jobs/${jobId}/stream`, {
    method: "GET",
    signal: handlers.signal,
  });

  if (!response.ok) {
    const raw = await response.text();
    const data = raw ? JSON.parse(raw) : null;
    throw new Error(data?.detail || `Request failed: ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";

    for (const frame of frames) {
      const trimmed = frame.trim();
      if (!trimmed || trimmed.startsWith(":")) continue;
      const line = trimmed
        .split("\n")
        .map((item) => item.trim())
        .find((item) => item.startsWith("data:"));
      if (!line) continue;
      const payloadText = line.slice(5).trim();
      if (!payloadText) continue;
      handlers.onEvent(JSON.parse(payloadText));
    }
  }
}

export function deleteDocument(documentId: string) {
  return request(`/documents/${documentId}`, {
    method: "DELETE",
  });
}

export function askQuestion(payload: {
  session_id: string;
  question: string;
  document_ids?: string[];
  top_k?: number;
  use_rerank?: boolean;
}) {
  return request("/qa/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: payload.session_id,
      question: payload.question,
      document_ids: payload.document_ids || [],
      top_k: payload.top_k || 5,
      use_rerank: payload.use_rerank ?? false,
    }),
  });
}

export async function askQuestionStream(
  payload: {
    session_id: string;
    question: string;
    document_ids?: string[];
    top_k?: number;
    use_rerank?: boolean;
  },
  handlers: {
    onEvent: (event: any) => void;
    signal?: AbortSignal;
  }
) {
  const response = await fetch(`${API_BASE_URL}/qa/ask-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: payload.session_id,
      question: payload.question,
      document_ids: payload.document_ids || [],
      top_k: payload.top_k || 5,
      use_rerank: payload.use_rerank ?? false,
    }),
    signal: handlers.signal,
  });

  if (!response.ok) {
    const raw = await response.text();
    const data = raw ? JSON.parse(raw) : null;
    throw new Error(data?.detail || `Request failed: ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";

    for (const frame of frames) {
      const line = frame
        .split("\n")
        .map((item) => item.trim())
        .find((item) => item.startsWith("data:"));
      if (!line) continue;
      const payloadText = line.slice(5).trim();
      if (!payloadText) continue;
      handlers.onEvent(JSON.parse(payloadText));
    }
  }
}

export function getQaHistory(
  sessionId: string,
  params?: {
    limit?: number;
    offset?: number;
    order?: "asc" | "desc";
  }
) {
  const query = new URLSearchParams();
  if (typeof params?.limit === "number") query.set("limit", String(params.limit));
  if (typeof params?.offset === "number") query.set("offset", String(params.offset));
  if (params?.order) query.set("order", params.order);
  const suffix = query.size ? `?${query.toString()}` : "";
  return request(`/qa/history/${sessionId}${suffix}`);
}

export const api = {
  baseUrl: API_BASE_URL,
};
