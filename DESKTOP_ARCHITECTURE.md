# Desktop v0.1 architecture

Baseline: `bd99376568d007b13e81e99d939afe2b72cde835` (v1.1.1). Kernel and all 19 modules unchanged.

```
React local editing draft → sportsOS.call(method, params)
  → Tauri Rust bridge (one command, serialized requests, 60s timeout)
  → persistent frozen Python JSON Lines process
  → DesktopSession → ApplicationService → existing Kernel / Registry / Modules / SQLite
```

## Ownership
- React owns selection, dialogs, unsent field values, display labels, and recent-project metadata. No SQLite/filesystem business writes, revenue arithmetic, approval decisions or Quality Gate implementation.
- Rust owns child lifetime, stdin/stdout, request IDs, ID matching, timeout and transport errors. Failed calls are never replayed automatically. Reconnect starts a fresh session; the user reopens their project.
- DesktopSession dispatches explicitly named service methods and serializes calls. Logging goes to stderr. Malformed JSON, duplicate keys/non-finite numbers, duplicate IDs and oversized frames are rejected.
- ApplicationService remains the only business write boundary. New service helpers support generic schema scaffolding, incomplete draft persistence, verified snapshot retrieval and read-only snapshot calculation. Existing save/release gates are not weakened.

## Three states, not two competing databases
1. **Unsubmitted UI draft**: browser memory only, dirty cells marked. Cancel/revert or confirm before navigating away. Submit waits for authoritative DTO.
2. **Backend working state** (v1.2): one working store, `data/modular.sqlite`. Valid projects are saved to its project tables (plus `project.toml`); an incomplete DRAFT is saved to its `drafts` table and is the working copy for both the desktop and the CLI until it validates, at which point it is saved normally and the draft row removed. Every write bumps a workspace revision; a session whose copy is older than the stored revision gets `CONFLICT` instead of overwriting. v1.1.1 `data/desktop-draft.json` files are moved into the store on first open.
3. **Snapshot**: existing immutable, hash-verified record and release export. View has no edit/approval controls. Snapshot revenue is computed by the backend using the verified frozen Project, never the current working copy.

Draft persistence solves a reproduced desktop friction: a new profile can have incomplete required rule fields and must be saveable without being publishable. `APPROVED` cannot be written as an incomplete draft. Original 180 regressions remain unchanged.

## Packaging / security scope
- PyInstaller one-file arm64 sidecar includes entry-point distribution metadata and all `sports_os` submodules. Final app needs no Python, venv or pip.
- Tauri bundles the executable; release locates it alongside its own binary. No HTTP backend, network service, AI, remote data or shell execution from project content.
- CSP restricts app content; native directory chooser only. `/Volumes` stays rejected by existing ApplicationService path discipline.
- macOS Apple Silicon build, local development/ad-hoc distribution; not notarized, not an App Store product. Intel and other OSs untested.
- One writer per project. No collaboration, encryption-at-rest, authentication, arbitrary third-party plugin installation UI or multi-process edit locking. Existing cross-file persistence limitations remain documented in v1.1.1.
- Cmd+Q / force termination can discard unsubmitted UI fields; submitted data is persisted. Normal window close and in-app navigation protect dirty edits. This is not crash-recovery software.

## Source map
- `apps/desktop/src/`: API DTO transport, App screens, generic Editor, shared accessible Dialog/Gate, tokens.
- `apps/desktop/src-tauri/`: Rust bridge, capabilities, packaging config, original table-grid icon.
- `apps/desktop/scripts/`: build and packaged-sidecar smoke scripts.
- `src/sports_os/desktop/`: protocol/session/entrypoint.
- `tests/test_desktop_protocol.py`: integration and error regressions.
- `apps/desktop/tests/`: browser E2E against the actual frozen sidecar. Only native directory chooser/IPC host are adapted for browser tests; business responses are not mocked.

Official implementation references: [Tauri sidecars](https://v2.tauri.app/develop/sidecar/), [macOS prerequisites](https://v2.tauri.app/start/prerequisites/), [native dialog plugin](https://v2.tauri.app/plugin/dialog/).
