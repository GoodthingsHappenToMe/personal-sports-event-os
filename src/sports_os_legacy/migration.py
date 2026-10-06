"""Explicit v1.0 input adapter. The modular kernel never imports this module."""
from copy import deepcopy
from .models import assert_model
from sports_os.kernel import Project,ModuleState
from sports_os.kernel.data import digest,KernelError

RULE_MODULES={k:'ticketing.'+k for k in ('refund','launch','transfer','identity','rights_return')}

def migrate_v10(data,registry):
    assert_model(data)
    d=deepcopy(data)
    if d['snapshot_id'] is not None:raise KernelError('旧snapshot只保留为1.0档案；请先显式导出工作数据再迁移')
    event=d['event']
    project=Project(dict(project=dict(id=event['event_id'],name=event['event_name'],timezone=event['timezone'],
        version=d['data_version']+'-v11',synthetic=True,status=d['status'],approval_ref=d['approval_ref'] or ''),modules={}),
        evidence=[dict(source_ref='synthetic-v1.0:'+digest(d),kind='migration',confirmed=False)])
    def add(key,payload,version=None,lifecycle=None):
        m=registry.get(key);project.manifest['modules'][key]=True
        status,ref=lifecycle if lifecycle else (d['status'],d['approval_ref'])
        project.states[key]=ModuleState(m.module_version,m.schema_version,payload,version or d['data_version'],status,ref)
    def lifting(rows,version_field,version):
        """v1.0 rows carried their own approval; lift it into ModuleState instead of dropping it.

        Consistent rows keep their claim. Disagreeing rows or a row version that differs from the
        module version cannot be represented as one approval, so the claim is kept without a
        reference and the kernel gate BLOCKs it (K002) rather than silently approving."""
        claims={(r.get('status','DRAFT'),r.get('approval_ref')) for r in rows}
        versions={r.get(version_field,version) for r in rows}
        for r in rows:
            for field in (version_field,'status','approval_ref'):r.pop(field,None)
        if len(claims)==1 and versions<={version}:return next(iter(claims))
        claimed=any(status in ('APPROVED','PUBLISHED') for status,_ in claims)
        return ('APPROVED' if claimed else 'DRAFT'),None
    add('core.schedule',dict(rows=d['sessions'],sales_start=min(p['valid_from'] for p in d['prices']),sales_end=max(s['end_time'] for s in d['sessions'])))
    add('core.venue',dict(rows=[dict(venue_id='SYNTHETIC-VENUE',name=event['venue'],timezone=event['timezone'])]))
    seats=[];rights=[]
    for old in d['seating']:
        row=dict(old);row['price_class_id']=row.get('price_class_id',row['tier'])
        paid=row.pop('paid_rights');policy=row.pop('paid_rights_pricing',dict(strategy='FACE_VALUE',value=1))
        seats.append(row)
        rights.append(dict(session_id=row['session_id'],zone_id=row['zone_id'],tier=row['tier'],quantity=paid,billing_basis='REDEEMED',**policy,
                           expected_fulfillment={k:v['paid_rights_rate'] for k,v in d['scenarios'].items()}))
    add('ticketing.seating',dict(rows=seats));add('ticketing.rights',dict(rows=rights))
    prices=[]
    for old in d['prices']:
        row=dict(old);row['price_class_id']=row.get('price_class_id',row['tier']);row.pop('tier');prices.append(row)
    add('ticketing.pricing',dict(rows=prices),d['price_version'],lifting(prices,'price_version',d['price_version']))
    add('ticketing.inventory',dict(rows=d['inventory']))
    for product_type,key in [('TRAVEL','product.travel'),('PASS','product.pass')]:
        rows=[p for p in d['products'] if (p['product_type']=='TRAVEL')==(product_type=='TRAVEL')]
        if rows:add(key,dict(rows=rows))
    for kind,key in RULE_MODULES.items():
        rows=[]
        for rule in d['rules']:
            if rule['rule_type']==kind:
                row=dict(rule);row.pop('rule_type');row['scope']={'type':'ALL'};rows.append(row)
        if rows:add(key,dict(rows=rows),d['rules_version'],lifting(rows,'version',d['rules_version']))
    for old,key in [('tasks','project.tasks'),('decisions','project.decisions')]:add(key,dict(rows=d[old]))
    add('demand.multiplicative',dict(scenarios={k:{f:v[f] for f in ('session_rates','tier_rates')} for k,v in d['scenarios'].items()}))
    add('finance.revenue',{})
    evidence=d['quality_evidence']
    for row in evidence['summaries']:
        for name in ('low','mid','high'):row['metric']=row['metric'].replace('totals.'+name+'.','totals.scenarios.'+name+'.')
    add('quality.declarations',evidence)
    # Preserve explicitly scoped evidence; field translation belongs to this adapter, not Kernel.
    roots={'prices':'ticketing.pricing','seating':'ticketing.seating','inventory':'ticketing.inventory','tasks':'project.tasks'}
    for decision in d['decisions']:
        for path in decision['changed_paths']:
            parts=path.split('/')
            if parts[0] not in roots:continue
            project.evidence.append(dict(module_id=roots[parts[0]],changed_paths=['/'+'/'.join(parts[1:])],
                reason=decision['reason'],source_ref=decision['source_ref'],confirmed=decision['confirmed'],approved_by_role=decision['approved_by_role']))
    return project
