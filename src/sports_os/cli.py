"""Thin CLI over ApplicationService. No direct business-engine imports.

Exit codes:
  0  success (validate: PASS or WARNING)
  1  blocked by the quality gate or release rules (findings are printed)
  2  usage or input error (bad arguments, unreadable/invalid files, unknown modules)
  3  workspace conflict: another program saved the workspace after it was opened
Results go to stdout; errors go to stderr.
"""
import argparse
import sqlite3
import sys
from .application import ApplicationService, GateBlocked
from .application.manifest import safe_path,PROFILES,TEMPLATES
from .kernel.data import load_json
from .kernel.snapshot import ReleaseBlocked
from .kernel.store import ConflictError

EXIT_OK, EXIT_BLOCKED, EXIT_INPUT, EXIT_CONFLICT = 0, 1, 2, 3

COMMANDS = ['demo','create','status','validate','revenue','calculate','diff','snapshot','load','export-data','modules','enable','disable','replace',
            'snapshots','migrate-v10','migrate-module','update','patch','approve-module','approve-project','migrate-project','discard-draft','schema','get']


def parser():
    p=argparse.ArgumentParser(description='Sports Event OS Modular Kernel v1.2 — synthetic/offline',
                              epilog='Exit codes: 0 ok, 1 blocked by quality gate, 2 input error, 3 workspace conflict.')
    sub=p.add_subparsers(dest='command',required=True)
    for name in COMMANDS:
        q=sub.add_parser(name);q.add_argument('--workspace',default='.')
        if name=='demo':q.add_argument('--profile',choices=sorted(PROFILES))
        if name=='create':
            q.add_argument('--name',required=True,help='项目名称（唯一必填项）')
            q.add_argument('--template',choices=[t['id'] for t in TEMPLATES],default='custom',
                           help='; '.join(f"{t['id']}={t['label']}" for t in TEMPLATES))
            q.add_argument('--profile',choices=sorted(PROFILES),help='旧名称，等同 --template')
            q.add_argument('--modules',default='',help='额外模块，逗号分隔；所需依赖会自动加上')
            q.add_argument('--id',help='默认由名称生成');q.add_argument('--timezone',help='默认使用本机时区')
        if name in ('validate','revenue','calculate','snapshot'):q.add_argument('--data')
        if name=='validate':q.add_argument('--for-release',action='store_true')
        if name=='snapshot':q.add_argument('--ack-warnings',action='store_true')
        if name=='status':q.add_argument('--json',action='store_true',help='machine-readable output')
        if name=='diff':
            help_text='WORKING (current working copy), a snapshot ID (SN11-...), version_a/version_b (demo inputs) or a JSON file'
            q.add_argument('version_a',help=help_text);q.add_argument('version_b',help=help_text)
        if name in ('load','migrate-v10'):q.add_argument('input')
        if name in ('enable','disable','calculate','migrate-module','update','patch','approve-module','schema','get'):q.add_argument('module_id')
        if name=='enable':q.add_argument('--payload')
        if name in ('update','patch'):q.add_argument('input')
        if name in ('approve-module','approve-project'):
            q.add_argument('--approval-ref',required=True);q.add_argument('--version',required=True)
        if name=='replace':
            q.add_argument('old_id');q.add_argument('new_id');q.add_argument('--payload',required=True)
    return p


def render_status(report):
    meta=report['project'];lines=[]
    lines.append(f"项目  {meta['id']} · {meta['name']}")
    lines.append(f"版本  {meta['version']} · {meta['status']}"+(f" · 批准 {meta['approval_ref']}" if meta['approval_ref'] else ''))
    if report['draft']:lines.append('工作副本  未完成草稿（尚未通过验证）')
    q,r=report['quality'],report['release_quality']
    lines.append(f"质量门禁  工作态 {q['status']}（BLOCK {q['blocks']} / WARNING {q['warnings']}）· 发布 {r['status']}（BLOCK {r['blocks']} / WARNING {r['warnings']}）")
    setup=report.get('setup')
    if setup and not setup['complete']:
        labels=dict(DONE='完成',TODO='待填写',FIX='有问题',WAITING='等待前置模块',AUTO='自动计算')
        lines.append('');lines.append(f"设置进度 {setup['done']}/{setup['total']}（按填写顺序）")
        for i in setup['modules']:
            lines.append(f"  {'→' if i['module_id']==setup['next'] else ' '} {i['display_name']:<16} {labels[i['status']]}")
    lines.append('')
    width=max((len(m['module_id']) for m in report['modules']),default=10)
    for m in report['modules']:
        mark='待批准' if m['needs_approval'] else '已批准'
        lines.append(f"  {m['module_id']:<{width}}  {m['data_version'] or '—':<24} {m['status'] or '—':<9} {mark}")
    snaps=report['snapshots']
    lines.append('');lines.append(f"快照  {snaps['count']} 个"+(f"，最近 {snaps['latest']}" if snaps['latest'] else ''))
    if report['next_steps']:
        lines.append('');lines.append('下一步（按顺序；尖括号必须替换为真实的人工批准引用）：')
        lines+=[f'  {i}. {step}' for i,step in enumerate(report['next_steps'],1)]
    return '\n'.join(lines)


