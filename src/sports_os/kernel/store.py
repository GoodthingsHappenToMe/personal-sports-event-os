import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .data import canonical, digest, KernelError
from .contract import Project, ModuleState


class ConflictError(KernelError):
    """The workspace changed on disk after this project was loaded (another window, the CLI, or the desktop app)."""


SCHEMA = '''
CREATE TABLE IF NOT EXISTS projects(project_id TEXT PRIMARY KEY, manifest TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS module_state(project_id TEXT NOT NULL REFERENCES projects(project_id), module_id TEXT NOT NULL,
    module_version TEXT NOT NULL, schema_version TEXT NOT NULL, data_version TEXT NOT NULL,
    status TEXT NOT NULL, approval_ref TEXT, payload TEXT NOT NULL CHECK(json_valid(payload)), content_hash TEXT NOT NULL,
    PRIMARY KEY(project_id,module_id));
CREATE TABLE IF NOT EXISTS snapshots(snapshot_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, record TEXT NOT NULL CHECK(json_valid(record)));
CREATE TABLE IF NOT EXISTS snapshot_modules(snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),module_id TEXT NOT NULL,
    module_version TEXT NOT NULL,schema_version TEXT NOT NULL,content_hash TEXT NOT NULL,PRIMARY KEY(snapshot_id,module_id));
CREATE TABLE IF NOT EXISTS drafts(project_id TEXT PRIMARY KEY, record TEXT NOT NULL CHECK(json_valid(record)), content_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS frozen_snapshot_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END;
CREATE TRIGGER IF NOT EXISTS frozen_snapshot_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END;
CREATE TRIGGER IF NOT EXISTS frozen_module_update BEFORE UPDATE ON snapshot_modules BEGIN SELECT RAISE(ABORT,'immutable snapshot module'); END;
CREATE TRIGGER IF NOT EXISTS frozen_module_delete BEFORE DELETE ON snapshot_modules BEGIN SELECT RAISE(ABORT,'immutable snapshot module'); END;
'''


