from decimal import Decimal

MISSING='[不存在]'

def changes(old,new,path=''):
    if old==new:return []
    if isinstance(old,dict) and isinstance(new,dict):
        return [c for k in sorted(old.keys()|new.keys()) for c in changes(old.get(k,MISSING),new.get(k,MISSING),path+'/'+k)]
    numeric=all(isinstance(x,(int,float,Decimal)) and not isinstance(x,bool) for x in (old,new))
    return [dict(path=path,old=old,new=new,fact_kind='数值变化' if numeric else '文件事实',
                 reasons=[dict(kind='无直接证据',reason='原因无法由输入直接确认')])]

def compare_versions(a,b,registry):
    registry.order(a.enabled);registry.order(b.enabled)
    metadata=changes(a.manifest,b.manifest,'manifest')
    business={}
    for key in sorted(set(a.enabled)&set(b.enabled)):
        left,right=a.states[key],b.states[key];module=registry.get(key)
        for state in (left,right):
            if (state.module_version,state.schema_version)!=(module.module_version,module.schema_version):
                raise ValueError('比较版本前需要相应插件版本或显式迁移：'+key)
        # Approval lives in ModuleState (not in payloads), so it must be reported here as metadata.
        lifecycle=lambda s:dict(module_version=s.module_version,schema_version=s.schema_version,data_version=s.data_version,
                                status=s.status,approval_ref=s.approval_ref)
        metadata+=changes(lifecycle(left),lifecycle(right),'modules/'+key)
        facts=module.diff(left.payload,right.payload)
        for fact in facts:
            evidence=[e for e in b.evidence if e.get('module_id')==key and fact['path'] in e.get('changed_paths',[])]
            if evidence:
                fact['reasons']=[dict(kind='已确认原因（输入证据）' if e.get('confirmed') is True and all(isinstance(e.get(k),str) and e[k].strip() for k in ('source_ref','approved_by_role','reason')) else '推测原因（输入提供，未确认）',
                    reason=e.get('reason','未提供原因'),source_ref=e.get('source_ref')) for e in evidence]
        if facts:business[key]=facts
    return dict(added_modules=sorted(set(b.enabled)-set(a.enabled)),removed_modules=sorted(set(a.enabled)-set(b.enabled)),
                metadata=metadata,business=business,limitations=['模块提供确定性事实差异；没有证据不推测动机。'])
