import { useEffect, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { getDifficulty, getLearningPath, type DifficultyAssessment, type LearningPath } from "../api/client";

export function LearningPanel() {
  const [difficulty, setDifficulty] = useState<DifficultyAssessment | null>(null);
  const [path, setPath] = useState<LearningPath | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [d, p] = await Promise.all([getDifficulty(), getLearningPath()]);
      setDifficulty(d);
      setPath(p);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const pathOption: EChartsOption | null = path && path.path.length > 0 ? {
    backgroundColor: "transparent",
    tooltip: { trigger: "item", backgroundColor: "#fff", borderColor: "#e5e5e0", textStyle: { color: "#333" } },
    series: [{
      type: "graph",
      layout: "force",
      roam: true,
      draggable: true,
      data: path.path.map((step, i) => ({
        id: step.node_id,
        name: step.name,
        symbolSize: 30 + (path.total_steps - i) * 2,
        itemStyle: { color: i === 0 ? "#16a34a" : i === path.path.length - 1 ? "#dc2626" : "#2563eb" },
        label: { show: true, color: "#333", fontSize: 10 },
      })),
      links: path.path.slice(0, -1).map((step, i) => ({
        source: step.node_id,
        target: path.path[i + 1].node_id,
        lineStyle: { color: "#999", width: 1.5 },
      })),
      force: { repulsion: 200, gravity: 0.1, edgeLength: [60, 120] },
    }],
  } : null;

  if (loading && !difficulty) {
    return <section className="tab-content"><div className="empty-state">加载中...</div></section>;
  }

  return (
    <section className="tab-content">
      <div className="stats-grid">
        <div className="metric-card">
          <span>入门</span>
          <strong style={{ color: "#16a34a" }}>{difficulty?.by_level["入门"] || 0}</strong>
        </div>
        <div className="metric-card">
          <span>中级</span>
          <strong style={{ color: "#d97706" }}>{difficulty?.by_level["中级"] || 0}</strong>
        </div>
        <div className="metric-card">
          <span>高级</span>
          <strong style={{ color: "#dc2626" }}>{difficulty?.by_level["高级"] || 0}</strong>
        </div>
        <div className="metric-card">
          <span>学习路径</span>
          <strong>{path?.total_steps || 0} 步</strong>
        </div>
      </div>

      {pathOption && (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ fontSize: 14, color: "#333", marginBottom: 8 }}>推荐学习路径（入门 → 高级）</h3>
          <ReactECharts option={pathOption} style={{ width: "100%", height: 300 }} />
        </div>
      )}

      {difficulty && difficulty.items.length > 0 && (
        <table className="summary-table" style={{ marginTop: 16 }}>
          <thead>
            <tr>
              <th>知识点</th>
              <th>难度</th>
              <th>前置数</th>
              <th>频次</th>
            </tr>
          </thead>
          <tbody>
            {difficulty.items.slice(0, 20).map((item) => (
              <tr key={item.node_id}>
                <td>{item.name}</td>
                <td><span style={{ color: item.difficulty === 1 ? "#16a34a" : item.difficulty === 2 ? "#d97706" : "#dc2626" }}>{item.label}</span></td>
                <td>{item.prerequisite_count}</td>
                <td>{item.frequency}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <button className="secondary-button full-width" type="button" style={{ marginTop: 16 }} onClick={() => void loadData()}>
        刷新
      </button>
    </section>
  );
}
