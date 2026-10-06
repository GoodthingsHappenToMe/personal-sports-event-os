"""Persistent offline sidecar: stdout exclusively contains protocol responses."""
import contextlib
import json
import os
import sys
import traceback
import threading
from datetime import datetime,timezone
from ..application import ApplicationService
from ..application.manifest import PROFILES
from ..kernel.data import KernelError,canonical
from ..kernel.snapshot import ReleaseBlocked
from ..kernel.store import ConflictError
from .protocol import decode,ProtocolError,MAX_LINE


DESKTOP_VERSION='0.2.0'
PROTOCOL_VERSION='0.2'


class Params(dict):
    """Request params: a missing required key is the client's protocol error, not a server defect."""
    def __missing__(self,key):
        raise ProtocolError('PROTOCOL',f'缺少参数：{key}')


class DesktopSession:
    def __init__(self):
        self.app=None;self.project=None;self.seen=set();self.lock=threading.Lock()

    def require_project(self):
        if self.project is None:raise ProtocolError('PROJECT','请先创建或打开项目')

    def state(self):
        self.require_project()
        gate=self.app.validate_project(self.project)
        release=self.app.validate_project(self.project,True)
        paths=[self.app.store.path,self.app.root/'project.toml']
        modified=max((p.stat().st_mtime for p in paths if p.exists()),default=0)
        added,self.app.last_added=self.app.last_added,{}
        return dict(project=self.project.to_dict(),workspace=str(self.app.root),setup=self.app.setup_progress(self.project,gate),
                    added_modules=added,modified_at=datetime.fromtimestamp(modified,timezone.utc).isoformat(),
                    draft=self.app.has_draft(),can_discard=self.app.can_discard_draft(),revision=self.project.base_revision,quality=gate.to_dict(),
                    release_quality=release.to_dict(),modules=self.app.list_modules())

    def dispatch(self,method,p):
        if method=='health':
            from ..kernel import Registry
            registry=Registry.discover()
            return dict(protocol_version=PROTOCOL_VERSION,desktop_version=DESKTOP_VERSION,modules=registry.list(),
                        plugin_problems=registry.problems(),profiles=PROFILES,
                        templates=ApplicationService.templates(),default_timezone=ApplicationService.local_timezone())
        if method=='list_modules':
            from ..kernel import Registry
            return Registry.discover().list()
        if method in ('create_project','open_project','create_demo'):
            if method=='create_project':
                identity=p['identity']
                if set(identity)-{'id','name','timezone'}:raise ProtocolError('PROTOCOL','identity仅允许id/name/timezone')
                # A non-empty folder gets a new sub-folder named after the project instead of an error.
                app=ApplicationService(ApplicationService.project_folder(p['workspace'],identity.get('name','')))
                project=app.create_workspace(identity,p.get('modules',[]),p.get('template'))
            else:
                app=ApplicationService(p['workspace'])
                if method=='create_demo':
                    if not app.store.is_empty() or (app.root/app.LEGACY_DRAFT).exists():raise KernelError('目录已存在项目，Demo不得覆盖')
                    project=app.demo()
                else:project=app.open_desktop_project()
            self.app=app;self.project=project
            return self.state()
        self.require_project()
        if method=='get_project':return self.state()
        if method=='list_enabled_modules':return [m for m in self.app.list_modules() if m['module_id'] in self.project.enabled]
        if method=='get_module_schema':return self.app.get_module_schema(p['module_id'])
        if method=='get_module_data':return self.app.get_module_data(self.project,p['module_id'])
        if method=='validate_project':return self.app.validate_project(self.project,p.get('for_release',False)).to_dict()
        if method=='calculate_module':
            if p.get('snapshot_id'):return self.app.calculate_snapshot_module(self.project,p['snapshot_id'],p['module_id'])
            return self.app.calculate_module(self.project,p['module_id'])
        if method=='discard_draft':
            self.project=self.app.discard_draft(self.project);return self.state()
        if method=='save_project':
            self.app.persist_desktop_project(self.project);return self.state()
        if method in ('enable_module','disable_module','update_module_data','apply_changeset','approve_module','approve_project'):
            candidate=self.project
            if method=='enable_module':
                key=p['module_id'];payload=p.get('payload')
                # Anything the module needs is enabled with it (reported back as added_modules).
                candidate=self.app.enable_with_dependencies(candidate,key,payload)
            elif method=='disable_module':candidate=self.app.disable_module(candidate,p['module_id'])
            elif method=='update_module_data':candidate=self.app.update_module_data(candidate,p['module_id'],p['payload'])
            elif method=='apply_changeset':candidate=self.app.apply_changeset(candidate,p['module_id'],p['changes'])
            elif method=='approve_module':candidate=self.app.approve_module(candidate,p['module_id'],p['approval_ref'],p['data_version'])
            else:candidate=self.app.approve_project(candidate,p['approval_ref'],p['version'])
            self.app.persist_desktop_project(candidate)
            self.project=candidate
            return self.state()
        if method=='create_snapshot':
            record=self.app.create_snapshot(self.project,p.get('ack_warnings',False))
            path=self.app.export_artifact(record)
            return dict(snapshot=record,path=str(path))
        if method=='list_snapshots':return self.app.list_snapshots(self.project.manifest['project']['id'])
        if method=='get_snapshot':return self.app.get_snapshot(self.project,p['snapshot_id'])
        if method=='compare_versions':
            def get(ref):return self.project if ref=='WORKING' else self.app.get_snapshot(self.project,ref)
            return self.app.compare_versions(get(p['old']),get(p['new']))
        raise ProtocolError('UNKNOWN_METHOD','未知方法：'+method)

    def handle(self,line):
        rid=None
        with self.lock:
            try:
                req=decode(line);rid=req['id']
                if rid in self.seen:raise ProtocolError('DUPLICATE_ID','请求id已使用；禁止重复执行')
                if len(self.seen)>=100000:raise ProtocolError('PROTOCOL','会话请求上限，请重启应用')
                self.seen.add(rid)
                # Never let a plugin's accidental print contaminate JSON Lines.
                with contextlib.redirect_stdout(sys.stderr):result=self.dispatch(req['method'],Params(req['params']))
                return dict(id=rid,ok=True,result=result)
            except ProtocolError as exc:return dict(id=rid,ok=False,error=dict(code=exc.code,message=str(exc),details=exc.details))
            except Exception as exc:
                code='UNEXPECTED'
                if isinstance(exc,ConflictError):code='CONFLICT'
                elif isinstance(exc,ReleaseBlocked):code='SNAPSHOT'
                elif isinstance(exc,KernelError):
                    code='VALIDATION_BLOCK'
                    if req['method'].startswith('approve'):code='APPROVAL'
                    elif req['method'] in ('enable_module','disable_module'):code='DEPENDENCY'
                trace=traceback.format_exc();print(trace,file=sys.stderr)
                # Full tracebacks stay on stderr; set SPORTS_OS_DEBUG=1 to also return them to the client.
                details=dict(technical=trace if os.environ.get('SPORTS_OS_DEBUG')=='1' else f'{type(exc).__name__}: {exc}')
                if self.project is not None:
                    # Best effort: a failure here must not turn a structured error into a dead sidecar.
                    try:details['quality']=self.app.validate_project(self.project).to_dict()
                    except Exception as inner:details['quality_error']=f'{type(inner).__name__}: {inner}'
                return dict(id=rid,ok=False,error=dict(code=code,message=str(exc),details=details))


def main():
    session=DesktopSession()
    while True:
        line=sys.stdin.buffer.readline(MAX_LINE+1)
        if not line:break
        if len(line)>MAX_LINE:
            while line and not line.endswith(b'\n'):line=sys.stdin.buffer.readline(MAX_LINE+1)
            response=dict(id=None,ok=False,error=dict(code='PROTOCOL',message='请求超过8MiB',details={}))
        else:
            try:response=session.handle(line.decode('utf-8'))
            except UnicodeDecodeError:response=dict(id=None,ok=False,error=dict(code='PROTOCOL',message='请求不是UTF-8',details={}))
        # json_text keeps Decimal exact; compact one-line frame, never pretty JSON on stdout.
        try:normalized=json.loads(ApplicationService.json_text(response))
        except Exception as exc:  # an unserializable result must still produce exactly one reply
            normalized=dict(id=response.get('id'),ok=False,error=dict(code='UNEXPECTED',message=f'结果无法序列化：{type(exc).__name__}: {exc}',details={}))
        print(canonical(normalized),flush=True)

if __name__=='__main__':main()
