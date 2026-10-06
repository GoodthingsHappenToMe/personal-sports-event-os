from zoneinfo import ZoneInfo
from decimal import localcontext, ROUND_HALF_EVEN
from .data import KernelError, _shape
from .findings import GateResult
from .contract import Context

S={'type':'string','minLength':1}
MANIFEST={'type':'object','required':['project','modules'],'additionalProperties':False,'properties':{
 'project':{'type':'object','required':['id','name','timezone','version','synthetic','status','approval_ref'],
 'additionalProperties':False,'properties':{'id':S,'name':S,'timezone':S,'version':S,'synthetic':{'const':True},
 'status':{'enum':['DRAFT','APPROVED','PUBLISHED']},'approval_ref':{'type':['string','null']}}},
 'modules':{'type':'object','additionalProperties':{'type':'boolean'}}}}

def _describe(error):
    # KernelError messages are user-facing; anything else is a defect, so keep its type for the report.
    return str(error) if isinstance(error,KernelError) else f'{type(error).__name__}: {error}'

def approved(status, ref):
    return status in ('APPROVED','PUBLISHED') and isinstance(ref,str) and bool(ref.strip())

def validate_project(project, registry, for_release=False):
    gate=GateResult()
    try:
        _shape(project.manifest,MANIFEST,'manifest')
        ZoneInfo(project.manifest['project']['timezone'])
        order=registry.order(project.enabled)
        for ref in project.evidence:
            if not isinstance(ref,dict) or not isinstance(ref.get('source_ref'),str) or not ref['source_ref'].strip():
                raise KernelError('Evidence必须有非空source_ref；不自动声称已经核实来源')
    except Exception as e:
        gate.add('K001','manifest/dependencies/evidence','有效内核契约',_describe(e));return gate
    meta=project.manifest['project'];releasing=for_release or meta['status']=='PUBLISHED'
    if (releasing or meta['status']=='APPROVED') and not approved(meta['status'],meta['approval_ref']):
        gate.add('K002','project/approval_ref','人工批准状态及引用',meta['status'])
    for key in order:
        try:
            m=registry.get(key);state=project.states[key]
            if (state.module_version,state.schema_version)!=(m.module_version,m.schema_version):
                raise KernelError('插件或schema版本不匹配；必须显式迁移，不能静默解释')
            if not isinstance(state.data_version,str) or not state.data_version.strip():raise KernelError('缺少data_version')
            if state.status not in ('DRAFT','APPROVED','PUBLISHED'):raise KernelError('未知模块状态')
            _shape(state.payload,m.schema(),key)
            if (releasing or state.status in ('APPROVED','PUBLISHED')) and not approved(state.status,state.approval_ref):
                gate.add('K002',key,'人工批准状态及引用',state.status)
        except Exception as e:
            gate.add('K003',key,'兼容版本及独立payload schema',_describe(e))
    if gate.status=='BLOCK':return gate
    context=Context(project,registry,releasing)
    graph=registry.dependency_graph(project.enabled);blocked=set()
    for key in order:
        # A module whose inputs come from a blocked module would only repeat its errors (or crash on them).
        upstream=sorted(graph[key]&blocked)
        if upstream:
            gate.add('DEPENDENCY_BLOCKED',key,'依赖模块全部通过验证',upstream,'依赖的模块存在阻断问题；先修正这些模块，本模块随后再验证')
            blocked.add(key);continue
        before=len(gate.findings)
        try:
            with localcontext() as decimal_context:
                decimal_context.prec=80
                decimal_context.rounding=ROUND_HALF_EVEN
                registry.get(key).validate(context,gate)
        except Exception as e:  # plugin code is trusted but fallible: report, never crash the gate
            gate.add('M_INPUT',key,'可验证的模块输入',_describe(e),'模块验证代码出现意外异常；这通常是插件缺陷，请报告')
        if any(f.severity=='BLOCK' for f in gate.findings[before:]):blocked.add(key)
    if gate.status!='BLOCK':
        for key in order:
            try:
                m=registry.get(key)
                with localcontext() as decimal_context:
                    decimal_context.prec=80
                    decimal_context.rounding=ROUND_HALF_EVEN
                    m.cross_validate(context,gate)
                    if releasing:m.release_requirements(context,gate)
            except Exception as e:  # see M_INPUT above
                gate.add('M_CROSS',key,'跨模块约束和发布条件',_describe(e),'模块跨模块检查代码出现意外异常；这通常是插件缺陷，请报告')
    return gate
