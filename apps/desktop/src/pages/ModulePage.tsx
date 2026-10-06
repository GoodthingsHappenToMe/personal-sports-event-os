import { Dict } from "../api";
import { Status } from "../components";
import { ModuleEditor } from "../Editor";

export type ModuleView = { id: string; schema: Dict; data: Dict };

/** One module's payload editor (read-only when viewing a snapshot). */
export function ModulePage({
  view,
  state,
  snapshotId,
  busy,
  dirty,
  onApprove,
  onDirty,
  onSubmit,
}: {
  view: ModuleView;
  state: Dict | undefined;
  snapshotId: string | null;
  busy: boolean;
  dirty: boolean;
  onApprove: () => void;
  onDirty: (dirty: boolean) => void;
  onSubmit: (payload: Dict) => Promise<void>;
}) {
  return (
    <>
      <div className="section-line">
        <code>{view.id}</code>
        <Status value={state?.status || "DRAFT"} />
        <code>{state?.data_version}</code>
        {!snapshotId && (
          <button disabled={busy || dirty} onClick={onApprove}>
            记录模块批准
          </button>
        )}
      </div>
      <ModuleEditor
        key={view.id + (snapshotId || "working")}
        id={view.id}
        schema={view.schema}
        data={view.data}
        readOnly={!!snapshotId}
        onDirty={onDirty}
        onSubmit={onSubmit}
      />
    </>
  );
}
