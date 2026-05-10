import type { IntegrationDecision, ReportData } from "../api/client";

interface ReportProps {
  report: ReportData | null;
  loading: boolean;
  onRefresh: () => Promise<void>;
}

const ACTION_TEXT: Record<string, string> = { merge: "合并", keep: "保留", remove: "移除" };

function reportToMarkdown(report: ReportData): string {
  const lines = [
    "# 医学教材知识整合报告",
    "",
    "## 总览",
    `- 教材数量：${report.original_stats.total_textbooks}`,
    `- 章节数量：${report.original_stats.total_chapters}`,
    `- 原始字符：${report.original_stats.total_chars}`,
    `- 压缩字符：${report.compressed_stats.compressed_chars}`,
    `- 压缩后占比：${(report.compressed_stats.compression_ratio * 100).toFixed(1)}%`,
    "",
    "## 决策摘要",
    `- 合并：${report.decision_summary.merge || 0}`,
    `- 保留：${report.decision_summary.keep || 0}`,
    `- 移除：${report.decision_summary.remove || 0}`,
    "",
    "## 知识图谱",
    `- 节点：${report.knowledge_graph_stats.nodes}`,
    `- 关系：${report.knowledge_graph_stats.edges}`,
    `- 已构建教材：${report.knowledge_graph_stats.textbooks_with_graph}`,
    "",
    "## 典型整合案例",
    ...report.notable_integration_cases.map(
      (item) => `- ${ACTION_TEXT[item.action] || item.action}：${item.affected_nodes.join("、")}；置信度 ${(item.confidence * 100).toFixed(0)}%；原因：${item.reason}`,
    ),
  ];
  return lines.join("\n");
}

function exportMarkdown(report: ReportData) {
  const blob = new Blob([reportToMarkdown(report)], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "医学教材知识整合报告.md";
  anchor.click();
  URL.revokeObjectURL(url);
}

function CaseRow({ item }: { item: IntegrationDecision }) {
  return (
    <tr>
      <td>{ACTION_TEXT[item.action] || item.action}</td>
      <td>{item.affected_nodes.join("、")}</td>
      <td>{Math.round(item.confidence * 100)}%</td>
    </tr>
  );
}

export function Report({ report, loading, onRefresh }: ReportProps) {
  if (!report) {
    return (
      <section className="tab-content">
        <button className="primary-button full-width" type="button" disabled={loading} onClick={() => void onRefresh()}>
          生成报告
        </button>
        <div className="empty-state">
          <span>暂无整合报告</span>
          <small>完成图谱构建和整合后生成汇总报告。</small>
        </div>
      </section>
    );
  }

  return (
    <section className="tab-content report-panel">
      <div className="report-actions">
        <button className="secondary-button" type="button" disabled={loading} onClick={() => void onRefresh()}>
          刷新报告
        </button>
        <button className="primary-button" type="button" onClick={() => exportMarkdown(report)}>
          导出 Markdown
        </button>
      </div>

      <div className="stats-grid">
        <div className="metric-card">
          <span>教材</span>
          <strong>{report.original_stats.total_textbooks}</strong>
        </div>
        <div className="metric-card">
          <span>原始字符</span>
          <strong>{report.original_stats.total_chars.toLocaleString("zh-CN")}</strong>
        </div>
        <div className="metric-card">
          <span>压缩字符</span>
          <strong>{report.compressed_stats.compressed_chars.toLocaleString("zh-CN")}</strong>
        </div>
        <div className="metric-card">
          <span>压缩后占比</span>
          <strong>{(report.compressed_stats.compression_ratio * 100).toFixed(1)}%</strong>
        </div>
      </div>

      <table className="summary-table">
        <thead>
          <tr>
            <th>决策</th>
            <th>数量</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>合并</td>
            <td>{report.decision_summary.merge || 0}</td>
          </tr>
          <tr>
            <td>保留</td>
            <td>{report.decision_summary.keep || 0}</td>
          </tr>
          <tr>
            <td>移除</td>
            <td>{report.decision_summary.remove || 0}</td>
          </tr>
        </tbody>
      </table>

      <div className="kg-stats">
        <span>图谱节点 {report.knowledge_graph_stats.nodes}</span>
        <span>关系边 {report.knowledge_graph_stats.edges}</span>
        <span>已构建 {report.knowledge_graph_stats.textbooks_with_graph}</span>
      </div>

      <table className="summary-table">
        <thead>
          <tr>
            <th>动作</th>
            <th>节点</th>
            <th>置信度</th>
          </tr>
        </thead>
        <tbody>{report.notable_integration_cases.map((item) => <CaseRow item={item} key={item.decision_id} />)}</tbody>
      </table>
    </section>
  );
}
