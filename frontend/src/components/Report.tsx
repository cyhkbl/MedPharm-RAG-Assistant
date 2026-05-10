import { getReportPDF, type IntegrationDecision, type ReportData, type TokenStats } from "../api/client";

interface ReportProps {
  report: ReportData | null;
  tokenStats: TokenStats | null;
  loading: boolean;
  onRefresh: () => Promise<void>;
}

const ACTION_TEXT: Record<string, string> = { merge: "合并", keep: "保留", remove: "移除" };

function reportToMarkdown(report: ReportData, tokenStats: TokenStats | null): string {
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
  if (tokenStats) {
    lines.push(
      "",
      "## Token 消耗统计",
      `- 总调用次数：${tokenStats.total_calls}`,
      `- 总 Token：${tokenStats.total_tokens.toLocaleString("zh-CN")}`,
      `- 输入 Token：${tokenStats.total_input_tokens.toLocaleString("zh-CN")}`,
      `- 输出 Token：${tokenStats.total_output_tokens.toLocaleString("zh-CN")}`,
      `- 推理 Token：${tokenStats.total_reasoning_tokens.toLocaleString("zh-CN")}`,
      `- 平均耗时：${tokenStats.avg_elapsed_ms.toFixed(0)}ms`,
    );
  }
  return lines.join("\n");
}

function exportMarkdown(report: ReportData, tokenStats: TokenStats | null) {
  const blob = new Blob([reportToMarkdown(report, tokenStats)], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "医学教材知识整合报告.md";
  anchor.click();
  URL.revokeObjectURL(url);
}

async function exportPDF() {
  try {
    const blob = await getReportPDF();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "integration_report.pdf";
    anchor.click();
    URL.revokeObjectURL(url);
  } catch {
    alert("PDF export failed");
  }
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

export function Report({ report, tokenStats, loading, onRefresh }: ReportProps) {
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
        <button className="primary-button" type="button" onClick={() => exportMarkdown(report, tokenStats)}>
          导出 Markdown
        </button>
        <button className="secondary-button" type="button" onClick={() => void exportPDF()}>
          导出 PDF
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

      {/* Token 消耗统计 */}
      {tokenStats && (
        <>
          <h3 style={{ margin: "16px 0 8px", fontSize: 14, color: "#333" }}>Token 消耗</h3>
          <div className="stats-grid">
            <div className="metric-card">
              <span>总调用</span>
              <strong>{tokenStats.total_calls}</strong>
            </div>
            <div className="metric-card">
              <span>总 Token</span>
              <strong>{tokenStats.total_tokens.toLocaleString("zh-CN")}</strong>
            </div>
            <div className="metric-card">
              <span>输入</span>
              <strong>{tokenStats.total_input_tokens.toLocaleString("zh-CN")}</strong>
            </div>
            <div className="metric-card">
              <span>输出</span>
              <strong>{tokenStats.total_output_tokens.toLocaleString("zh-CN")}</strong>
            </div>
            <div className="metric-card">
              <span>推理</span>
              <strong>{tokenStats.total_reasoning_tokens.toLocaleString("zh-CN")}</strong>
            </div>
            <div className="metric-card">
              <span>平均耗时</span>
              <strong>{tokenStats.avg_elapsed_ms.toFixed(0)}ms</strong>
            </div>
          </div>
        </>
      )}

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
