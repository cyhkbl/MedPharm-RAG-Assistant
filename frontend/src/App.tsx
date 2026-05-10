import { Component, ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  buildKG,
  deleteTextbook,
  getAllKG,
  getDecisions,
  getHistory,
  getRAGStatus,
  getReport,
  getTokenStats,
  type TokenStats,
  getStats,
  getTextbooks,
  indexRAG,
  integrate,
  overrideDecision,
  queryRAG,
  sendChat,
  uploadFile,
  type ChatMessage,
  type DecisionAction,
  type IntegrationDecision,
  type IntegrationStats,
  type KnowledgeGraphData,
  type RAGResponse,
  type RAGStatus,
  type ReportData,
  type Textbook,
} from "./api/client";
import { Dialogue } from "./components/Dialogue";
import { FileUpload } from "./components/FileUpload";
import { IntegrationPanel } from "./components/IntegrationPanel";
import { KnowledgeGraph } from "./components/KnowledgeGraph";
import { RAGChat } from "./components/RAGChat";
import { Report } from "./components/Report";
import { LearningPanel } from "./components/LearningPanel";

type TabKey = "integration" | "rag" | "dialogue" | "report" | "learning";
type ToastKind = "success" | "error" | "info";

interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "integration", label: "整合" },
  { key: "rag", label: "问答" },
  { key: "dialogue", label: "对话" },
  { key: "report", label: "报告" },
  { key: "learning", label: "学习" },
];

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; message: string }> {
  state = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="fatal-error">
          <strong>界面渲染失败</strong>
          <span>{this.state.message || "请刷新页面重试。"}</span>
        </div>
      );
    }
    return this.props.children;
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "未知错误";
}

