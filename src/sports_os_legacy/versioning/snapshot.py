from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
import json
from ..models import canonical
from ..validators import validate

class ReleaseBlocked(ValueError):pass

def _hash(data):
    normalized=deepcopy(data);normalized['snapshot_id']=None
    return sha256(canonical(normalized).encode()).hexdigest()

def require_gate(data,ack_warnings=False):
    gate=validate(data,for_release=True)
    if gate.status=='BLOCK':
        rules=sorted({f.rule_id for f in gate.findings if f.severity=='BLOCK'})
        raise ReleaseBlocked('BLOCK：禁止生成批准快照或正式发布件：'+','.join(rules))
    if gate.status=='WARNING' and not ack_warnings:
        raise ReleaseBlocked('WARNING：需人工阅读并显式确认 --ack-warnings')
    return gate

def verify_snapshot(record):
    data=record['data'];digest=_hash(data)
    if digest!=record['content_hash'] or record['snapshot_id']!='SN-'+digest[:20]:
        raise ReleaseBlocked('BLOCK：快照内容哈希不匹配')
    if data['snapshot_id']!=record['snapshot_id']:
        raise ReleaseBlocked('BLOCK：快照ID不匹配')
    for key in ('data_version','price_version','rules_version','approval_ref'):
        if record[key]!=data[key]:raise ReleaseBlocked('BLOCK：快照元数据与内容不同：'+key)
    if record['status']!='APPROVED':raise ReleaseBlocked('BLOCK：快照状态不是APPROVED')
    require_gate(data,ack_warnings=record.get('warnings_acknowledged',False))
    return record

def create_snapshot(data,store,ack_warnings=False):
    # No approval is invented here. All references must already be supplied.
    require_gate(data,ack_warnings)
    digest=_hash(data);sid='SN-'+digest[:20]
    payload=deepcopy(data);payload['snapshot_id']=sid
    record=dict(snapshot_id=sid,data_version=data['data_version'],rules_version=data['rules_version'],
                price_version=data['price_version'],created_at=datetime.now(timezone.utc).isoformat(),
                status='APPROVED',approval_ref=data['approval_ref'],content_hash=digest,
                warnings_acknowledged=ack_warnings,data=payload)
    verify_snapshot(record)
    with store.connect() as con:
        con.execute('CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT PRIMARY KEY, record TEXT NOT NULL CHECK(json_valid(record)))')
        con.execute("CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END")
        con.execute("CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'immutable snapshot'); END")
        existing=con.execute('SELECT record FROM snapshots WHERE snapshot_id=?',(sid,)).fetchone()
        if existing:return verify_snapshot(json.loads(existing[0]))
        for (old_json,) in con.execute('SELECT record FROM snapshots'):
            old=verify_snapshot(json.loads(old_json))
            if old['data_version']==record['data_version']:
                raise ReleaseBlocked('BLOCK Q018：相同data_version对应不同内容；必须创建新版本并重新批准')
            for version,group,key in [('price_version','prices',lambda x:(x['session_id'],x['tier'])),
                                      ('rules_version','rules',lambda x:x['rule_id'])]:
                if old[version]==record[version] and canonical(sorted(old['data'][group],key=key))!=canonical(sorted(data[group],key=key)):
                    raise ReleaseBlocked('BLOCK Q027：已冻结的'+version+'内容变化；必须创建新版本并重新批准')
        con.execute('INSERT INTO snapshots VALUES(?,?)',(sid,canonical(record)))
    return record
