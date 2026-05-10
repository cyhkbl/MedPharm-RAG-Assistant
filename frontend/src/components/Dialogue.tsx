import { FormEvent, useState } from "react";
import type { ChatMessage } from "../api/client";

interface DialogueProps {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (message: string) => Promise<void>;
}

export function Dialogue({ messages, loading, onSend }: DialogueProps) {
  const [message, setMessage] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = message.trim();
    if (!text) return;
    setMessage("");
    void onSend(text);
  };

  return (
    <section className="tab-content dialogue-panel">
      <div className="dialogue-scroll">
        {messages.length === 0 ? (
          <div className="empty-state">
            <span>与整合智能体对话</span>
            <small>可以要求解释决策、保留节点、拆分概念或调整合并策略。</small>
          </div>
        ) : (
          messages.map((item, index) => (
            <div className={`bubble ${item.role}`} key={`${item.timestamp}-${index}`}>
              <p>{item.content}</p>
              <time>{new Date(item.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</time>
            </div>
          ))
        )}
      </div>
      <form className="chat-input" onSubmit={submit}>
        <input value={message} onChange={(event) => setMessage(event.target.value)} placeholder="例如：请保留白细胞与粒细胞两个节点" />
        <button className="primary-button" type="submit" disabled={loading || !message.trim()}>
          发送
        </button>
      </form>
    </section>
  );
}
