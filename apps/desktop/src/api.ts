import { invoke } from "@tauri-apps/api/core";
export type Dict = Record<string, any>;
export type Finding = {
  rule_id: string;
  severity: string;
  message: string;
  source: string;
  expected: unknown;
  actual: unknown;
  suggested_action: string;
};
export type Gate = { status: string; findings: Finding[] };
export type Workspace = {
  workspace: string;
  modified_at: string;
  /** True when the working copy is an incomplete draft that does not pass validation yet. */
  draft: boolean;
  /** Whether there is a saved version to fall back to (false for a brand-new unfinished project). */
  can_discard: boolean;
  /** Ordered setup checklist: what to fill in next. */
  setup: Dict;
  /** Modules enabled automatically by the last call -> the module that needed them. */
  added_modules: Record<string, string>;
  /** Workspace revision this copy was loaded at; saves from a stale revision are refused (CONFLICT). */
  revision: number | null;
  project: {
    manifest: { project: Dict; modules: Record<string, boolean> };
    modules: Record<string, Dict>;
  };
  quality: Gate;
  release_quality: Gate;
  modules: Dict[];
};
export class BackendError extends Error {
  constructor(
    public code: string,
    message: string,
    public details: Dict = {},
  ) {
    super(message);
  }
}
export const sportsOS = {
  async call<T = any>(method: string, params: Dict = {}): Promise<T> {
    let response;
    try {
      response = await invoke<Dict>("sports_call", { method, params });
    } catch (e) {
      throw new BackendError(
        "SIDECAR",
        "后端连接不可用。请重新连接后打开项目。",
        { technical: String(e) },
      );
    }
    if (!response.ok)
      throw new BackendError(
        response.error.code,
        response.error.message,
        response.error.details,
      );
    return response.result as T;
  },
};
/**
 * Module presentation metadata comes from the backend (Module.display_name / category / description),
 * so third-party modules get proper names without frontend changes. Unknown IDs fall back to the ID.
 */
let catalog: Record<string, Dict> = {};
export const setModuleCatalog = (modules: Dict[] | undefined) => {
  catalog = Object.fromEntries((modules || []).map((m) => [m.module_id, m]));
};
export const moduleName = (id: string): string =>
  catalog[id]?.display_name || id;
export const moduleCategory = (id: string): string =>
  catalog[id]?.category || "Other";
export const moduleDescription = (id: string): string =>
  catalog[id]?.description || "";
export const display = (v: unknown) =>
  v === null || v === undefined
    ? "—"
    : typeof v === "object"
      ? JSON.stringify(v)
      : String(v);
