from dataclasses import dataclass, asdict
from zoneinfo import ZoneInfo
from ..models import assert_model, ModelError
from ..models.core import moment, seating_key
from ..models.schema import obj, arr, S, RATE, I

RULES={
 'Q001':'结构、类型、唯一键、外键及缺失值', 'Q002':'Excel错误值与计算错误',
 'Q003':'空单元格或缺失引用', 'Q004':'硬编码摘要与派生值', 'Q005':'分项与总计',
 'Q006':'百分比闭合', 'Q007':'同一指标单位一致', 'Q008':'负可售库存',
 'Q009':'容量与付费权益边界', 'Q010':'扣减标识重复', 'Q011':'年度残留',
 'Q012':'开始结束时间与有效期', 'Q013':'赛前任务时序', 'Q014':'退款窗口重叠',
 'Q015':'退款窗口空档', 'Q016':'批准凭证', 'Q017':'草案禁止发布',
 'Q018':'同名内容冲突', 'Q019':'发布件引用规则状态', 'Q020':'统一快照引用',
 'Q021':'通票等于票价之和的声明', 'Q022':'旅行包房间数量', 'Q023':'markup与margin',
 'Q024':'库存守恒与时点', 'Q025':'产品价格与占票结构', 'Q026':'需求情景排序',
 'Q027':'活动版本一致', 'Q028':'任务完成凭证', 'Q029':'规则内容结构',
 'Q030':'可验证的公式范围', 'Q031':'Excel业务检查契约',
}

@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    source: str
    expected: object
    actual: object
    suggested_action: str

@dataclass
class GateResult:
    findings: list

    @property
    def status(self):
        return 'BLOCK' if any(f.severity=='BLOCK' for f in self.findings) else 'WARNING' if any(f.severity=='WARNING' for f in self.findings) else 'PASS'

    def to_dict(self):
        return dict(status=self.status,findings=[asdict(f) for f in self.findings])

    def add(self,rule,severity,source,expected,actual,message=None,action='修正输入或补充明确依据，然后重新校验；不得直接改发布件'):
        self.findings.append(Finding(rule,severity,message or RULES[rule],source,expected,actual,action))

def approved(row):
    return row['status'] in ('APPROVED','PUBLISHED') and isinstance(row.get('approval_ref'),str) and bool(row['approval_ref'].strip())

CONTENT_SCHEMAS={
 'refund':obj(dict(coverage_start=S,coverage_end=S,windows=arr(obj(dict(start=S,end=S,fee_rate=RATE))))),
 'launch':obj(dict(denominator={'const':'PUBLIC_POOL'},rounds=arr(obj(dict(at=S,fraction=RATE))))),
 'transfer':obj(dict(allowed={'type':'boolean'})), 'identity':obj(dict(mode=S)),
 'rights_return':obj(dict(hours_before=I)),
}

def _validate(data,for_release=False):
    g=GateResult([])
    try:
        assert_model(data)
    except (ModelError,TypeError,ValueError,KeyError,RecursionError) as e:
        g.add('Q001','BLOCK','$','有效的Event Master v1结构',str(e))
        return g
    zone=ZoneInfo(data['event']['timezone']);year=data['event']['year']
    sessions={s['session_id']:s for s in data['sessions']}
    end=max(moment(s['end_time']) for s in sessions.values())
    start=min(moment(s['start_time']) for s in sessions.values())
    releasing=for_release or data['status']=='PUBLISHED' or data['event']['status']=='PUBLISHED'
    types=[r['rule_type'] for r in data['rules']]
    if (releasing or data['status']=='APPROVED') and (set(types)!=set(CONTENT_SCHEMAS) or len(types)!=len(set(types))):
        g.add('Q029','BLOCK','rules','v1每类全局规则恰好一条：'+','.join(CONTENT_SCHEMAS),types,
              '批准版本不能缺少关键规则或同时引用相互竞争的全局规则')
    if releasing and (not approved(data) or data['event']['status'] not in ('APPROVED','PUBLISHED')):
        g.add('Q017','BLOCK','status/approval_ref','APPROVED/PUBLISHED且有人工批准引用',data['status'])
    if data['status'] in ('APPROVED','PUBLISHED') and not approved(data):
        g.add('Q016','BLOCK','approval_ref','非空批准引用',data['approval_ref'])
    for s in sessions.values():
        src=f"sessions/{s['session_id']}"
        if moment(s['end_time']) <= moment(s['start_time']):
            g.add('Q012','BLOCK',src,'end_time > start_time',[s['start_time'],s['end_time']])
        for field in ('start_time','end_time'):
            if moment(s[field]).astimezone(zone).year!=year:
                g.add('Q011','BLOCK',f'{src}/{field}',year,s[field])
    seatmap={seating_key(s):s for s in data['seating']}
    from .legacy_checks.seating import check as check_seating
    check_seating(data,g,start,end,releasing,sessions,seatmap,year)
    from .legacy_checks.inventory import check as check_inventory
    check_inventory(data,g,start,end,releasing,sessions,seatmap,year)
    from .legacy_checks.pricing import check as check_pricing
    check_pricing(data,g,start,end,releasing,sessions,seatmap,year)
    from .legacy_checks.rules import check as check_rules
    check_rules(data,g,start,end,releasing,sessions,seatmap,year)
    from .legacy_checks.tasks import check as check_tasks
    check_tasks(data,g,start,end,releasing,sessions,seatmap,year)
    from .legacy_checks.products import check as check_products
    check_products(data,g,start,end,releasing,sessions,seatmap,year)
    from .legacy_checks.demand import check as check_demand
    check_demand(data,g,start,end,releasing,sessions,seatmap,year)
    from .legacy_checks.evidence import check as check_evidence
    check_evidence(data,g,start,end,releasing,sessions,seatmap,year)
    checked=set(RULES)-{'Q030','Q031'}
    for rule in sorted(checked-{f.rule_id for f in g.findings}):
        g.add(rule,'PASS','$','无适用违规','未发现适用违规',action='无；PASS仅覆盖本次结构化输入与声明的检查契约')
    return g

def validate(data,for_release=False):
    try:
        return _validate(data,for_release)
    except (ArithmeticError,OverflowError) as e:
        result=GateResult([])
        result.add('Q001','BLOCK','$','可在Decimal范围内安全计算的输入',str(e),
                   '输入导致算术失败，不能生成可靠发布结果')
        return result