def render_setup(progress,workspace):
    import shlex
    labels=dict(DONE='完成',TODO='待填写',FIX='有问题',WAITING='等待前置模块',AUTO='自动计算')
    lines=[f"\n设置进度 {progress['done']}/{progress['total']}"]
    for i in progress['modules']:
        mark='→' if i['module_id']==progress['next'] else ' '
        lines.append(f"  {mark} {i['display_name']:<16} {labels[i['status']]:<8} {i['module_id']}")
    if progress['next']:
        w=' --workspace '+shlex.quote(str(workspace))
        key=progress['next'];folder=shlex.quote(str(workspace))
        lines+=['',f'下一步：填写 {key}',
                f'  1. 导出当前数据：sports-os get {key}{w} > {folder}/{key}.json',
                f'     （字段说明：sports-os schema {key}{w}）',
                f'  2. 编辑该文件后保存：sports-os update {key} {key}.json{w}',
                f'  3. 查看进度：sports-os status{w}']
    return '\n'.join(lines)


def create(args):
    # A non-empty --workspace gets a new sub-folder named after the project.
    app=ApplicationService(ApplicationService.project_folder(args.workspace,args.name))
    modules=[m.strip() for m in args.modules.split(',') if m.strip()]
    identity=dict(name=args.name,id=args.id or '',timezone=args.timezone or '')
    project=app.create_workspace(identity,modules,args.profile or args.template)
    meta=project.manifest['project']
    print(f"已创建项目 {meta['name']}（{meta['id']}，时区 {meta['timezone']}）\n目录：{app.root}")
    for key,why in app.last_added.items():print(f'  已自动加入 {key}（{why} 需要）')
    print(render_setup(app.setup_progress(project),app.root))
    return EXIT_OK


