from datetime import datetime,timezone
from .data import canonical,digest,KernelError
from .contract import Project
from .gate import validate_project

class ReleaseBlocked(KernelError):pass

def verify_snapshot(record):
    body={k:v for k,v in record.items() if k!='record_hash'}
    if digest(body)!=record.get('record_hash'):raise ReleaseBlocked('快照元数据或内容被篡改')
    project=Project.from_dict(record['project'])
    if set(project.states)!=set(project.enabled):raise ReleaseBlocked('快照含未启用模块或缺模块')
    index={k:dict(module_version=s.module_version,schema_version=s.schema_version,content_hash=s.content_hash) for k,s in sorted(project.states.items())}
    if record['module_index']!=index:raise ReleaseBlocked('模块hash或版本不符')
    content=digest(record['project'])
    if record['content_hash']!=content or record['snapshot_id']!='SN11-'+content[:24]:raise ReleaseBlocked('快照ID/content hash不符')
    return record

def create_snapshot(project,registry,store,ack_warnings=False):
    gate=validate_project(project,registry,True)
    if gate.status=='BLOCK' or (gate.status=='WARNING' and not ack_warnings):
        raise ReleaseBlocked('质量门禁不允许快照：'+gate.status)
    data=project.to_dict(active_only=True);hashed=digest(data);sid='SN11-'+hashed[:24]
    index={k:dict(module_version=s.module_version,schema_version=s.schema_version,content_hash=s.content_hash) for k,s in sorted(project.states.items()) if k in project.enabled}
    record=dict(format_version='1.1',snapshot_id=sid,content_hash=hashed,project=data,module_index=index,
                created_at=datetime.now(timezone.utc).isoformat(),warnings_acknowledged=ack_warnings,quality_gate=gate.to_dict())
    record['record_hash']=digest(record)
    verify_snapshot(record);pid=project.manifest['project']['id']
    # One write transaction: the uniqueness checks below cannot race with another writer's insert.
    with store.transaction() as con:
        for old in store.verified_snapshots(con,pid):
            if old['snapshot_id']==sid:return old
            oldproject=Project.from_dict(old['project'])
            if oldproject.manifest['project']['version']==project.manifest['project']['version']:
                raise ReleaseBlocked('同一项目版本禁止对应不同快照内容；修改版本并重新批准')
            for key in set(oldproject.enabled)&set(project.enabled):
                a,b=oldproject.states[key],project.states[key]
                if a.data_version==b.data_version and a.content_hash!=b.content_hash:
                    raise ReleaseBlocked('已批准模块内容发生变化但复用data_version：'+key)
        con.execute('INSERT INTO snapshots VALUES(?,?,?)',(sid,pid,canonical(record)))
        for key,state in index.items():
            con.execute('INSERT INTO snapshot_modules VALUES(?,?,?,?,?)',(sid,key,state['module_version'],state['schema_version'],state['content_hash']))
    return record
