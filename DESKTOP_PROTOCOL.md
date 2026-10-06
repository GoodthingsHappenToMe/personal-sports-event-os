# Desktop protocol 0.1

UTF-8 JSON Lines over persistent stdin/stdout. One request/response per line. stdout exclusively protocol; stderr logs/tracebacks. No TCP port.

```json
{"id":"req-001","method":"get_module_data","params":{"module_id":"ticketing.pricing"}}
{"id":"req-001","ok":true,"result":{"rows":[]}}
{"id":"req-002","ok":false,"error":{"code":"APPROVAL","message":"...","details":{"technical":"..."}}}
```

IDs are nonempty strings ≤128 characters; process-lifetime uniqueness, max 100,000 IDs. Decode failures return null ID. Duplicate/concurrent IDs execute at most once. Frame ≤8 MiB; duplicate JSON keys, NaN/Infinity and unknown root keys rejected. Rust assigns IDs, serializes concurrent UI calls, matches response IDs, kills failed child on timeout/EOF/protocol mismatch; no automatic retry of writes.

## Methods / params
|Method|Params|
|---|---|
|health, list_modules|none; health includes profiles, protocol/desktop versions, installed Registry|
|create_project|workspace (any folder; a non-empty one gets a project sub-folder), identity:{name, id?, timezone?}, template?, modules?:[module_id] — needed modules are added automatically|
|create_demo, open_project|workspace (independent local folder)|
|get_project, save_project, list_enabled_modules, discard_draft|none|
|get_module_schema, get_module_data|module_id|
|enable_module|module_id; optional payload (otherwise generic schema scaffold)|
|disable_module|module_id|
|update_module_data|module_id, payload|
|apply_changeset|module_id, changes:[{path:[typed path components],value:...}]|
|validate_project|optional for_release:boolean|
|calculate_module|module_id; optional snapshot_id for read-only frozen calculation|
|approve_module|module_id, approval_ref, data_version (must match current)|
|approve_project|approval_ref, version (must match current)|
|create_snapshot|optional ack_warnings:boolean; returns record and release path|
|list_snapshots|none (current project)|
|get_snapshot|snapshot_id (current project only, verified)|
|compare_versions|old,new: snapshot IDs or WORKING|

State-changing project/module calls return authoritative workspace DTO: `project`, `workspace`, `modified_at`, `draft`, `revision`, `quality`, `release_quality`, `modules`. `draft=true` means the working copy is an incomplete draft stored in the workspace SQLite; `discard_draft` drops it and returns the last saved project, and is refused when `can_discard=false` (a new project that has never been saved complete). `setup` is the ordered fill-in checklist; `added_modules` lists modules the last call enabled automatically. `health` also returns `templates` and `default_timezone`. Disk failure does not replace in-memory session state. `modified_at` is persisted workspace file mtime, not time opened.

## Errors
`PROTOCOL`, `DUPLICATE_ID`, `UNKNOWN_METHOD`, `PROJECT`, `VALIDATION_BLOCK`, `DEPENDENCY`, `APPROVAL`, `SNAPSHOT`, `CONFLICT`, `UNEXPECTED`; `CONFLICT` means the workspace was saved by another program (CLI or another window) after this session opened it — nothing was written and the session must reopen; Rust/frontend add `SIDECAR` for transport failure. UI shows category/message and collapsible Technical Details. Missing dependencies and invalid approvals remain backend decisions.

Approvals require an explicit reference and current revision, and only record outside decisions. Neither protocol nor UI auto-approves prices or inventory. All demos and tests use synthetic facts.
