"""Decimal arithmetic; all summaries roll up the same calculation rows."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from ..models.core import price_key, seating_key
from ..models import assert_model, sellable, ModelError, occupancy

D = lambda v: Decimal(str(v))
ZERO=Decimal(0)

def money(v):
    return format(v.quantize(Decimal(".01"),rounding=ROUND_HALF_UP),"f")

def product_details(data):
    prices={price_key(p):D(p['price']) for p in data['prices']}
    seats={seating_key(s):s for s in data['seating']}
    result=[]
    for p in data['products']:
        face=sum((prices[price_key(seats[seating_key(c)])]*c['ticket_quantity'] for c in p['included_sessions']),ZERO)
        effective=face if p['price'] is None else D(p['price'])
        result.append(dict(product_id=p['product_id'],product_type=p['product_type'],
            ticket_quantity=sum(occupancy(p).values()),included_sessions=p['included_sessions'],
            ticket_face_value=money(face),price=money(effective),non_ticket_or_discount=money(effective-face)))
    return result

def rights_price(seat, face):
    policy=seat.get('paid_rights_pricing', {'strategy':'FACE_VALUE','value':1})
    strategies={'FACE_VALUE':lambda:face, 'FIXED_PRICE':lambda:D(policy['value']),
                'DISCOUNT_RATE':lambda:face*D(policy['value'])}
    if policy['value']<0 or (policy['strategy']=='DISCOUNT_RATE' and policy['value']>1):
        raise ModelError('无效付费权益定价参数')
    return strategies[policy['strategy']]()

def _calculate(data,price_factor=Decimal(1),demand_increment=ZERO):
    sessions={s['session_id']:s for s in data['sessions']}
    prices={price_key(p):D(p['price'])*price_factor for p in data['prices']}
    rows=[]
    for seat in data['seating']:
        sid,tier=seat['session_id'],seat['tier']; capacity=sellable(seat);paid=seat['paid_rights'];price=prices[price_key(seat)];effective=rights_price(seat,price)
        if capacity<0 or paid>capacity or price<0:
            raise ModelError('收入模型要求非负可售量/价格，且付费权益不超过可售量')
        row=dict(session_id=sid,stage=sessions[sid]['stage'],zone_id=seat['zone_id'],tier=tier,
                 physical_capacity=seat['physical_capacity'],sellable_capacity=capacity,paid_rights=paid,
                 public_capacity=capacity-paid,price=money(price),full_revenue=str(D(capacity-paid)*price+D(paid)*effective))
        for scenario, sc in data['scenarios'].items():
            q=min(Decimal(1),D(sc['session_rates'][sid])*D(sc['tier_rates'][tier])+demand_increment)
            public=D(capacity-paid)*q;rights=D(paid)*D(sc['paid_rights_rate'])
            row[scenario]=dict(public_rate=str(q),paid_rights_rate=str(sc['paid_rights_rate']),
                               public_tickets=str(public),paid_rights_tickets=str(rights),tickets=str(public+rights),
                               revenue=str(public*price+rights*effective))
        rows.append(row)
    def aggregate(items):
        physical=sum(r['physical_capacity'] for r in items);capacity=sum(r['sellable_capacity'] for r in items)
        full=sum((D(r['full_revenue']) for r in items),ZERO)
        a=dict(physical_seat_opportunities=physical,sellable_seat_opportunities=capacity,
               sellable_rate=str(D(capacity)/physical) if physical else None,
               full_revenue=money(full),full_revenue_exact=str(full),full_average_price=money(full/capacity) if capacity else None)
        for scenario in data['scenarios']:
            tickets=sum((D(r[scenario]['tickets']) for r in items),ZERO)
            revenue=sum((D(r[scenario]['revenue']) for r in items),ZERO)
            a[scenario]=dict(revenue=money(revenue),revenue_exact=str(revenue),expected_tickets=str(tickets),
                             average_price=money(revenue/tickets) if tickets else None)
        return a
    groups={}
    for name,key in [('by_stage','stage'),('by_tier','tier'),('by_session','session_id')]:
        pools=defaultdict(list)
        for row in rows:pools[row[key]].append(row)
        groups[name]={k:aggregate(v) for k,v in sorted(pools.items())}
    return dict(data_version=data['data_version'],price_version=data['price_version'],
                rules_version=data['rules_version'],snapshot_id=data['snapshot_id'],
                unit='DEMO_CURRENCY',totals=aggregate(rows),**groups,rows=rows)

def calculate(data):
    assert_model(data)
    result=_calculate(data)
    base=D(result['totals']['mid']['revenue'])
    p=_calculate(data,price_factor=D('1.01'))['totals']['mid']['revenue']
    q=_calculate(data,demand_increment=D('.01'))['totals']['mid']['revenue']
    result['sensitivity']=dict(
        price_plus_1_percent=dict(mid_revenue=p,delta=money(D(p)-base),assumption='需求不变；不是价格弹性预测'),
        public_sellthrough_plus_1_percentage_point=dict(mid_revenue=q,delta=money(D(q)-base),assumption='有效公开池售罄率+0.01，上限1；付费权益率不变'))
    result['products']=product_details(data)
    result['notes']=[
        '满售/情景收入是门票面值容量/需求模型，不是实际销售、结算或利润。',
        '付费权益保留在可售总池；情景中按独立履约率计收入，公开池扣除同一预留，避免双计或漏计。',
        'q=场次售罄率×票档系数；付费权益率独立设置。预期票张可为小数，不是已售门票。',
        '通票/旅行包提供占票映射和价格拆解；不把套餐营业额叠加到已含这些座席的容量收入。',
        '逐座区保留完整Decimal值；汇总后才显示到分，分组显示尾差不反向参与计算。',
        '可售率分母是跨场次座席机会，不是场馆独立座位数；零分母输出null。']
    return result
