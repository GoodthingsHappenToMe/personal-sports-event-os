from .common import *

RATES={'type':'object','additionalProperties':RATE}

class MultiplicativeDemandModel(Module):
    module_id='demand.multiplicative'
    default_provider=True
    display_name='需求预估'
    category='Finance'
    description='按场次需求率×票档需求率得到各容量池需求率的情景'
    provides=('demand',)
    requires_capabilities=('capacity',)
    def schema(self):
        return obj(dict(scenarios={'type':'object','additionalProperties':obj(dict(session_rates=RATES,tier_rates=RATES))}))
    def validate(self,c,g):
        ck=Checks(g,self.module_id);pools=c.provider('capacity');p=c.payload(self.module_id)['scenarios']
        ck(bool(p),'DEMAND_NO_SCENARIOS',ck.where('scenarios'),'需求情景不可为空')
        sessions=sorted({r['session_id'] for r in pools.values()});tiers=sorted({r['tier'] for r in pools.values()})
        for name,rates in p.items():
            ck(sorted(rates['session_rates'])==sessions,'DEMAND_SESSION_RATES',ck.where('scenarios',name,'session_rates'),
               f'情景{name}的场次需求必须与容量池场次一致，不能猜默认值',sessions,sorted(rates['session_rates']))
            ck(sorted(rates['tier_rates'])==tiers,'DEMAND_TIER_RATES',ck.where('scenarios',name,'tier_rates'),
               f'情景{name}的票档需求必须与容量池票档一致',tiers,sorted(rates['tier_rates']))
    def calculate(self,c):
        pools=c.provider('capacity')
        return {scenario:{key:D(r['session_rates'][seat['session_id']])*D(r['tier_rates'][seat['tier']]) for key,seat in pools.items()}
                for scenario,r in c.payload(self.module_id)['scenarios'].items()}

class DirectDemandModel(Module):
    module_id='demand.direct'
    display_name='需求预估（逐池输入）'
    category='Finance'
    description='直接给出每个容量池需求率的情景'
    provides=('demand',)
    requires_capabilities=('capacity',)
    def schema(self):
        return obj(dict(scenarios={'type':'object','additionalProperties':arr(obj(dict(session_id=S,zone_id=S,tier=S,rate=RATE)))}))
    def validate(self,c,g):
        ck=Checks(g,self.module_id);pools=c.provider('capacity');scenarios=c.payload(self.module_id)['scenarios']
        ck(bool(scenarios),'DEMAND_NO_SCENARIOS',ck.where('scenarios'),'情景不可为空')
        for name,rows in scenarios.items():
            covered=ck.unique(rows,pool_key,collection='scenarios/'+name)
            missing=sorted('/'.join(k) for k in set(pools)-set(covered));extra=sorted('/'.join(k) for k in set(covered)-set(pools))
            ck(not missing,'DEMAND_MISSING_POOLS',ck.where('scenarios',name),f'情景{name}缺少容量池的需求率',[],missing)
            ck(not extra,'DEMAND_UNKNOWN_POOLS',ck.where('scenarios',name),f'情景{name}引用不存在的容量池',[],extra)
    def calculate(self,c):
        return {name:{pool_key(r):D(r['rate']) for r in rows} for name,rows in c.payload(self.module_id)['scenarios'].items()}
    def diff(self,a,b):
        def keyed(p):return {n:{'/'.join(pool_key(r)):r['rate'] for r in rows} for n,rows in p['scenarios'].items()}
        return changes(keyed(a),keyed(b))
