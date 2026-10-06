import { useState } from "react";
import { BackendError } from "../api";
import { Modal } from "../components";
import { ErrorNotice } from "./Errors";

/** Records a human approval that already happened outside the software. */
export function ApprovalDialog({
  target,
  version,
  busy,
  error,
  onClearError,
  onClose,
  onSubmit,
}: {
  target: string | null;
  version: string | undefined;
  busy: boolean;
  error: BackendError | null;
  onClearError: () => void;
  onClose: () => void;
  onSubmit: (approvalRef: string) => void;
}) {
  const [ref, setRef] = useState("");
  return (
    <Modal
      title={target === "PROJECT" ? "记录项目批准" : "记录模块批准"}
      open={!!target}
      onClose={onClose}
    >
      {error && <ErrorNotice error={error} onClose={onClearError} />}
      <p>此操作只记录在软件之外已发生的人工批准。软件不会替你批准业务决定。</p>
      <p>
        当前版本：
        <code>{version}</code>
      </p>
      <label className="field">
        批准引用 Approval Reference
        <input autoFocus value={ref} onChange={(e) => setRef(e.target.value)} />
      </label>
      <button
        className="primary"
        disabled={!ref.trim() || busy}
        onClick={() => onSubmit(ref)}
      >
        记录人工批准
      </button>
    </Modal>
  );
}
