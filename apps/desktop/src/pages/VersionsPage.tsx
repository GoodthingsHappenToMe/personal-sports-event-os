import { useState } from "react";
import { Dict, display, moduleName } from "../api";
import { Empty } from "../components";

/** Compare a snapshot with the working copy or with another snapshot. */
export function VersionsPage({
  snapshots,
  busy,
  onCompare,
}: {
  snapshots: Dict[];
  busy: boolean;
  onCompare: (oldRef: string, newRef: string) => Promise<Dict | undefined>;
}) {
  const [picked, setPicked] = useState(""),
    [newVersion, setNewVersion] = useState("WORKING"),
    [diff, setDiff] = useState<Dict | null>(null);
  // Default to the first snapshot until the user picks one.
  const old = picked || snapshots[0]?.snapshot_id || "";
  return (
    <>
      <div className="compare-controls">
        <label>
          旧版本
          <select value={old} onChange={(e) => setPicked(e.target.value)}>
            <option value="">选择快照</option>
            {snapshots.map((s) => (
              <option key={s.snapshot_id}>{s.snapshot_id}</option>
            ))}
          </select>
        </label>
        <span>→</span>
        <label>
          新版本
          <select
            value={newVersion}
            onChange={(e) => setNewVersion(e.target.value)}
          >
            <option value="WORKING">当前工作副本</option>
            {snapshots.map((s) => (
              <option key={s.snapshot_id}>{s.snapshot_id}</option>
            ))}
          </select>
        </label>
        <button
          disabled={!old || busy}
          onClick={async () => setDiff((await onCompare(old, newVersion)) ?? null)}
        >
          比较版本
        </button>
      </div>
      {diff ? (
        <DiffView diff={diff} />
      ) : (
        <Empty title="选择两个版本进行比较">
          支持快照与工作副本、快照与快照；原因由后端证据提供，不做推测补全。
        </Empty>
      )}
    </>
  );
}

function DiffView({ diff }: { diff: Dict }) {
  const entries = Object.entries(diff.business || {});
  return (
    <section>
      {!entries.length && (
        <Empty title="没有业务事实变化">
          元数据或快照标识仍可能不同，详见下方后端记录。
        </Empty>
      )}
      {entries.map(([id, rows]: [string, any]) => (
        <section key={id}>
          <h2>{moduleName(id)}</h2>
          <table>
            <caption className="sr-only">{id} 版本差异</caption>
            <thead>
              <tr>
                <th>字段 / 事实类型</th>
                <th>Old → New</th>
                <th>原因证据</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any, i: number) => (
                <tr key={i}>
                  <td>
                    <code>{r.path}</code>
                    <small>{r.fact_kind}</small>
                  </td>
                  <td>
                    {display(r.old)} → {display(r.new)}
                  </td>
                  <td>
                    {r.reasons?.length
                      ? r.reasons.map((x: any, j: number) => (
                          <p key={j}>{display(x)}</p>
                        ))
                      : "No Evidence · 无直接证据"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      <details>
        <summary>完整后端差异记录（含模块启停与元数据）</summary>
        <pre>{JSON.stringify(diff, null, 2)}</pre>
      </details>
    </section>
  );
}
