import { FormEvent, useState } from "react";
import type { RAGResponse, RAGStatus } from "../api/client";

interface RAGChatProps {
  status: RAGStatus | null;
  history: Array<{ query: string; response: RAGResponse }>;
  loading: boolean;
  onBuildIndex: () => Promise<void>;
  onAsk: (query: string) => Promise<void>;
}

export function RAGChat({ status, history, loading, onBuildIndex, onAsk }: RAGChatProps) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = query.trim();
    if (!text) return;
    setQuery("");
    void onAsk(text);
  };

  return (
    <section className="tab-content rag-panel">
      <div className="status-bar">
        <span className={status?.ready ? "ready-dot ready" : "ready-dot"} />
        <div>
          <strong>{status?.ready ? "索引可用" : "索引未建立"}</strong>
          <small>
            {status?.indexed_textbooks || 0} 本教材 · {status?.total_chunks || 0} 个片段
          </small>
        </div>
        <button className="secondary-button" type="button" disabled={loading} onClick={() => void onBuildIndex()}>
          建立索引
        </button>
      </div>

      <div className="chat-history">
        {history.length === 0 ? (
          <div className="empty-state">
            <span>输入医学问题</span>
            <small>回答会附带教材、章节、页码与相关原文片段。</small>
          </div>
        ) : (
          history.map((item, index) => (
            <article className="qa-card" key={`${item.query}-${index}`}>
              <div className="bubble user">{item.query}</div>
              <div className="answer-block">
                <p>{item.response.answer}</p>
                <div className="citation-list">
                  {item.response.citations.map((citation, citationIndex) => {
                    const key = `${index}-${citationIndex}`;
                    return (
                      <div className="citation" key={key}>
                        <button type="button" onClick={() => setExpanded(expanded === key ? null : key)}>
                          {citation.textbook} · {citation.chapter} · 第 {citation.page} 页
                          <span>{Math.round(citation.relevance_score * 100)}%</span>
                        </button>
                        {expanded === key && (
                          <div className="source-chunks">
                            {citation.source_chunks.map((chunk, chunkIndex) => (
                              <p key={chunkIndex}>{chunk}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </article>
          ))
        )}
      </div>

      <form className="chat-input" onSubmit={submit}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="询问教材中的概念、机制或用药依据" />
        <button className="primary-button" type="submit" disabled={loading || !query.trim()}>
          发送
        </button>
      </form>
    </section>
  );
}
