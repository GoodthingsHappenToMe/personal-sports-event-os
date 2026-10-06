import { useState } from "react";
import { Dict } from "../api";
import { Empty, Status } from "../components";

/** Freeze the working copy and browse existing (immutable) snapshots. */
export function SnapshotsPage({
  snapshots,
  releaseStatus,
  readOnly,
  busy,
  dirty,
  onCreate,
  onOpen,
}: {
  snapshots: Dict[];
  releaseStatus: string;
  readOnly: boolean;
  busy: boolean;
  dirty: boolean;
  onCreate: (ackWarnings: boolean) => void;
  onOpen: (snapshotId: string) => void;
}) {
  const [ack, setAck] = useState(false);
  return (
    <>
      <div className="section-line">
        <h2>冻结当前工作版本</h2>
        {!readOnly && (
          <>
            <Status value={releaseStatus} />
            <label>
              <input
                type="checkbox"
                checked={ack}
                onChange={(e) => setAck(e.target.checked)}
              />
              已阅读并确认警告
            </label>
            <button
              className="primary"
              disabled={
                busy ||
                dirty ||
                releaseStatus === "BLOCK" ||
                (releaseStatus === "WARNING" && !ack)
              }
              onClick={() => onCreate(ack)}
            >
              冻结 Snapshot
            </button>
          </>
        )}
      </div>
      {releaseStatus === "BLOCK" && !readOnly && (
        <p className="muted">
          发布存在阻断或未批准模块。先检查、记录人工批准，再冻结。
        </p>
      )}
      {!snapshots.length ? (
        <Empty title="尚无快照">
          当前工作副本通过发布门禁并完成批准后，可生成第一个不可变版本。
        </Empty>
      ) : (
        <table>
          <caption className="sr-only">快照列表</caption>
          <thead>
            <tr>
              <th>Snapshot ID</th>
              <th>创建时间</th>
              <th>项目版本</th>
              <th>质量</th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((s) => (
              <tr key={s.snapshot_id}>
                <td>
                  <button
                    className="text-button"
                    onClick={() => onOpen(s.snapshot_id)}
                  >
                    {s.snapshot_id}
                  </button>
                </td>
                <td>{s.created_at}</td>
                <td>{s.project.manifest.project.version}</td>
                <td>
                  <Status value={s.quality_gate.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
