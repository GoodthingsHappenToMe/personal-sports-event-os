from collections import defaultdict
from decimal import localcontext, ROUND_HALF_EVEN
from .common import *

class Revenue(Module):
    display_name='收入 Revenue'
    category='Finance'
    description='由容量、票价、需求和权益计算的收入预览（无输入数据）'
    module_id='finance.revenue'
    module_version='1.1.1'
    requires_capabilities=('capacity','demand','prices','schedule')
    optional_capabilities=('rights',)
    def schema(self):return obj({})

    def cross_validate(self,c,g):
        ck=Checks(g,self.module_id)
        pools=c.provider('capacity');prices=c.provider('prices');demand=c.provider('demand')
        rights=c.provider('rights',required=False) or {}
        if not ck(bool(demand),'REVENUE_NO_DEMAND',self.module_id,'需求结果不能为空'):return
        for key,pool in pools.items():
            label='/'.join(key)
            ck(price_key(pool) in prices,'REVENUE_MISSING_PRICE',self.module_id,f'容量池{label}没有票价','已有price_class',list(price_key(pool)))
            if key not in rights:continue
            r=rights[key]
            ck(0<=r['quantity']<=pool['sellable_capacity'] and r['effective_unit_price']>=0,'REVENUE_RIGHTS_INVALID','ticketing.rights',
               f'容量池{label}的权益标准化结果无效',f"0..{pool['sellable_capacity']}",r['quantity'])
            ck(r['billing_basis'] in ('ALLOCATED','REDEEMED'),'REVENUE_RIGHTS_BASIS','ticketing.rights',f'容量池{label}权益计费基础无效',
               ['ALLOCATED','REDEEMED'],r['billing_basis'])
            ck(set(r['expected_fulfillment'])==set(demand),'REVENUE_RIGHTS_SCENARIOS','ticketing.rights',
               f'容量池{label}的权益履约率必须覆盖当前Demand情景',sorted(demand),sorted(r['expected_fulfillment']))
            ck(all(0<=q<=1 for q in r['expected_fulfillment'].values()),'REVENUE_RIGHTS_RATE_RANGE','ticketing.rights',
               f'容量池{label}的权益履约率越界','0..1',{k:str(v) for k,v in r['expected_fulfillment'].items()})
        unknown=sorted('/'.join(k) for k in set(rights)-set(pools))
        ck(not unknown,'REVENUE_RIGHTS_UNKNOWN_POOL','ticketing.rights','权益结果引用未知容量池',[],unknown)
        for name,rates in demand.items():
            ck(set(rates)==set(pools),'REVENUE_DEMAND_INCOMPLETE',self.module_id,f'Demand情景{name}必须覆盖全部容量池',
               len(pools),len(set(rates)&set(pools)))
            out=sorted('/'.join(k) for k,q in rates.items() if not 0<=q<=1)
            ck(not out,'REVENUE_DEMAND_RANGE',self.module_id,f'Demand情景{name}的需求率必须在0到1之间',[],out)
        if {'low','mid','high'}<=set(demand):
            for key in pools:
                if not all(key in demand[n] for n in ('low','mid','high')):continue
                label='/'.join(key)
                ck(demand['low'][key]<=demand['mid'][key]<=demand['high'][key],'REVENUE_SCENARIO_ORDER',self.module_id,
                   f'容量池{label}需求率应满足low≤mid≤high','low<=mid<=high',[str(demand[n][key]) for n in ('low','mid','high')])
                if key in rights and {'low','mid','high'}<=set(rights[key]['expected_fulfillment']):
                    q=rights[key]['expected_fulfillment']
                    ck(q['low']<=q['mid']<=q['high'],'REVENUE_RIGHTS_SCENARIO_ORDER','ticketing.rights',
                       f'容量池{label}权益履约率应满足low≤mid≤high','low<=mid<=high',[str(q[n]) for n in ('low','mid','high')])

    def calculate(self,c):
        # Bounded input schemas (<=1e12); 80 digits keeps all finite input products exact.
        with localcontext() as context:
            context.prec=80
            context.rounding=ROUND_HALF_EVEN
            return self._calculate(c)

    def _calculate(self,c):
        pools=c.provider('capacity');prices=c.provider('prices');demand=c.provider('demand')
        rights=c.provider('rights',required=False) or {};schedule=c.provider('schedule')
        rows=[]
        for key,pool in sorted(pools.items()):
            public_price=prices[price_key(pool)];right=rights.get(key)
            quantity=right['quantity'] if right else 0
            effective=right['effective_unit_price'] if right else ZERO
            public=pool['sellable_capacity']-quantity
            row=dict(session_id=pool['session_id'],zone_id=pool['zone_id'],tier=pool['tier'],price_class_id=pool['price_class_id'],
                stage=schedule['sessions'][pool['session_id']]['stage'],physical_capacity=pool['physical_capacity'],
                sellable_capacity=pool['sellable_capacity'],public_capacity=public,paid_rights=quantity,
                price=public_price,full_revenue=D(public)*public_price+D(quantity)*effective,scenarios={})
            for name,rates in demand.items():
                q=rates[key];fulfillment=right['expected_fulfillment'][name] if right else ZERO
                public_tickets=D(public)*q;fulfilled=D(quantity)*fulfillment
                basis=right['billing_basis'] if right else None
                billed=D(quantity) if basis=='ALLOCATED' else fulfilled
                row['scenarios'][name]=dict(public_expected_tickets=public_tickets,rights_allocated=quantity,
                    rights_expected_fulfilled=fulfilled,rights_revenue_tickets=billed,
                    revenue_basis=basis,revenue_tickets=public_tickets+billed,
                    fulfilled_tickets=public_tickets+fulfilled,public_revenue=public_tickets*public_price,
                    rights_revenue=billed*effective,revenue=public_tickets*public_price+billed*effective)
            rows.append(row)
        def aggregate(items):
            physical=sum(r['physical_capacity'] for r in items);capacity=sum(r['sellable_capacity'] for r in items)
            full=sum((r['full_revenue'] for r in items),ZERO)
            result=dict(physical_seat_opportunities=physical,sellable_seat_opportunities=capacity,full_revenue=full,
                        sellable_rate=D(capacity)/physical if physical else None,full_average_price=full/capacity if capacity else None,scenarios={})
            for name in demand:
                fields=('public_expected_tickets','rights_allocated','rights_expected_fulfilled','rights_revenue_tickets',
                        'revenue_tickets','fulfilled_tickets','public_revenue','rights_revenue','revenue')
                totals={f:sum((r['scenarios'][name][f] for r in items),ZERO) for f in fields}
                bases=defaultdict(int)
                for r in items:
                    v=r['scenarios'][name]
                    if v['revenue_basis']:bases[v['revenue_basis']]+=v['rights_allocated']
                totals['revenue_basis']=dict(sorted(bases.items()))
                totals['average_price_per_revenue_ticket']=totals['revenue']/totals['revenue_tickets'] if totals['revenue_tickets'] else None
                totals['average_revenue_per_fulfilled_ticket']=totals['revenue']/totals['fulfilled_tickets'] if totals['fulfilled_tickets'] else None
                result['scenarios'][name]=totals
            return result
        groups={}
        for group,key in [('by_stage','stage'),('by_tier','tier'),('by_session','session_id')]:
            buckets=defaultdict(list)
            for row in rows:buckets[row[key]].append(row)
            groups[group]={k:aggregate(v) for k,v in sorted(buckets.items())}
        # Sensitivities are arithmetic on standardized results, not a second demand model.
        sensitivity={}
        for name,rates in demand.items():
            delta=sum((D(pools[k]['sellable_capacity']-rights.get(k,{}).get('quantity',0))*
                       (min(D(1),q+D('.01'))-q)*prices[price_key(pools[k])] for k,q in rates.items()),ZERO)
            sensitivity[name]=dict(public_demand_plus_1pp_delta=delta,
                public_price_plus_1percent_delta=sum((D(r['public_capacity'])*rates[(r['session_id'],r['zone_id'],r['tier'])]*r['price']*D('.01') for r in rows),ZERO))
        return dict(unit='DEMO_CURRENCY',totals=aggregate(rows),rows=rows,**groups,sensitivity=sensitivity,
                    notes=['全程Decimal；货币仅在显示层舍入。','权益收入按billing_basis确认；履约票张始终乘履约率。',
                           '容量票房不加通票或旅行包营业额；产品金额另行查看。',
                           '敏感性仅改变公开池价格/需求，权益合同输入保持不变，不是价格弹性预测。'])

    def export(self,c):
        return c.calculate(self.module_id)

    def migrate(self,old_version,old_schema,payload):
        require((old_version,old_schema)==('1.1.0','1'),'不支持的Revenue迁移')
        return payload
