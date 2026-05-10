import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { KnowledgeEdge, KnowledgeGraphData, KnowledgeNode, Textbook } from "../api/client";

interface KnowledgeGraphProps {
  graph: KnowledgeGraphData;
  textbooks: Textbook[];
  loading: boolean;
  integrated: boolean;
  onBuildAll: () => Promise<void>;
  onIntegrate: () => Promise<void>;
}

type ViewMode = "force" | "tree" | "compare";

const PALETTE = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#64748b", "#0891b2", "#7c3aed", "#65a30d"];
const EDGE_LABELS: Record<string, string> = {
  prerequisite: "前置",
  parallel: "并列",
  contains: "包含",
  applies_to: "应用",
};

function colorMap(textbooks: Textbook[]): Record<string, string> {
  return textbooks.reduce<Record<string, string>>((acc, item, index) => {
    acc[item.id] = PALETTE[index % PALETTE.length];
    return acc;
  }, {});
}

function textbookName(textbooks: Textbook[], id: string): string {
  return textbooks.find((item) => item.id === id)?.title || textbooks.find((item) => item.id === id)?.filename || id;
}

function uniqueEdgeTypes(edges: KnowledgeEdge[]): string[] {
  return Array.from(new Set(edges.map((edge) => edge.relation_type))).sort();
}

function makeTree(nodes: KnowledgeNode[], textbooks: Textbook[]) {
  return {
    name: "教材知识库",
    children: textbooks.map((book) => ({
      name: book.title || book.filename,
      children: nodes
        .filter((node) => node.textbook_id === book.id)
        .slice(0, 120)
        .map((node) => ({
          name: node.name,
          value: node.frequency,
          itemStyle: { color: colorMap(textbooks)[book.id] },
        })),
    })),
  };
}

