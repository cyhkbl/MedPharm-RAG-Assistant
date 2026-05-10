export type ParseStatus = "parsing" | "done" | "failed" | string;
export type DecisionAction = "merge" | "keep" | "remove";
export type EdgeType = "prerequisite" | "parallel" | "contains" | "applies_to" | string;
export type ChatRole = "user" | "assistant";

export interface Chapter {
  chapter_id: string;
  title: string;
  page_start: number;
  page_end: number;
  content: string;
  char_count: number;
}

export interface Textbook {
  id: string;
  filename: string;
  title: string;
  format: string;
  total_pages: number;
  total_chars: number;
  chapters?: Chapter[];
  upload_time: string;
  parse_status: ParseStatus;
}

export interface KnowledgeNode {
  id: string;
  name: string;
  definition: string;
  category: string;
  chapter: string;
  page: number;
  textbook_id: string;
  frequency: number;
}

export interface KnowledgeEdge {
  source: string;
  target: string;
  relation_type: EdgeType;
  description: string;
}

export interface KnowledgeGraphData {
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
}

export interface IntegrationDecision {
  decision_id: string;
  action: DecisionAction;
  affected_nodes: string[];
  result_node: string;
  reason: string;
  confidence: number;
}

export interface IntegrationStats {
  original_chars: number;
  compressed_chars: number;
  compression_ratio: number;
  merge_count: number;
  keep_count: number;
  remove_count: number;
}

export interface IntegrationResult {
  matched_pairs: Array<{ source: string; target: string; score: number }>;
  decisions: IntegrationDecision[];
  compression_ratio: number;
}

export interface RAGStatus {
  indexed_textbooks: number;
  total_chunks: number;
  ready: boolean;
  updated_at?: string;
}

export interface Citation {
  textbook: string;
  chapter: string;
  page: number;
  relevance_score: number;
  source_chunks: string[];
}

export interface RAGResponse {
  answer: string;
  citations: Citation[];
}

export interface ChatMessage {
  role: ChatRole;
  content: string;
  timestamp: string;
}

export interface DialogueResponse {
  conversation_id: string;
  message: string;
  timestamp: string;
}

export interface ReportData {
  original_stats: {
    total_textbooks: number;
    total_chars: number;
    total_chapters: number;
  };
  compressed_stats: {
    compressed_chars: number;
    compression_ratio: number;
  };
  decision_summary: Record<DecisionAction, number>;
  knowledge_graph_stats: {
    nodes: number;
    edges: number;
    textbooks_with_graph: number;
  };
  notable_integration_cases: IntegrationDecision[];
}

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8100";

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json().catch(() => null) : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `请求失败：${response.status}`;
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export function uploadFile(file: File): Promise<Textbook> {
  const formData = new FormData();
  formData.append("file", file);
  return request<Textbook>("/api/upload", { method: "POST", body: formData });
}

export const getTextbooks = (): Promise<Textbook[]> => request<Textbook[]>("/api/textbooks");

export const deleteTextbook = (textbookId: string): Promise<{ deleted: boolean; textbook_id: string }> =>
  request<{ deleted: boolean; textbook_id: string }>(`/api/textbooks/${encodeURIComponent(textbookId)}`, { method: "DELETE" });

export const buildKG = (textbookId: string): Promise<KnowledgeGraphData> =>
  request<KnowledgeGraphData>(`/api/kg/build/${encodeURIComponent(textbookId)}`, { method: "POST" });

export const getKG = (textbookId: string): Promise<KnowledgeGraphData> =>
  request<KnowledgeGraphData>(`/api/kg/${encodeURIComponent(textbookId)}`);

export const getAllKG = (): Promise<KnowledgeGraphData> => request<KnowledgeGraphData>("/api/kg/all");

export const integrate = (): Promise<IntegrationResult> => request<IntegrationResult>("/api/integrate", { method: "POST" });

export const getDecisions = (): Promise<IntegrationDecision[]> => request<IntegrationDecision[]>("/api/integrate/decisions");

export const overrideDecision = (
  decisionId: string,
  action: DecisionAction,
  reason = "用户手动覆盖",
): Promise<IntegrationDecision> =>
  request<IntegrationDecision>("/api/integrate/override", {
    method: "POST",
    body: JSON.stringify({ decision_id: decisionId, action, reason }),
  });

export const getStats = (): Promise<IntegrationStats> => request<IntegrationStats>("/api/integrate/stats");

export const indexRAG = (): Promise<{ indexed_textbooks: number; total_chunks: number; updated_at: string }> =>
  request<{ indexed_textbooks: number; total_chunks: number; updated_at: string }>("/api/rag/index", { method: "POST" });

export const queryRAG = (query: string): Promise<RAGResponse> =>
  request<RAGResponse>("/api/rag/query", { method: "POST", body: JSON.stringify({ query }) });

export const getRAGStatus = (): Promise<RAGStatus> => request<RAGStatus>("/api/rag/status");

export const sendChat = (message: string, conversationId?: string): Promise<DialogueResponse> =>
  request<DialogueResponse>("/api/dialogue/chat", {
    method: "POST",
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

export const getHistory = (conversationId?: string): Promise<{ conversation_id?: string; messages: ChatMessage[] }> => {
  const suffix = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
  return request<{ conversation_id?: string; messages: ChatMessage[] }>(`/api/dialogue/history${suffix}`);
};

export const getReport = (): Promise<ReportData> => request<ReportData>("/api/report");