class Store:
    """The single working store of a workspace.

    Holds the validated working project, at most one incomplete DRAFT (desktop edits that do not pass the
    gate yet) and immutable snapshots. Every write bumps a workspace revision. A loaded project remembers
    the revision it was read at (``Project.base_revision``); a write from a stale copy raises ConflictError
    instead of silently overwriting another program's change. ``base_revision=None`` marks a project that
    was not loaded from this store (created, demo, imported) and is written unconditionally.
    """

    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        """Open, yield and always close a connection (sqlite3's own context manager never closes)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        try:
            con.execute('PRAGMA foreign_keys=ON')
            con.executescript(SCHEMA)
            yield con
        finally:
            con.close()

    @contextmanager
    def transaction(self):
        """BEGIN IMMEDIATE so a revision check and the write that follows happen under one write lock."""
        with self.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                yield con
            except BaseException:
                con.execute('ROLLBACK')
                raise
            con.execute('COMMIT')

    @staticmethod
    def _revision(con):
        row = con.execute("SELECT value FROM workspace_meta WHERE key='revision'").fetchone()
        return int(row[0]) if row else 0

    def revision(self):
        if not self.path.exists():
            return 0
        with self.connect() as con:
            return self._revision(con)

    def _advance(self, con, base):
        current = self._revision(con)
        if base is not None and base != current:
            raise ConflictError(f'工作区已被其他程序修改（打开时修订{base}，现在{current}）；请重新打开项目再修改，本次修改未覆盖他人的更改')
        con.execute("INSERT INTO workspace_meta VALUES('revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(current + 1),))
        return current + 1

    def save(self, project):
        """Save a validated working project; clears any incomplete draft."""
        pid = project.manifest['project']['id']
        with self.transaction() as con:
            revision = self._advance(con, project.base_revision)
            con.execute('INSERT INTO projects VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET manifest=excluded.manifest,evidence=excluded.evidence',
                        (pid, canonical(project.manifest), canonical(project.evidence)))
            con.execute('DELETE FROM module_state WHERE project_id=?', (pid,))
            for key, state in sorted(project.states.items()):
                con.execute('INSERT INTO module_state VALUES(?,?,?,?,?,?,?,?,?)',
                            (pid, key, state.module_version, state.schema_version, state.data_version, state.status, state.approval_ref,
                             canonical(state.payload), state.content_hash))
            con.execute('DELETE FROM drafts')
        project.base_revision = revision

    def save_draft(self, project):
        """Save an incomplete DRAFT in the same store; it is the working copy until it validates and is saved."""
        if project.manifest['project']['status'] != 'DRAFT':
            raise KernelError('未完成草稿必须为DRAFT')
        record = project.to_dict()
        with self.transaction() as con:
            revision = self._advance(con, project.base_revision)
            con.execute('DELETE FROM drafts')
            con.execute('INSERT INTO drafts VALUES(?,?,?)', (project.manifest['project']['id'], canonical(record), digest(record)))
        project.base_revision = revision

    def discard_draft(self, base_revision=None):
        """Drop the incomplete draft; the last saved project becomes the working copy again.

        Refuses (changing nothing) when there is no saved project to fall back to, e.g. a new project
        that has never passed validation: the draft is then the only copy. ``base_revision`` works like
        in save(): a draft that another program changed since it was loaded is not discarded.
        """
        with self.transaction() as con:
            if not con.execute('SELECT COUNT(*) FROM drafts').fetchone()[0]:
                return
            if not con.execute('SELECT COUNT(*) FROM projects').fetchone()[0]:
                raise KernelError('这是新项目的唯一版本，还没有可以回退的已保存版本；放弃会丢失整个项目，因此未做任何更改。'
                                  '请继续修正问题；如果确实要重新开始，请删除整个项目文件夹。')
            self._advance(con, base_revision)
            con.execute('DELETE FROM drafts')

    def has_saved(self):
        """Whether a validated project has ever been saved (something a draft can be discarded back to)."""
        if not self.path.exists():
            return False
        with self.connect() as con:
            return con.execute('SELECT COUNT(*) FROM projects').fetchone()[0] > 0

    def has_draft(self):
        if not self.path.exists():
            return False
        with self.connect() as con:
            return con.execute('SELECT COUNT(*) FROM drafts').fetchone()[0] > 0

    def is_empty(self):
        """No saved project and no draft (snapshots alone never exist without a project)."""
        if not self.path.exists():
            return True
        with self.connect() as con:
            return not any(con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('projects', 'drafts'))

    def load_working(self):
        """The one working copy: the incomplete draft when there is one, otherwise the saved project."""
        if self.path.exists():
            with self.connect() as con:
                revision = self._revision(con)
                draft = con.execute('SELECT record,content_hash FROM drafts').fetchall()
            if draft:
                record, hashed = draft[0]
                body = json.loads(record)
                if digest(body) != hashed:
                    raise KernelError('草稿hash不符')
                project = Project.from_dict(body)
                if project.manifest['project']['status'] != 'DRAFT':
                    raise KernelError('草稿不能声称已批准')
                project.base_revision = revision
                return project
        return self.load()

    def load(self, project_id=None):
        """The last saved (validated) project, ignoring any draft."""
        if not self.path.exists():
            raise KernelError('模块工作库不存在，请 create、demo 或 migrate-v10')
        with self.connect() as con:
            revision = self._revision(con)
            rows = con.execute('SELECT project_id,manifest,evidence FROM projects ORDER BY project_id').fetchall()
            if project_id is not None:
                rows = [r for r in rows if r[0] == project_id]
            if len(rows) != 1:
                raise KernelError('必须明确选择唯一项目')
            pid, manifest, evidence = rows[0]
            states = {}
            for row in con.execute('SELECT module_id,module_version,schema_version,data_version,status,approval_ref,payload,content_hash FROM module_state WHERE project_id=?', (pid,)):
                key, mv, sv, dv, status, ref, payload, hashed = row
                state = ModuleState(mv, sv, json.loads(payload), dv, status, ref)
                if state.content_hash != hashed:
                    raise KernelError('工作模块hash不符：' + key)
                states[key] = state
        project = Project(json.loads(manifest), states, json.loads(evidence))
        project.base_revision = revision
        return project

    def list_snapshots(self, project_id):
        if not self.path.exists():
            return []
        with self.connect() as con:
            return self.verified_snapshots(con, project_id)

    @staticmethod
    def verified_snapshots(con, project_id):
        from .snapshot import verify_snapshot
        records = [json.loads(r[0]) for r in con.execute('SELECT record FROM snapshots WHERE project_id=? ORDER BY snapshot_id', (project_id,))]
        for r in records:
            verify_snapshot(r)
            actual = con.execute('SELECT module_id,module_version,schema_version,content_hash FROM snapshot_modules WHERE snapshot_id=? ORDER BY module_id',
                                 (r['snapshot_id'],)).fetchall()
            expected = [(k, v['module_version'], v['schema_version'], v['content_hash']) for k, v in sorted(r['module_index'].items())]
            if actual != expected:
                raise KernelError('冻结模块索引不一致')
        return records