function App() {
  const [textbooks, setTextbooks] = useState<Textbook[]>([]);
  const [graph, setGraph] = useState<KnowledgeGraphData>({ nodes: [], edges: [] });
  const [decisions, setDecisions] = useState<IntegrationDecision[]>([]);
  const [stats, setStats] = useState<IntegrationStats | null>(null);
  const [ragStatus, setRagStatus] = useState<RAGStatus | null>(null);
  const [ragHistory, setRagHistory] = useState<Array<{ query: string; response: RAGResponse }>>([]);
  const [dialogueMessages, setDialogueMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [report, setReport] = useState<ReportData | null>(null);
  const [tokenStats, setTokenStats] = useState<TokenStats | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("integration");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [graphLoading, setGraphLoading] = useState(false);
  const [panelLoading, setPanelLoading] = useState(false);
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());

  const integrated = decisions.length > 0;

  const showToast = useCallback((message: string, kind: ToastKind = "info") => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, kind, message }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 3600);
  }, []);

  const refreshCore = useCallback(async () => {
    const [books, kg, decisionList, integrationStats, status] = await Promise.all([
      getTextbooks(),
      getAllKG().catch(() => ({ nodes: [], edges: [] })),
      getDecisions().catch(() => []),
      getStats().catch(() => null),
      getRAGStatus().catch(() => null),
    ]);
    setTextbooks(books);
    setGraph(kg);
    setDecisions(decisionList);
    setStats(integrationStats);
    setRagStatus(status);
  }, []);

  useEffect(() => {
    void refreshCore().catch((error) => showToast(`加载失败：${errorMessage(error)}`, "error"));
    void getHistory()
      .then((payload) => setDialogueMessages(payload.messages || []))
      .catch(() => undefined);
  }, [refreshCore, showToast]);

  const handleUpload = async (files: File[]) => {
    setUploading(true);
    setUploadProgress(8);
    try {
      for (let index = 0; index < files.length; index += 1) {
        await uploadFile(files[index]);
        setUploadProgress(Math.round(((index + 1) / files.length) * 100));
      }
      await refreshCore();
      showToast("教材上传并解析完成", "success");
    } catch (error) {
      showToast(`上传失败：${errorMessage(error)}`, "error");
    } finally {
      setUploading(false);
      window.setTimeout(() => setUploadProgress(0), 500);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTextbook(id);
      await refreshCore();
      showToast("教材已删除", "success");
    } catch (error) {
      showToast(`删除失败：${errorMessage(error)}`, "error");
    }
  };

  const handleBuildKG = async (id: string) => {
    setBusyIds((current) => new Set(current).add(id));
    setGraphLoading(true);
    try {
      const kg = await buildKG(id);
      setGraph(kg.nodes.length ? await getAllKG() : kg);
      showToast("知识图谱构建完成", "success");
    } catch (error) {
      showToast(`构建失败：${errorMessage(error)}`, "error");
    } finally {
      setBusyIds((current) => {
        const next = new Set(current);
        next.delete(id);
        return next;
      });
      setGraphLoading(false);
    }
  };

  const handleBuildAll = async () => {
    setGraphLoading(true);
    try {
      for (const book of textbooks) {
        setBusyIds((current) => new Set(current).add(book.id));
        await buildKG(book.id);
      }
      setGraph(await getAllKG());
      showToast("全部教材图谱已构建", "success");
    } catch (error) {
      showToast(`全部构建失败：${errorMessage(error)}`, "error");
    } finally {
      setBusyIds(new Set());
      setGraphLoading(false);
    }
  };

  const handleIntegrate = async () => {
    setPanelLoading(true);
    setGraphLoading(true);
    try {
      const result = await integrate();
      setDecisions(result.decisions);
      setStats(await getStats());
      setReport(await getReport().catch(() => null));
      setTokenStats(await getTokenStats().catch(() => null));
      showToast("跨教材整合完成", "success");
    } catch (error) {
      showToast(`整合失败：${errorMessage(error)}`, "error");
    } finally {
      setPanelLoading(false);
      setGraphLoading(false);
    }
  };

  const handleOverride = async (decisionId: string, action: DecisionAction) => {
    try {
      await overrideDecision(decisionId, action);
      setDecisions(await getDecisions());
      setStats(await getStats());
      showToast("决策已覆盖", "success");
    } catch (error) {
      showToast(`覆盖失败：${errorMessage(error)}`, "error");
    }
  };

  const handleIndex = async () => {
    setPanelLoading(true);
    try {
      await indexRAG();
      setRagStatus(await getRAGStatus());
      showToast("RAG 索引已建立", "success");
    } catch (error) {
      showToast(`索引失败：${errorMessage(error)}`, "error");
    } finally {
      setPanelLoading(false);
    }
  };

  const handleAsk = async (query: string) => {
    setPanelLoading(true);
    try {
      const response = await queryRAG(query);
      setRagHistory((current) => [...current, { query, response }]);
    } catch (error) {
      showToast(`问答失败：${errorMessage(error)}`, "error");
    } finally {
      setPanelLoading(false);
    }
  };

  const handleDialogue = async (message: string) => {
    const now = new Date().toISOString();
    setDialogueMessages((current) => [...current, { role: "user", content: message, timestamp: now }]);
    setPanelLoading(true);
    try {
      const response = await sendChat(message, conversationId);
      setConversationId(response.conversation_id);
      setDialogueMessages((current) => [...current, { role: "assistant", content: response.message, timestamp: response.timestamp }]);
      // 如果对话修改了整合决策，刷新图谱和决策列表
      if (response.message.includes("已将决策")) {
        setDecisions(await getDecisions());
        setStats(await getStats());
        setGraph(await getAllKG());
        showToast("决策已更新，图谱已刷新", "success");
      }
    } catch (error) {
      showToast(`对话失败：${errorMessage(error)}`, "error");
    } finally {
      setPanelLoading(false);
    }
  };

  const handleReport = async () => {
    setPanelLoading(true);
    try {
      setReport(await getReport());
      setTokenStats(await getTokenStats().catch(() => null));
      showToast("报告已更新", "success");
    } catch (error) {
      showToast(`报告生成失败：${errorMessage(error)}`, "error");
    } finally {
      setPanelLoading(false);
    }
  };

  const panel = useMemo(() => {
    if (activeTab === "integration") {
      return (
        <IntegrationPanel
          decisions={decisions}
          stats={stats}
          loading={panelLoading}
          onRun={handleIntegrate}
          onOverride={handleOverride}
        />
      );
    }
    if (activeTab === "rag") {
      return <RAGChat status={ragStatus} history={ragHistory} loading={panelLoading} onBuildIndex={handleIndex} onAsk={handleAsk} />;
    }
    if (activeTab === "dialogue") {
      return <Dialogue messages={dialogueMessages} loading={panelLoading} onSend={handleDialogue} />;
    }
    if (activeTab === "learning") {
      return <LearningPanel />;
    }
    return <Report report={report} tokenStats={tokenStats} loading={panelLoading} onRefresh={handleReport} />;
  }, [activeTab, decisions, dialogueMessages, panelLoading, ragHistory, ragStatus, report, stats]);

  return (
    <ErrorBoundary>
      <div className="app-shell">
        <FileUpload
          textbooks={textbooks}
          busyIds={busyIds}
          uploading={uploading}
          uploadProgress={uploadProgress}
          onUpload={handleUpload}
          onDelete={handleDelete}
          onBuildKG={handleBuildKG}
        />
        <KnowledgeGraph
          graph={graph}
          textbooks={textbooks}
          loading={graphLoading}
          integrated={integrated}
          decisions={decisions}
          onBuildAll={handleBuildAll}
          onIntegrate={handleIntegrate}
        />
        <aside className="right-panel panel-column">
          <div className="panel-header">
            <div>
              <p className="eyebrow">智能体工作台</p>
              <h2>整合控制</h2>
            </div>
          </div>
          <nav className="tabs">
            {TABS.map((tab) => (
              <button key={tab.key} className={activeTab === tab.key ? "active" : ""} type="button" onClick={() => setActiveTab(tab.key)}>
                {tab.label}
              </button>
            ))}
          </nav>
          {panel}
        </aside>
        <div className="toast-stack" aria-live="polite">
          {toasts.map((toast) => (
            <div className={`toast ${toast.kind}`} key={toast.id}>
              {toast.message}
            </div>
          ))}
        </div>
      </div>
    </ErrorBoundary>
  );
}

export default App;
