import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";

const API = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8100";

interface QuizQuestion {
  type: string;
  difficulty: string;
  question: string;
  options: string[];
  answer: string;
  explanation: string;
  knowledge_points: string[];
}

interface OutlineChapter {
  title: string;
  hours: number;
  objectives: string[];
  key_points: string[];
  prerequisites: string[];
}

interface CoverageData {
  textbooks: string[];
  categories: string[];
  matrix: number[][];
  gaps: Array<{ textbook: string; category: string; count: number }>;
}

export function TeachingPanel() {
  const [tab, setTab] = useState<"quiz" | "outline" | "heatmap">("quiz");
  const [quiz, setQuiz] = useState<QuizQuestion[]>([]);
  const [outline, setOutline] = useState<{ course_name: string; total_hours: number; chapters: OutlineChapter[] } | null>(null);
  const [coverage, setCoverage] = useState<CoverageData | null>(null);
  const [loading, setLoading] = useState(false);
  const [showAnswer, setShowAnswer] = useState<Set<number>>(new Set());

  useEffect(() => {
    void loadCoverage();
  }, []);

  const loadCoverage = async () => {
    try {
      const res = await fetch(`${API}/api/teaching/coverage`);
      setCoverage(await res.json());
    } catch { /* ignore */ }
  };

  const loadQuiz = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/teaching/quiz?n=10`);
      const data = await res.json();
      setQuiz(data.questions || []);
      setShowAnswer(new Set());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  const loadOutline = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/teaching/outline`);
      setOutline(await res.json());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  // 热力图配置
  const heatmapOption: EChartsOption | null = useMemo(() => {
    if (!coverage || !coverage.matrix.length) return null;
    const data: number[][] = [];
    coverage.textbooks.forEach((_, ti) => {
      coverage.categories.forEach((_, ci) => {
        data.push([ci, ti, coverage.matrix[ti][ci]]);
      });
    });
    return {
      tooltip: { position: "top", backgroundColor: "#fff", borderColor: "#e5e5e0", textStyle: { color: "#333" } },
      grid: { top: 40, bottom: 80, left: 120, right: 40 },
      xAxis: { type: "category", data: coverage.categories, axisLabel: { rotate: 45, fontSize: 10, color: "#666" }, splitArea: { show: true } },
      yAxis: { type: "category", data: coverage.textbooks.map((t) => t.replace(/tb_|\.pdf/g, "").slice(0, 12)), axisLabel: { fontSize: 10, color: "#666" }, splitArea: { show: true } },
      visualMap: { min: 0, max: Math.max(...data.map((d) => d[2]), 1), calculable: true, orient: "horizontal", left: "center", bottom: 10, inRange: { color: ["#f7fafc", "#bee3f8", "#3182ce", "#1a365d"] }, textStyle: { color: "#666" } },
      series: [{ type: "heatmap", data, label: { show: true, color: "#333", fontSize: 11 }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0, 0, 0, 0.5)" } } }],
    };
  }, [coverage]);

  return (
    <section className="tab-content">
      <div className="segmented" style={{ marginBottom: 12 }}>
        <button className={tab === "quiz" ? "active" : ""} type="button" onClick={() => setTab("quiz")}>AI 测验</button>
        <button className={tab === "outline" ? "active" : ""} type="button" onClick={() => setTab("outline")}>教学大纲</button>
        <button className={tab === "heatmap" ? "active" : ""} type="button" onClick={() => setTab("heatmap")}>覆盖热力图</button>
      </div>

      {tab === "quiz" && (
        <>
          <button className="primary-button full-width" type="button" disabled={loading} onClick={() => void loadQuiz()}>
            {loading ? "生成中..." : "AI 生成 10 道测验题"}
          </button>
          {quiz.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <p style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>共 {quiz.length} 题</p>
              {quiz.map((q, i) => (
                <div key={i} style={{ background: "#fff", border: "1px solid #e5e5e0", borderRadius: 6, padding: 12, marginBottom: 8 }}>
                  <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: q.difficulty === "简单" ? "#16a34a" : q.difficulty === "中等" ? "#d97706" : "#dc2626" }}>{q.difficulty}</span>
                    <span style={{ fontSize: 11, color: "#999" }}>{q.type}</span>
                  </div>
                  <p style={{ fontSize: 14, color: "#333", marginBottom: 8 }}>{i + 1}. {q.question}</p>
                  {q.options.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      {q.options.map((opt, j) => <p key={j} style={{ fontSize: 13, color: "#666", margin: "2px 0" }}>{opt}</p>)}
                    </div>
                  )}
                  <button className="secondary-button" type="button" style={{ fontSize: 12, padding: "4px 12px" }} onClick={() => { const s = new Set(showAnswer); s.has(i) ? s.delete(i) : s.add(i); setShowAnswer(s); }}>
                    {showAnswer.has(i) ? "隐藏答案" : "查看答案"}
                  </button>
                  {showAnswer.has(i) && (
                    <div style={{ marginTop: 8, padding: 8, background: "#f0fdf4", borderRadius: 4, border: "1px solid #bbf7d0" }}>
                      <p style={{ fontSize: 13, color: "#16a34a" }}><strong>答案：</strong>{q.answer}</p>
                      <p style={{ fontSize: 12, color: "#666", marginTop: 4 }}><strong>解析：</strong>{q.explanation}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "outline" && (
        <>
          <button className="primary-button full-width" type="button" disabled={loading} onClick={() => void loadOutline()}>
            {loading ? "生成中..." : "AI 生成教学大纲"}
          </button>
          {outline && (
            <div style={{ marginTop: 12 }}>
              <h3 style={{ fontSize: 15, color: "#333" }}>{outline.course_name}</h3>
              <p style={{ fontSize: 13, color: "#666", marginBottom: 12 }}>总学时：{outline.total_hours}</p>
              {outline.chapters.map((ch, i) => (
                <div key={i} style={{ background: "#fff", border: "1px solid #e5e5e0", borderRadius: 6, padding: 12, marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <strong style={{ fontSize: 14, color: "#333" }}>{ch.title}</strong>
                    <span style={{ fontSize: 12, color: "#999" }}>{ch.hours} 学时</span>
                  </div>
                  <p style={{ fontSize: 12, color: "#666", marginBottom: 4 }}><strong>教学目标：</strong>{ch.objectives.join("；")}</p>
                  <p style={{ fontSize: 12, color: "#666" }}><strong>重点：</strong>{ch.key_points.join("、")}</p>
                  {ch.prerequisites.length > 0 && <p style={{ fontSize: 11, color: "#999", marginTop: 4 }}>前置：{ch.prerequisites.join("、")}</p>}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "heatmap" && (
        <>
          {heatmapOption ? (
            <>
              <p style={{ fontSize: 13, color: "#666", marginBottom: 8 }}>教材 × 知识点分类覆盖矩阵（颜色越深=覆盖越多）</p>
              <ReactECharts option={heatmapOption} style={{ width: "100%", height: 400 }} />
              {coverage && coverage.gaps.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <p style={{ fontSize: 13, color: "#dc2626", marginBottom: 4 }}>⚠ 知识盲区（{coverage.gaps.length} 项）：</p>
                  {coverage.gaps.slice(0, 5).map((g, i) => (
                    <p key={i} style={{ fontSize: 12, color: "#666" }}>• {g.textbook.slice(0, 12)} 缺少「{g.category}」相关内容</p>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">构建知识图谱后，将在此显示教材覆盖热力图。</div>
          )}
        </>
      )}
    </section>
  );
}