def run(args):
    if args.command=='create':return create(args)
    app=ApplicationService(args.workspace)
    read=lambda p:load_json(safe_path(app.root,p))
    emit=lambda name,value:app.write_artifact('outputs/'+name,app.json_text(value))
    if args.command=='modules':print(app.json_text(app.list_modules()),end='');return EXIT_OK
    if args.command=='schema':print(app.json_text(app.get_module_schema(args.module_id)),end='');return EXIT_OK
    if args.command=='demo':
        project=app.demo(args.profile);print('PASS — 完全虚构模块项目：'+project.manifest['project']['name']);return EXIT_OK
    if args.command in ('load','migrate-v10'):
        raw=read(args.input);project=app.migrate_v10(raw) if args.command=='migrate-v10' else app.import_project(raw)
        gate=app.save_project(project);print(gate.status);return EXIT_OK
    if args.command=='discard-draft':
        if not app.has_draft():print('没有未完成草稿');return EXIT_OK
        app.discard_draft(app.open_project());print('已放弃草稿；工作副本回到上次保存的状态');return EXIT_OK
    if args.command=='diff':
        working=[]
        def version(name):
            if name=='WORKING':
                if not working:working.append(app.open_project())
                return working[0]
            if name.startswith('SN11-'):
                if not working:working.append(app.open_project())
                return app.get_snapshot(working[0],name)
            path=safe_path(app.root,'data/modular_demo/'+name+'.json' if name in ('version_a','version_b') else name)
            return load_json(path)
        result=app.compare_versions(version(args.version_a),version(args.version_b));emit('V1_1_DIFF.json',result)
        print(app.json_text(result),end='');return EXIT_OK
    project=app.import_project(read(args.data)) if getattr(args,'data',None) else app.open_project()
    if args.command=='status':
        report=app.status(project)
        print(app.json_text(report),end='') if args.json else print(render_status(report))
        return EXIT_OK
    if args.command=='get':print(app.json_text(app.get_module_data(project,args.module_id)),end='');return EXIT_OK
    if args.command=='export-data':print(emit('working-project.json',project.to_dict()));return EXIT_OK
    if args.command=='snapshots':print(app.json_text(app.list_snapshots(project.manifest['project']['id'])),end='');return EXIT_OK
    if args.command in ('enable','disable','replace','migrate-module'):
        if args.command=='enable':
            project=app.enable_with_dependencies(project,args.module_id,read(args.payload) if args.payload else None)
            for key,why in app.last_added.items():print(f'已自动加入 {key}（{why} 需要）',file=sys.stderr)
        elif args.command=='disable':project=app.disable_module(project,args.module_id)
        elif args.command=='replace':project=app.replace_module(project,args.old_id,args.new_id,read(args.payload))
        else:project=app.migrate_module(project,args.module_id)
        saved=app.persist_desktop_project(project)
        print('PASS — 工作态配置已更新；历史snapshot未变；需重新批准')
        if saved['storage']=='DRAFT':print(render_setup(app.setup_progress(project),app.root))
        return EXIT_OK
    if args.command=='migrate-project':
        project=app.migrate_project(project);app.save_project(project)
        print('PASS — 显式迁移完成；变化模块及项目需要人工重新批准');return EXIT_OK
    if args.command in ('update','patch','approve-module','approve-project'):
        if args.command=='update':project=app.update_module_data(project,args.module_id,read(args.input))
        elif args.command=='patch':project=app.apply_changeset(project,args.module_id,read(args.input))
        elif args.command=='approve-module':project=app.approve_module(project,args.module_id,args.approval_ref,args.version)
        else:project=app.approve_project(project,args.approval_ref,args.version)
        # Edits to an unfinished project are kept as the draft working copy, so a project can be filled
        # in one module at a time; approvals still require the whole project to pass.
        saved=app.persist_desktop_project(project) if args.command in ('update','patch') else (app.save_project(project),dict(storage='SAVED'))[1]
        print(app.json_text(dict(project=project.manifest['project'],storage=saved['storage'],
                                 modules={k:dict(data_version=s.data_version,status=s.status) for k,s in project.states.items()})),end='')
        if saved['storage']=='DRAFT':print(render_setup(app.setup_progress(project),app.root),file=sys.stderr)
        return EXIT_OK
    gate=app.validate_project(project,args.command=='snapshot' or getattr(args,'for_release',False))
    emit('V1_1_QUALITY_GATE.json',gate.to_dict())
    if args.command=='validate':print(app.json_text(gate.to_dict()),end='');return EXIT_BLOCKED if gate.status=='BLOCK' else EXIT_OK
    if gate.status=='BLOCK':print(app.json_text(gate.to_dict()),end='');return EXIT_BLOCKED
    if args.command in ('revenue','calculate'):
        key='finance.revenue' if args.command=='revenue' else args.module_id
        result=app.calculate_module(project,key);emit('V1_1_'+key+'.json',result);print(app.json_text(result),end='');return EXIT_OK
    if args.command=='snapshot':
        record=app.create_snapshot(project,args.ack_warnings);path=app.export_artifact(record)
        print('PASS — '+record['snapshot_id']+'\n'+str(path));return EXIT_OK
    return EXIT_OK


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if '--legacy' in argv:
        argv.remove('--legacy');return ApplicationService.run_legacy(argv)
    args=parser().parse_args(argv)
    try:
        return run(args)
    except ConflictError as e:
        print('CONFLICT — '+str(e),file=sys.stderr);return EXIT_CONFLICT
    except GateBlocked as e:
        print(ApplicationService.json_text(e.gate.to_dict()),end='')
        print(f'BLOCK — 质量门禁阻断（{sum(f.severity=="BLOCK" for f in e.gate.findings)} 个BLOCK）；运行 sports-os validate 查看',file=sys.stderr)
        return EXIT_BLOCKED
    except ReleaseBlocked as e:
        print('BLOCK — '+str(e),file=sys.stderr);return EXIT_BLOCKED
    except (ValueError,KeyError,TypeError,OSError,sqlite3.DatabaseError) as e:
        print('ERROR — '+str(e),file=sys.stderr);return EXIT_INPUT
