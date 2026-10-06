"""Stable application boundary for CLI and a future GUI; no stdout contracts."""
from copy import deepcopy
from decimal import Decimal
from datetime import datetime
import json
import re
from ..kernel import Project,ModuleState,Context,Registry
from ..kernel.store import Store
from ..kernel.gate import validate_project
from ..kernel.diff import compare_versions
from ..kernel.snapshot import create_snapshot,verify_snapshot,ReleaseBlocked
from ..kernel.data import KernelError,canonical,digest
from .manifest import PROFILES,TEMPLATES,parse_manifest,render_manifest,safe_path


class GateBlocked(KernelError):
    """The quality gate BLOCKed an operation; ``gate`` holds the findings."""
    def __init__(self,gate):
        super().__init__('BLOCK: '+canonical(gate.to_dict()));self.gate=gate

class ApplicationService:
    def __init__(self,workspace,registry=None):
        self.root=safe_path(workspace,'.')
        self.registry=registry if registry is not None else Registry.discover()
        self.store=Store(safe_path(self.root,'data/modular.sqlite'))
        self.last_added={}  # modules added automatically by the last create/enable call -> which module needed them

    @staticmethod
    def run_legacy(argv):
        from sports_os_legacy.cli import main
        return main(argv)

    def migrate_v10(self,data):
        from sports_os_legacy.migration import migrate_v10
        return migrate_v10(data,self.registry)

    def demo(self,profile=None):
        from sports_os_legacy.models.demo import make_demo,make_version_b
        a=make_demo();b=make_version_b(a)
        projects=[self.migrate_v10(d) for d in (a,b)]
        if profile is not None:
            if profile not in PROFILES:raise KernelError('未知预设')
            for p in projects:
                selected=PROFILES[profile]
                p.manifest['modules']={k:True for k in selected}
                p.states={k:v for k,v in p.states.items() if k in selected}
                if 'ticketing.rights' not in selected and 'ticketing.inventory' in selected:
                    for r in p.states['ticketing.inventory'].payload['rows']:
                        r['allocation_type']='PUBLIC'
                        if r['status']=='PAID_RESERVED':r['status']='AVAILABLE'
        for name,p in zip(('version_a','version_b'),projects):
            target=safe_path(self.root,'data/modular_demo/'+name+'.json')
            if target.exists():
                from ..kernel.data import load_json
                if canonical(load_json(target))!=canonical(p.to_dict()):raise KernelError('拒绝覆盖已修改Demo')
        if self.store.has_draft():raise KernelError('工作区有未完成草稿，拒绝覆盖')
        if not self.store.is_empty():
            current=self.store.load()
            if current.to_dict()!=projects[0].to_dict():raise KernelError('工作数据已修改，拒绝覆盖')
            projects[0].base_revision=current.base_revision
        for name,p in zip(('version_a','version_b'),projects):
            gate=self.validate_project(p,True)
            if gate.status=='BLOCK':raise KernelError(canonical(gate.to_dict()))
            self.write_artifact('data/modular_demo/'+name+'.json',self.json_text(p.to_dict()))
        self.save_project(projects[0]);return projects[0]

    def list_modules(self):return self.registry.list()
    def plugin_problems(self):return self.registry.problems()

    def create_project(self,identity,profile=None,modules=()):
        if profile is not None and profile not in PROFILES:raise KernelError('未知预设')
        selected=tuple(PROFILES[profile]) if profile else tuple(modules)
        self.registry.order(selected)
        meta=dict(identity)
        meta.setdefault('version','1');meta.setdefault('synthetic',True);meta.setdefault('status','DRAFT');meta.setdefault('approval_ref','')
        project=Project(dict(project=meta,modules={k:True for k in selected}))
        # Only modules supply payload schemas; kernel/project creation never invents business input.
        return project

    LEGACY_DRAFT='data/desktop-draft.json'

    def _adopt_legacy_draft(self):
        """v1.1.1 desktop kept drafts in a separate JSON file; move it into the store once."""
        from ..kernel.data import load_json
        path=safe_path(self.root,self.LEGACY_DRAFT)
        if not path.exists():return
        body=load_json(path)
        if digest(body['project'])!=body['content_hash']:raise KernelError('草稿hash不符')
        project=Project.from_dict(body['project'])
        if project.manifest['project']['status']!='DRAFT':raise KernelError('草稿不能声称已批准')
        if self.store.has_draft():raise KernelError('同时存在旧草稿文件和工作库草稿；请备份后删除其中一个：'+str(path))
        self.store.save_draft(project);path.unlink()

    def open_project(self):
        """Open the single working copy: an incomplete draft if one exists, otherwise the saved project."""
        self._adopt_legacy_draft()
        project=self.store.load_working()
        if self.store.has_draft():return project
        path=safe_path(self.root,'project.toml')
        if path.exists():
            manifest=parse_manifest(path)
            if manifest['project']['id']!=project.manifest['project']['id']:
                raise KernelError('manifest项目ID与工作库不符')
            if canonical(manifest)!=canonical(project.manifest):
                # External TOML edits are working changes, not a route to record approval.
                version=project.manifest['project']['version']
                project.manifest=manifest;project.manifest['project']['version']=version
                self._configuration_changed(project)
        return project

    def save_project(self,project):
        gate=self.validate_project(project)
        if gate.status=='BLOCK':raise GateBlocked(gate)
        self.store.save(project)
        self.write_artifact('project.toml',render_manifest(project.manifest))
        return gate

    @staticmethod
    def _next_revision(version):
        match=re.fullmatch(r"(.*)-r([0-9]+)",version)
        return f"{match[1]}-r{int(match[2])+1}" if match else version+"-r1"

    @classmethod
    def _configuration_changed(cls,project):
        meta=project.manifest['project']
        meta.update(status='DRAFT',approval_ref='',version=cls._next_revision(meta['version']))
        return project

    def enable_module(self,project,module_id,payload=None):
        module=self.registry.get(module_id);out=deepcopy(project)
        was_enabled=module_id in out.enabled
        out.manifest['modules'][module_id]=True
        self.registry.order(out.enabled)
        if module_id in out.states:
            if payload is not None:out=self.update_module_data(out,module_id,payload)
        elif payload is not None:
            out.states[module_id]=ModuleState(module.module_version,module.schema_version,
                                              module.prepare_revision(deepcopy(payload),'1'))
        if module_id not in out.states:raise KernelError('启用模块必须显式提供payload')
        if was_enabled or out.manifest['project']['version']!=project.manifest['project']['version']:return out
        return self._configuration_changed(out)

    def disable_module(self,project,module_id):
        if module_id not in project.enabled:return deepcopy(project)
        out=deepcopy(project);out.manifest['modules'][module_id]=False
        self.registry.order(out.enabled)
        # Retain inactive state for deliberate re-enabling; excluded from execution and snapshots.
        return self._configuration_changed(out)

    def replace_module(self,project,old_id,new_id,payload):
        out=deepcopy(project);out.manifest['modules'][old_id]=False
        out=self.enable_module(out,new_id,payload)
        if out.manifest['modules']!=project.manifest['modules'] and out.manifest['project']['version']==project.manifest['project']['version']:
            self._configuration_changed(out)
        return out

    def import_project(self,data):
        """Import untrusted working JSON as DRAFT, never as an approval transfer."""
        out=Project.from_dict(data)
        for key,state in out.states.items():
            state.data_version=self._next_revision(state.data_version)
            state.status='DRAFT';state.approval_ref=None
            if key in out.enabled:
                module=self.registry.get(key)
                if (state.module_version,state.schema_version)!=(module.module_version,module.schema_version):
                    raise KernelError('导入前须显式迁移模块：'+key)
                state.payload=module.prepare_revision(state.payload,state.data_version)
        return self._configuration_changed(out)

    def get_module_schema(self,module_id):
        return deepcopy(self.registry.get(module_id).schema())

    @staticmethod
    def empty_payload(schema):
        """Editor scaffolding, not business defaults; incomplete facts remain BLOCK."""
        if 'const' in schema:return deepcopy(schema['const'])
        if 'enum' in schema:return deepcopy(schema['enum'][0])
        kind=schema.get('type','object')
        if isinstance(kind,list):
            if 'null' in kind:return None
            kind=kind[0]
        if kind=='object':return {k:ApplicationService.empty_payload(v) for k,v in schema.get('properties',{}).items() if k in schema.get('required',[])}
        if kind=='array':return []
        if kind=='boolean':return False
        if kind in ('number','integer'):return schema.get('minimum',0)
        return ''

    # ---- New project -------------------------------------------------------------------------------
    @staticmethod
    def suggest_project_id(name):
        """A readable project ID from the name (ASCII words, upper case); dated fallback for other scripts."""
        import unicodedata
        ascii_name=unicodedata.normalize('NFKD',name or '').encode('ascii','ignore').decode()
        slug='-'.join(re.findall(r'[A-Za-z0-9]+',ascii_name)).upper()[:40].strip('-')
        if not slug:return 'EVENT-'+datetime.now().strftime('%Y%m%d')
        return slug if re.search('[A-Z]',slug) else 'EVENT-'+slug  # "2027 夏季公开赛" -> EVENT-2027

    @staticmethod
    def local_timezone():
        """Best-effort IANA name of this computer's time zone; UTC when it cannot be determined."""
        import os
        from pathlib import Path
        from zoneinfo import ZoneInfo
        candidates=[os.environ.get('TZ','')]
        try:
            target=str(Path('/etc/localtime').resolve())
            if 'zoneinfo/' in target:candidates.append(target.split('zoneinfo/',1)[1])
        except OSError:
            pass
        for name in candidates:
            try:
                if name and '/' in name:ZoneInfo(name);return name
            except (ValueError,KeyError,OSError):
                continue
        return 'UTC'

    @staticmethod
    def project_folder(chosen,name):
        """Where a new project goes: the chosen folder if it is empty (or new), otherwise a new sub-folder
        named after the project, so picking an ordinary folder such as Documents just works."""
        from pathlib import Path
        root=Path(chosen).expanduser()
        if not root.exists() or (root.is_dir() and not any(root.iterdir())):return root
        base=ApplicationService.suggest_project_id(name).lower();candidate=root/base;n=2
        while candidate.exists() and any(candidate.iterdir()):
            candidate=root/f'{base}-{n}';n+=1
        return candidate

    @staticmethod
    def templates():
        return [dict(t,modules=list(t['modules'])) for t in TEMPLATES]

    def create_workspace(self,identity,modules=None,template=None):
        """Create a new project in this (empty) workspace.

        Only a name is required: the ID defaults to one derived from the name, the time zone to this
        computer's, and the modules to the chosen template. Modules the selection needs are added
        automatically. Returns the project; ``self.last_added`` lists what was added and why."""
        if not self.store.is_empty() or safe_path(self.root,'project.toml').exists() or safe_path(self.root,self.LEGACY_DRAFT).exists():
            raise KernelError('目录已有项目，拒绝覆盖；请选择空项目目录')
        identity=dict(identity)
        if not str(identity.get('name','')).strip():raise KernelError('请填写项目名称')
        identity['id']=str(identity.get('id') or '').strip() or self.suggest_project_id(identity['name'])
        identity['timezone']=str(identity.get('timezone') or '').strip() or self.local_timezone()
        if template is not None:
            found=[t for t in TEMPLATES if t['id']==template]
            if not found:raise KernelError('未知模板：'+template)
            modules=list(found[0]['modules'])+list(modules or ())
        selected,self.last_added=self.registry.with_dependencies(modules or ())
        project=self.create_project(identity,modules=selected)
        for key in self.registry.order(project.enabled):
            project=self.enable_module(project,key,self.empty_payload(self.get_module_schema(key)))
        # A project with nothing left to fill in is saved normally; otherwise it starts as a draft.
        self.persist_desktop_project(project)
        return project

    def enable_with_dependencies(self,project,module_id,payload=None):
        """Enable a module and, with empty starter data, anything it needs that is not enabled yet."""
        selected,added=self.registry.with_dependencies(list(project.enabled)+[module_id])
        out=project
        for key in self.registry.order(selected):
            if key in out.enabled:continue
            data=payload if key==module_id else None
            if data is None and key not in out.states:data=self.empty_payload(self.get_module_schema(key))
            out=self.enable_module(out,key,data)
        self.last_added={k:v for k,v in added.items() if k not in project.enabled}
        return out

    def setup_progress(self,project,gate=None):
        """Per enabled module, in the order to fill them in: what is left to do.

        state: DONE (filled in, no blocking problems), TODO (still empty), FIX (has blocking problems),
        WAITING (a module it depends on must be completed first), AUTO (calculated, nothing to enter).
        ``next`` is the module to work on now."""
        gate=gate or self.validate_project(project)
        try:order=self.registry.order(project.enabled)
        except KernelError:order=list(project.enabled)
        items=[]
        for key in order:
            module=self.registry.get(key);schema=module.schema()
            mine=[f for f in gate.findings if f.severity=='BLOCK' and (f.source==key or f.source.startswith(key+'/'))]
            waiting=sorted({m for f in mine if f.rule_id=='DEPENDENCY_BLOCKED' for m in (f.actual or [])})
            blocks=sum(f.rule_id!='DEPENDENCY_BLOCKED' for f in mine)
            state=project.states.get(key)
            empty=state is None or canonical(state.payload)==canonical(self.empty_payload(schema))
            if not schema.get('properties'):status='WAITING' if waiting else ('FIX' if blocks else 'AUTO')
            elif waiting:status='WAITING'
            elif empty:status='TODO'   # problems of an untouched module are just "fill this in"
            elif blocks:status='FIX'
            else:status='DONE'
            items.append(dict(module_id=key,display_name=module.display_name or key,description=module.description,
                              status=status,blocks=blocks,waiting_for=waiting))
        nxt=next((i['module_id'] for i in items if i['status'] in ('FIX','TODO')),None)
        done=sum(i['status'] in ('DONE','AUTO') for i in items)
        return dict(modules=items,next=nxt,done=done,total=len(items),complete=bool(items) and done==len(items))

    def save_desktop_draft(self,project):
        """Persist an incomplete DRAFT in the working store; never weakens save/release gates."""
        from ..kernel.data import _shape
        from ..kernel.gate import MANIFEST
        _shape(project.manifest,MANIFEST,'manifest')
        self.store.save_draft(project)

    def open_desktop_project(self):
        """Kept for protocol compatibility; the desktop and CLI open the same working copy."""
        return self.open_project()

    def has_draft(self):return self.store.has_draft()

    def can_discard_draft(self):return self.store.has_draft() and self.store.has_saved()

    def discard_draft(self,project=None):
        """Drop incomplete edits and return to the last saved project.

        Pass the project being discarded so a draft changed elsewhere since it was opened is not lost."""
        self.store.discard_draft(project.base_revision if project is not None else None)
        return self.open_project()

    def persist_desktop_project(self,project):
        gate=self.validate_project(project)
        if gate.status=='BLOCK':
            self.save_desktop_draft(project)
            return dict(storage='DRAFT',quality=gate.to_dict())
        self.save_project(project)
        return dict(storage='SAVED',quality=gate.to_dict())

    def calculate_snapshot_module(self,project,snapshot_id,module_id):
        record=self.get_snapshot(project,snapshot_id)
        verify_snapshot(record)
        return self.calculate_module(Project.from_dict(record['project']),module_id)

    def get_snapshot(self,project,snapshot_id):
        for record in self.list_snapshots(project.manifest['project']['id']):
            if record['snapshot_id']==snapshot_id:return record
        raise KernelError('快照不存在')

    def get_module_data(self,project,module_id):
        return deepcopy(project.states[module_id].payload)

    def update_module_data(self,project,module_id,payload):
        module=self.registry.get(module_id);state=project.states[module_id]
        if (state.module_version,state.schema_version)!=(module.module_version,module.schema_version):
            raise KernelError('请先显式迁移模块')
        if canonical(state.payload)==canonical(payload):return deepcopy(project)
        out=deepcopy(project);state=out.states[module_id]
        state.data_version=self._next_revision(state.data_version)
        state.payload=module.prepare_revision(deepcopy(payload),state.data_version)
        canonical(state.payload)
        state.status='DRAFT';state.approval_ref=None
        return self._configuration_changed(out)

    def apply_changeset(self,project,module_id,changes):
        """Atomic replace of existing typed paths, e.g. ['rows', 0, 'price']."""
        payload=self.get_module_data(project,module_id)
        if not isinstance(changes,list):raise KernelError('changeset必须为数组')
        for change in changes:
            if not isinstance(change,dict):raise KernelError('每个patch必须为对象')
            if set(change)!={'path','value'} or not isinstance(change['path'],list) or not change['path']:
                raise KernelError('patch需要非空结构化path和value')
            parent=payload
            for key in change['path']:
                if isinstance(parent,list):
                    if type(key) is not int or not 0<=key<len(parent):raise KernelError('数组path越界')
                elif isinstance(parent,dict):
                    if not isinstance(key,str) or key not in parent:raise KernelError('对象path不存在')
                else:raise KernelError('path穿过标量')
                value=parent[key]
                parent=value
            parent=payload
            for key in change['path'][:-1]:parent=parent[key]
            parent[change['path'][-1]]=deepcopy(change['value'])
        return self.update_module_data(project,module_id,payload)

    @staticmethod
    def _approval_ref(ref):
        if not isinstance(ref,str) or not ref.strip():raise KernelError('必须提供明确的人工批准引用')

    def approve_module(self,project,module_id,approval_ref,data_version):
        self._approval_ref(approval_ref)
        if module_id not in project.enabled:raise KernelError('只能批准启用模块')
        state=project.states[module_id]
        if state.data_version!=data_version:raise KernelError('批准版本已过期')
        if state.status in ('APPROVED','PUBLISHED'):
            if state.approval_ref==approval_ref:return deepcopy(project)
            raise KernelError('已批准版本不可改写批准引用；先修改工作数据')
        out=deepcopy(project);state=out.states[module_id]
        state.payload=self.registry.get(module_id).prepare_revision(state.payload,data_version,approval_ref)
        state.status='APPROVED';state.approval_ref=approval_ref
        gate=self.validate_project(out)
        if gate.status=='BLOCK':raise GateBlocked(gate)
        return out

    def approve_project(self,project,approval_ref,version):
        self._approval_ref(approval_ref)
        meta=project.manifest['project']
        if meta['version']!=version:raise KernelError('批准项目版本已过期')
        if meta['status'] in ('APPROVED','PUBLISHED') and meta['approval_ref']!=approval_ref:
            raise KernelError('已批准项目不可改写批准引用')
        out=deepcopy(project);out.manifest['project'].update(status='APPROVED',approval_ref=approval_ref)
        gate=self.validate_project(out,True)
        if gate.status=='BLOCK':raise GateBlocked(gate)
        return out

    def migrate_project(self,project):
        """Explicit all-installed-module migration; persist only after every migration succeeds.

        The project version advances once for the whole migration, not once per module."""
        out=deepcopy(project);changed=False
        for key in sorted(out.states):
            state=out.states[key]
            if key not in out.enabled:continue
            module=self.registry.get(key)
            if (state.module_version,state.schema_version)!=(module.module_version,module.schema_version):
                out=self._migrate_state(out,key);changed=True
        if changed:self._configuration_changed(out)
        gate=self.validate_project(out)
        if gate.status=='BLOCK':raise GateBlocked(gate)
        return out

    def migrate_module(self,project,module_id):
        return self._configuration_changed(self._migrate_state(deepcopy(project),module_id))

    def _migrate_state(self,out,module_id):
        module=self.registry.get(module_id);state=out.states[module_id]
        state.payload=module.migrate(state.module_version,state.schema_version,deepcopy(state.payload))
        state.module_version=module.module_version;state.schema_version=module.schema_version
        state.data_version=self._next_revision(state.data_version)
        state.payload=module.prepare_revision(state.payload,state.data_version)
        state.status='DRAFT';state.approval_ref=None
        return out

    def validate_project(self,project,for_release=False):return validate_project(project,self.registry,for_release)

    def status(self,project):
        """Where the working copy stands and the exact next steps to a snapshot (no approvals are invented)."""
        import shlex
        from ..kernel.gate import approved
        gate=self.validate_project(project);release=self.validate_project(project,True)
        meta=project.manifest['project'];draft=self.store.has_draft()
        modules=[]
        for key in project.enabled:
            state=project.states.get(key)
            if state is None:
                modules.append(dict(module_id=key,data_version=None,status=None,approval_ref=None,needs_approval=True));continue
            modules.append(dict(module_id=key,data_version=state.data_version,status=state.status,approval_ref=state.approval_ref,
                                needs_approval=not approved(state.status,state.approval_ref)))
        workspace=' --workspace '+shlex.quote(str(self.root))
        steps=[]
        progress=self.setup_progress(project,gate)
        if gate.status=='BLOCK':
            if progress['next']:
                item=next(i for i in progress['modules'] if i['module_id']==progress['next'])
                what='还没有填写' if item['status']=='TODO' else f"有 {item['blocks']} 个阻断问题（sports-os validate 查看）"
                key=item['module_id'];folder=shlex.quote(str(self.root))
                steps.append(f"先完成 {item['display_name']}（{key}）：{what}。"
                             f"导出：sports-os get {key}{workspace} > {folder}/{key}.json；编辑后：sports-os update {key} {key}.json{workspace}")
            else:
                steps.append('修正 sports-os validate 报告的BLOCK问题')
            if self.can_discard_draft():steps.append('或放弃这次未完成的修改：sports-os discard-draft'+workspace)
        else:
            for m in modules:
                if m['needs_approval'] and m['data_version']:
                    steps.append(f"sports-os approve-module {m['module_id']} --version {shlex.quote(m['data_version'])} --approval-ref '<人工批准引用>'"+workspace)
            if not approved(meta['status'],meta['approval_ref']):
                steps.append(f"sports-os approve-project --version {shlex.quote(meta['version'])} --approval-ref '<人工批准引用>'"+workspace)
            steps.append('sports-os snapshot'+(' --ack-warnings' if release.status=='WARNING' else '')+workspace)
        snapshots=self.list_snapshots(meta['id']) if not draft else []
        count=lambda g,level:sum(f.severity==level for f in g.findings)
        return dict(project={k:meta[k] for k in ('id','name','version','status','approval_ref')},draft=draft,revision=project.base_revision,
                    quality=dict(status=gate.status,blocks=count(gate,'BLOCK'),warnings=count(gate,'WARNING')),
                    release_quality=dict(status=release.status,blocks=count(release,'BLOCK'),warnings=count(release,'WARNING')),
                    modules=modules,setup=progress,snapshots=dict(count=len(snapshots),latest=max(snapshots,key=lambda r:r['created_at'])['snapshot_id'] if snapshots else None),
                    next_steps=steps)

    def calculate_module(self,project,module_id):
        gate=self.validate_project(project)
        if gate.status=='BLOCK':raise GateBlocked(gate)
        return Context(project,self.registry).calculate(module_id)

    def compare_versions(self,old,new):
        from ..kernel.diff import changes
        upgraded=[]
        def readable(project,label):
            """Snapshots frozen by older plugin versions are migrated in memory for comparison only;
            the stored snapshot is never changed."""
            for key in project.enabled:
                state=project.states[key];module=self.registry.get(key)
                if (state.module_version,state.schema_version)!=(module.module_version,module.schema_version):
                    state.payload=module.migrate(state.module_version,state.schema_version,deepcopy(state.payload))
                    state.module_version,state.schema_version=module.module_version,module.schema_version
                    upgraded.append(f'{label}:{key}')
            return project
        def unpack(value):
            if isinstance(value,Project):return value,None
            if 'snapshot_id' in value:
                verify_snapshot(value)
                project=readable(Project.from_dict(value['project']),value['snapshot_id'])
                return project,{k:value[k] for k in ('snapshot_id','created_at','content_hash','record_hash')}
            return Project.from_dict(value),None
        a,ma=unpack(old);b,mb=unpack(new)
        result=compare_versions(a,b,self.registry)
        result['snapshot_metadata']=changes(ma,mb,'snapshot')
        if upgraded:
            result['limitations'].append('以下快照模块由旧插件版本冻结，已在内存中按当前模块迁移后比较（快照本身未改变）：'+', '.join(upgraded))
        return result

    def create_snapshot(self,project,ack_warnings=False):return create_snapshot(project,self.registry,self.store,ack_warnings)
    def list_snapshots(self,project_id):return self.store.list_snapshots(project_id)

    def export_artifact(self,record):
        verify_snapshot(record);project=Project.from_dict(record['project'])
        gate=self.validate_project(project,True)
        if gate.status=='BLOCK' or (gate.status=='WARNING' and not record['warnings_acknowledged']):raise ReleaseBlocked('导出前门禁未通过')
        context=Context(project,self.registry,True)
        artifacts={key:self.registry.get(key).export(context) for key in project.enabled}
        document=dict(snapshot_id=record['snapshot_id'],module_index=record['module_index'],artifacts=artifacts)
        files={'snapshot.json':self.json_text(record),'artifacts.json':self.json_text(document)}
        files['manifest.json']=self.json_text(dict(snapshot_id=record['snapshot_id'],files={k:digest(v) for k,v in files.items()}))
        target=safe_path(self.root,'outputs/releases/'+record['snapshot_id'])
        if target.exists():
            if {p.name for p in target.iterdir()}!=set(files) or any(safe_path(target,k).read_text(encoding='utf-8')!=v for k,v in files.items()):
                raise ReleaseBlocked('发布目录不同，拒绝覆盖')
            return target
        import tempfile
        import os
        import shutil
        target.parent.mkdir(parents=True,exist_ok=True)
        from pathlib import Path
        temporary=Path(tempfile.mkdtemp(prefix='.staging-',dir=target.parent))
        try:
            for name,text in files.items():(temporary/name).write_text(text,encoding='utf-8')
            os.rename(temporary,target)
        finally:
            if temporary.exists():shutil.rmtree(temporary)
        return target

    @staticmethod
    def json_text(value):
        def decimal(v):
            if isinstance(v,Decimal):return format(v,'f')
            if isinstance(v,datetime):return v.isoformat()
            raise TypeError(type(v).__name__)
        def keys(v):
            if isinstance(v,dict):return {(canonical(list(k)) if isinstance(k,tuple) else k):keys(x) for k,x in v.items()}
            if isinstance(v,list):return [keys(x) for x in v]
            return v
        return json.dumps(keys(value),ensure_ascii=False,indent=2,sort_keys=True,default=decimal,allow_nan=False)+'\n'

    def write_artifact(self,name,content):
        path=safe_path(self.root,name);path.parent.mkdir(parents=True,exist_ok=True)
        # Atomic replacement of working artifacts; never used for frozen release paths.
        import tempfile
        import os
        fd,tmp=tempfile.mkstemp(prefix='.write-',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(content)
            os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return path