export function KnowledgeGraph({ graph, textbooks, loading, integrated, onBuildAll, onIntegrate }: KnowledgeGraphProps) {
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("force");
  const [visibleEdges, setVisibleEdges] = useState<Set<string>>(new Set());

  const colors = useMemo(() => colorMap(textbooks), [textbooks]);
  const edgeTypes = useMemo(() => uniqueEdgeTypes(graph.edges), [graph.edges]);
  const activeEdges = visibleEdges.size ? visibleEdges : new Set(edgeTypes);
  const searchTerm = search.trim().toLowerCase();

  const filteredEdges = graph.edges.filter((edge) => activeEdges.has(edge.relation_type));
  const nodeLookup = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);

  const graphOption: EChartsOption = useMemo(() => {
    const nodes = graph.nodes.map((node) => {
      const matched = searchTerm && node.name.toLowerCase().includes(searchTerm);
      return {
        id: node.id,
        name: node.name,
        value: node.frequency,
        symbolSize: Math.min(68, 22 + node.frequency * 8),
        draggable: true,
        itemStyle: {
          color: colors[node.textbook_id] || "#64748b",
          borderColor: matched ? "#2563eb" : "#ffffff",
          borderWidth: matched ? 3 : 1,
        },
        label: {
          show: matched || node.frequency > 1,
          color: "#333333",
          fontSize: 11,
        },
      };
    });

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: "#ffffff",
        borderColor: "#e5e5e0",
        textStyle: { color: "#333333" },
        formatter: (params: unknown) => {
          const data = (params as { data?: { id?: string; source?: string; target?: string; name?: string } }).data;
          if (data?.id) {
            const node = nodeLookup.get(data.id);
            return node ? `<b>${node.name}</b><br/>${node.category}<br/>频次：${node.frequency}` : data.name || "";
          }
          return data?.source && data?.target ? `${data.source} → ${data.target}` : "";
        },
      },
      legend: {
        data: textbooks.map((item) => item.title || item.filename),
        top: 4,
        left: 10,
        textStyle: { color: "#666666", fontSize: 11 },
      },
      series: [
        {
          type: "graph",
          layout: "force",
          roam: true,
          draggable: true,
          top: 36,
          bottom: 16,
          categories: textbooks.map((item) => ({ name: item.title || item.filename, itemStyle: { color: colors[item.id] } })),
          data: nodes,
          links: filteredEdges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            value: 1,
            lineStyle: {
              color: edge.relation_type === "contains" ? "#16a34a" : edge.relation_type === "prerequisite" ? "#d97706" : "#999999",
              width: edge.relation_type === "contains" ? 1.8 : 1,
              opacity: 0.55,
            },
          })),
          force: {
            repulsion: 260,
            gravity: 0.08,
            edgeLength: [80, 180],
            friction: 0.45,
          },
          emphasis: { focus: "adjacency", lineStyle: { width: 3 } },
          lineStyle: { curveness: 0.15 },
        },
      ],
    };
  }, [colors, filteredEdges, graph.nodes, nodeLookup, searchTerm, textbooks]);

  const treeOption: EChartsOption = useMemo(
    () => ({
      backgroundColor: "transparent",
      tooltip: { trigger: "item", backgroundColor: "#ffffff", borderColor: "#e5e5e0", textStyle: { color: "#333333" } },
      series: [
        {
          type: "tree",
          data: [makeTree(graph.nodes, textbooks)],
          top: "5%",
          left: "8%",
          bottom: "5%",
          right: "18%",
          symbolSize: 9,
          roam: true,
          label: { color: "#333333", fontSize: 11, position: "left", verticalAlign: "middle", align: "right" },
          leaves: { label: { position: "right", align: "left" } },
          lineStyle: { color: "#d4d4cf", width: 1.2 },
          expandAndCollapse: true,
          initialTreeDepth: 2,
          animationDuration: 450,
        },
      ],
    }),
    [graph.nodes, textbooks],
  );

  const compareOption: EChartsOption = useMemo(() => {
    const beforeNodes = graph.nodes.slice(0, 80);
    const afterNodes = integrated ? graph.nodes.filter((node) => node.frequency > 1).slice(0, 80) : graph.nodes.slice(0, 45);
    const toSeries = (nodes: KnowledgeNode[], center: [string, string], title: string) => ({
      name: title,
      type: "graph" as const,
      layout: "force" as const,
      center,
      roam: false,
      data: nodes.map((node) => ({
        id: `${title}-${node.id}`,
        name: node.name,
        symbolSize: Math.min(54, 16 + node.frequency * 7),
        itemStyle: { color: colors[node.textbook_id] || "#64748b" },
        label: { show: node.frequency > 1, color: "#333333", fontSize: 10 },
      })),
      links: [],
      force: { repulsion: 130, gravity: 0.12 },
    });
    return {
      backgroundColor: "transparent",
      title: [
        { text: "整合前", left: "23%", top: 12, textStyle: { color: "#333333", fontSize: 13 } },
        { text: integrated ? "整合后" : "待整合预览", left: "72%", top: 12, textStyle: { color: "#333333", fontSize: 13 } },
      ],
      series: [toSeries(beforeNodes, ["25%", "54%"], "before"), toSeries(afterNodes, ["74%", "54%"], "after")],
    };
  }, [colors, graph.nodes, integrated]);

  const option = viewMode === "tree" ? treeOption : viewMode === "compare" ? compareOption : graphOption;

  const handleChartClick = (params: { data?: { id?: string } }) => {
    if (params.data?.id) {
      const id = params.data.id.replace(/^before-/, "").replace(/^after-/, "");
      setSelectedNode(nodeLookup.get(id) || null);
    }
  };

  return (
    <main className="graph-panel">
      <div className="graph-toolbar">
        <div>
          <p className="eyebrow">知识图谱</p>
          <h1>教材概念整合视图</h1>
        </div>
        <div className="toolbar-actions">
          <input className="search-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索知识点" />
          <div className="segmented">
            <button className={viewMode === "force" ? "active" : ""} type="button" onClick={() => setViewMode("force")}>
              力导向
            </button>
            <button className={viewMode === "tree" ? "active" : ""} type="button" onClick={() => setViewMode("tree")}>
              树结构
            </button>
            <button className={viewMode === "compare" ? "active" : ""} type="button" onClick={() => setViewMode("compare")}>
              对比
            </button>
          </div>
          <button className="secondary-button" type="button" disabled={loading} onClick={() => void onBuildAll()}>
            全部构建
          </button>
          <button className="primary-button" type="button" disabled={loading} onClick={() => void onIntegrate()}>
            执行整合
          </button>
        </div>
      </div>

      <div className="edge-filter">
        {edgeTypes.length === 0 ? (
          <span>暂无关系边</span>
        ) : (
          edgeTypes.map((type) => (
            <label key={type}>
              <input
                type="checkbox"
                checked={activeEdges.has(type)}
                onChange={() => {
                  const next = new Set(activeEdges);
                  if (next.has(type)) next.delete(type);
                  else next.add(type);
                  setVisibleEdges(next);
                }}
              />
              {EDGE_LABELS[type] || type}
            </label>
          ))
        )}
      </div>

      <section className="graph-canvas">
        {loading && (
          <div className="graph-loading">
            <span className="spinner" />
            正在计算知识网络
          </div>
        )}
        {graph.nodes.length === 0 ? (
          <div className="empty-graph">上传教材并构建知识图谱后，将在此显示概念、定义与跨章节关系。</div>
        ) : (
          <ReactECharts option={option} style={{ width: "100%", height: "100%" }} notMerge lazyUpdate onEvents={{ click: handleChartClick }} />
        )}
      </section>

      <div className="graph-footer">
        <div className="legend-strip">
          {textbooks.map((book) => (
            <span key={book.id}>
              <i style={{ background: colors[book.id] }} />
              {book.title || book.filename}
            </span>
          ))}
        </div>
        <div className="node-detail">
          {selectedNode ? (
            <>
              <strong>{selectedNode.name}</strong>
              <span>{selectedNode.definition || "暂无定义"}</span>
              <small>
                {textbookName(textbooks, selectedNode.textbook_id)} · {selectedNode.chapter} · 第 {selectedNode.page} 页
              </small>
            </>
          ) : (
            <span>点击节点查看定义、章节、页码与来源。</span>
          )}
        </div>
      </div>
    </main>
  );
}
