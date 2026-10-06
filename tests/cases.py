import json
from pathlib import Path
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.validators import validate

CASES=json.loads((Path(__file__).parent/'fixtures/regressions.json').read_text())

def case_data(case_id):
    d=make_demo();e=d['quality_evidence']
    if case_id=='TEST-001':e['cells']=[dict(source='synthetic.xlsx!Model!A9',value='=A1+#REF!')]
    elif case_id=='TEST-002':e['documents']=[dict(source='document/title',text='2026年赛事正式说明',critical=True)]
    elif case_id=='TEST-003':e['totals']=[dict(source='synthetic/total',components=[100,200,300],declared=650)]
    elif case_id=='TEST-004':
        for p in d['prices']:
            if p['tier']=='VIP':p['price']=1080
        d['products']=[d['products'][1]];d['products'][0]['price']=19980
    elif case_id=='TEST-005':d['inventory'][1]['quantity']+=1
    elif case_id=='TEST-006':d['products'][2]['travel']['room_quantity']=2
    elif case_id=='TEST-007':
        t=d['products'][2]['travel'];t['actual_method']='margin';t['quoted_non_ticket']=round(780/.9,2)
    elif case_id=='TEST-008':d['rules'][0]['content']['windows'][1]['start']='2027-06-30T00:00:00+00:00'
    elif case_id=='TEST-009':e['metrics']=[dict(metric_id='refund_count',unit=u,source='synthetic/'+u) for u in ['订单','票张']]
    elif case_id=='TEST-010':d['prices'][0].update(status='PUBLISHED',approval_ref=None)
    else:raise ValueError(case_id)
    return d

def regression_results():
    results=[]
    for c in CASES:
        g=validate(case_data(c['id']));rules={f.rule_id for f in g.findings if f.severity!='PASS'}
        results.append(dict(**c,actual=g.status,actual_rules=sorted(rules),result='PASS' if g.status==c['expected'] and c['rule'] in rules else 'FAIL'))
    return results
