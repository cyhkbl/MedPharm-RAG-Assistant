import { useMemo, useState } from "react";
import type { DecisionAction, IntegrationDecision, IntegrationStats } from "../api/client";

interface IntegrationPanelProps {
  decisions: IntegrationDecision[];
  stats: IntegrationStats | null;
  loading: boolean;
  onRun: () => Promise<void>;
  onOverride: (decisionId: string, action: DecisionAction) => Promise<void>;
}

const ACTION_TEXT: Record<DecisionAction, string> = { merge: "合并", keep: "保留", remove: "移除" };

export function IntegrationPanel({ decisions, stats, loading, onRun, onOverride }: IntegrationPanelProps) {
  const [filter, setFilter] = useState<DecisionAction | "all">("all");
  const filtered = useMemo(() => decisions.filter((item) => filter === "all" || item.action === filter), [decisions, filter]);
  const ratio = stats ? Math.round((1 - stats.compression_ratio) * 100) : 0;

  return (
    <section className="tab-content">
      <button className="primary-button full-width" type="button" disabled={loading} onClick={() => void onRun()}>
        {loading ? "整合中" : "运行跨教材整合"}
      </button>

      <div className="stats-grid">
        <div className="metric-card">
          <span>原始字符</span>
          <strong>{stats?.original_chars.toLocaleString("zh-CN") || 0}</strong>
        </div>
        <div className="metric-card">
          <span>压缩字符</span>
          <strong>{stats?.compressed_chars.toLocaleString("zh-CN") || 0}</strong>
        </div>
        <div className="metric-card wide">
          <span>压缩率</span>
          <strong>{ratio}%</strong>
          <div className="progress-shell">
            <span style={{ width: `${Math.max(0, Math.min(100, ratio))}%` }} />
          </div>
        </div>
      </div>

      <div className="filter-row">
        {(["all", "merge", "keep", "remove"] as const).map((item) => (
          <button key={item} className={filter === item ? "active" : ""} type="button" onClick={() => setFilter(item)}>
            {item === "all" ? "全部" : ACTION_TEXT[item]}
          </button>
        ))}
      </div>

      <div className="decision-list">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <span>暂无整合决策</span>
            <small>运行整合后可查看合并、保留与移除原因。</small>
          </div>
        ) : (
          filtered.map((decision) => (
            <article className="decision-card" key={decision.decision_id}>
              <div className="decision-head">
                <span className={`action-chip ${decision.action}`}>{ACTION_TEXT[decision.action]}</span>
                <strong>{Math.round(decision.confidence * 100)}%</strong>
              </div>
              <p>{decision.reason}</p>
              <small>影响节点：{decision.affected_nodes.join("、")}</small>
              <div className="override-row">
                {(["merge", "keep", "remove"] as DecisionAction[]).map((action) => (
                  <button className={action} key={action} type="button" onClick={() => void onOverride(decision.decision_id, action)}>
                    改为{ACTION_TEXT[action]}
                  </button>
                ))}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
