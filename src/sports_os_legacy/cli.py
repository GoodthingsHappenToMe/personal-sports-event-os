"""Frozen v1.0 application adapter. Never used by the modular kernel."""
import argparse
import json
import sqlite3
from pathlib import Path
from .models import load_json,canonical,ModelError
from .models.demo import make_demo,make_version_b
from .models.schema import SCHEMA
from .database import Store
from .validators import validate
from .validators.excel import validate_xlsx
from .revenue import calculate
from .versioning import compare,render_diff
from .versioning.snapshot import create_snapshot,ReleaseBlocked
from .exporters import render_gate,render_revenue,export_release

def safe_path(workspace,path):
    root=Path(workspace).resolve()
    if root==Path('/Volumes') or Path('/Volumes') in root.parents:
        raise ValueError('本原型不在/Volumes中读取或写入；请使用独立本地目录')
    p=Path(path);p=(p if p.is_absolute() else root/p).resolve()
    if p!=root and root not in p.parents:raise ValueError('路径超出独立工作目录（包括符号链接）')
    return p

def _write(root,name,content):
    p=safe_path(root,name);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(content,encoding='utf-8');return p

def _json(root,name,data):
    return _write(root,name,json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def parser():
    p=argparse.ArgumentParser(description='Personal Sports Event OS v1.0 — synthetic/offline only')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['demo','validate','revenue','diff','snapshot','load','export-data']:
        s=sub.add_parser(name)
        s.add_argument('--workspace',default='.',help='独立本地工作目录；全部输入输出限制于此')
        if name in ['validate','revenue','snapshot']:s.add_argument('--data',help='检查/试算显式JSON，不覆盖SQLite工作库')
        if name in ['validate','snapshot']:
            s.add_argument('--xlsx',help='额外只读检查工作目录内的合成XLSX')
            s.add_argument('--excel-contract',help='XLSX合计检查契约JSON')
        if name=='validate':s.add_argument('--for-release',action='store_true')
        if name=='snapshot':s.add_argument('--ack-warnings',action='store_true')
        if name=='diff':s.add_argument('version_a');s.add_argument('version_b')
        if name=='load':s.add_argument('input')
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    try:
        root=safe_path(args.workspace,'.');store=Store(safe_path(root,'data/event.sqlite'))
        if args.command=='demo':
            a=make_demo();b=make_version_b(a)
            if store.path.exists() and canonical(store.load())!=canonical(a):
                raise ValueError('已有非初始工作数据；不覆盖。请使用新的 --workspace')
            for filename,d in [('version_a.json',a),('version_b.json',b)]:
                target=safe_path(root,'data/demo/'+filename)
                if target.exists() and canonical(load_json(target))!=canonical(d):
                    raise ValueError('已有修改过的演示文件；不覆盖：'+filename)
            store.save(a)
            _json(root,'data/demo/version_a.json',a);_json(root,'data/demo/version_b.json',b)
            _json(root,'data/schemas/event-master.schema.json',SCHEMA)
            print('PASS — 已建立完全虚构赛事：16场／4阶段／5票档／8040席；SQLite为工作事实源。')
            return 0
        if args.command=='load':
            data=load_json(safe_path(root,args.input));gate=validate(data)
            if gate.status=='BLOCK':
                print(render_gate(gate));return 2
            store.save(data);print(gate.status+' — 原子导入SQLite；未调整真实库存或批准状态。');return 0
        if args.command=='export-data':
            path=_json(root,'outputs/working-data.json',store.load());print(str(path));return 0
        if args.command=='diff':
            def version(name):
                path=safe_path(root,'data/demo/'+name+'.json' if name in ['version_a','version_b'] else name)
                return load_json(path) if path.suffix.lower()=='.json' else path.read_text(encoding='utf-8')
            a,b=version(args.version_a),version(args.version_b)
            r=compare(a,b,Path(args.version_a).stem,Path(args.version_b).stem)
            _json(root,'outputs/VERSION_DIFF.json',r);_write(root,'outputs/VERSION_DIFF.md',render_diff(r))
            print(f"PASS — {len(r['changes'])}项变化；无证据原因不补造。\noutputs/VERSION_DIFF.md");return 0
        data=load_json(safe_path(root,args.data)) if args.data else store.load()
        gate=validate(data,for_release=args.command=='snapshot' or getattr(args,'for_release',False))
        if getattr(args,'excel_contract',None) and not getattr(args,'xlsx',None):
            raise ValueError('--excel-contract必须与--xlsx同时使用')
        if getattr(args,'xlsx',None):
            contract=load_json(safe_path(root,args.excel_contract)) if args.excel_contract else None
            extra=validate_xlsx(safe_path(root,args.xlsx),contract)
            gate.findings.extend(extra.findings)
        _json(root,'outputs/QUALITY_GATE.json',gate.to_dict());_write(root,'outputs/QUALITY_GATE.md',render_gate(gate))
        if args.command=='validate':
            counts={s:sum(f.severity==s for f in gate.findings) for s in ['PASS','WARNING','BLOCK']}
            print(f'{gate.status} — {counts}\noutputs/QUALITY_GATE.md');return 2 if gate.status=='BLOCK' else 0
        if gate.status=='BLOCK':
            print('BLOCK — 禁止生成收入报告或批准发布件。详见outputs/QUALITY_GATE.md');return 2
        if args.command=='revenue':
            r=calculate(data);_json(root,'outputs/REVENUE.json',r);_write(root,'outputs/REVENUE.md',render_revenue(r))
            print(render_revenue(r));return 0
        if args.command=='snapshot':
            if gate.status=='WARNING' and not args.ack_warnings:
                raise ReleaseBlocked('WARNING：读取质量报告后，显式 --ack-warnings 才能生成快照')
            record=create_snapshot(data,store,args.ack_warnings)
            dest=export_release(record,safe_path(root,'outputs/releases'))
            print(f"PASS — {record['snapshot_id']}\n{dest}\n仅生成本地合成批准快照，未对外发布。");return 0
    except (ValueError,ModelError,KeyError,OSError,json.JSONDecodeError,sqlite3.DatabaseError) as e:
        print('ERROR / BLOCK — '+str(e));return 2
    return 0
