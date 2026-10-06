import { BackendError, Dict, display } from "../api";

export const ERROR_LABELS: Dict = {
  VALIDATION_BLOCK: "数据检查未通过",
  DEPENDENCY: "模块依赖冲突",
  APPROVAL: "未能记录批准",
  SNAPSHOT: "快照暂不可生成",
  PROTOCOL: "通信协议错误",
  SIDECAR: "后端连接中断",
  UNEXPECTED: "出现意外错误",
  PROJECT: "请先打开项目",
  CONFLICT: "工作区已在别处修改",
};

/** Inline error inside dialogs. */
export function ErrorNotice({
  error,
  onClose,
}: {
  error: BackendError;
  onClose: () => void;
}) {
  return (
    <section role="alert">
      <strong>{ERROR_LABELS[error.code] || error.code}</strong>
      <p>{error.message}</p>
      <details>
        <summary>Technical Details</summary>
        <pre>{display(error.details)}</pre>
      </details>
      <button onClick={onClose}>关闭错误提示</button>
    </section>
  );
}

/** Floating error panel; a CONFLICT offers to reopen the project from disk. */
export function ErrorPanel({
  error,
  onClose,
  onReopen,
}: {
  error: BackendError;
  onClose: () => void;
  onReopen?: () => void;
}) {
  return (
    <div className="error-panel" role="alert">
      <strong>{ERROR_LABELS[error.code] || error.code}</strong>
      <p>{error.message}</p>
      <details>
        <summary>Technical Details</summary>
        <pre>{display(error.details)}</pre>
      </details>
      {error.code === "CONFLICT" && onReopen && (
        <button className="primary" onClick={onReopen}>
          重新打开项目（放弃本窗口未保存的修改）
        </button>
      )}
      <button onClick={onClose}>关闭错误提示</button>
    </div>
  );
}
