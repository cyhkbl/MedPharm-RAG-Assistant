import { useRef, useState } from "react";
import type { Textbook } from "../api/client";

interface FileUploadProps {
  textbooks: Textbook[];
  busyIds: Set<string>;
  uploading: boolean;
  uploadProgress: number;
  onUpload: (files: File[]) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onBuildKG: (id: string) => Promise<void>;
}

const ACCEPTED = ".pdf,.md,.markdown,.txt,.docx";

function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = { parsing: "解析中", done: "已完成", failed: "失败" };
  return labels[status] || status || "未知";
}

function iconFor(format: string): string {
  const normalized = format.replace(".", "").toLowerCase();
  if (normalized === "pdf") return "PDF";
  if (normalized === "docx") return "DOC";
  if (normalized === "md" || normalized === "markdown") return "MD";
  return "TXT";
}

export function FileUpload({ textbooks, busyIds, uploading, uploadProgress, onUpload, onDelete, onBuildKG }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  const handleFiles = (fileList: FileList | null) => {
    const files = Array.from(fileList || []);
    if (files.length) void onUpload(files);
  };

  return (
    <aside className="left-panel panel-column">
      <div className="panel-header">
        <div>
          <p className="eyebrow">资料库</p>
          <h2>医学教材</h2>
        </div>
        <span className="count-pill">{textbooks.length}</span>
      </div>

      <button
        className={`upload-zone ${dragging ? "dragging" : ""}`}
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          handleFiles(event.dataTransfer.files);
        }}
      >
        <span className="upload-icon">+</span>
        <strong>拖拽或点击上传</strong>
        <small>支持 PDF / MD / TXT / DOCX</small>
        {uploading && (
          <span className="progress-shell" aria-label="上传进度">
            <span style={{ width: `${uploadProgress}%` }} />
          </span>
        )}
      </button>
      <input ref={inputRef} type="file" accept={ACCEPTED} multiple hidden onChange={(event) => handleFiles(event.target.files)} />

      <div className="textbook-list">
        {textbooks.length === 0 ? (
          <div className="empty-state">
            <span>等待教材上传</span>
            <small>上传后可解析章节、构建知识图谱并建立 RAG 索引。</small>
          </div>
        ) : (
          textbooks.map((book) => (
            <article className="textbook-card" key={book.id}>
              <div className="file-row">
                <span className={`format-badge format-${book.format.replace(".", "").toLowerCase()}`}>{iconFor(book.format)}</span>
                <div className="file-main">
                  <strong title={book.title || book.filename}>{book.title || book.filename}</strong>
                  <small>
                    {book.format.toUpperCase()} · {formatBytes(book.total_chars)} 字符 · {book.total_pages || 0} 页
                  </small>
                </div>
              </div>
              <div className="file-meta">
                <span className={`status-dot status-${book.parse_status}`}>{statusLabel(book.parse_status)}</span>
                <span>{new Date(book.upload_time).toLocaleDateString("zh-CN")}</span>
              </div>
              <div className="card-actions">
                <button className="secondary-button" type="button" disabled={busyIds.has(book.id)} onClick={() => void onBuildKG(book.id)}>
                  {busyIds.has(book.id) ? "构建中" : "构建图谱"}
                </button>
                <button className="icon-button danger" type="button" title="删除教材" onClick={() => void onDelete(book.id)}>
                  ×
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </aside>
  );
}
