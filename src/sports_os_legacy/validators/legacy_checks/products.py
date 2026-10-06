from decimal import Decimal
from ...models import sellable
from ...models.core import seating_key
from ...revenue import product_details

def check(data,g,start,end,releasing,sessions,seatmap,year):
    details={p['product_id']:p for p in product_details(data)}
    for p in data['products']:
        src=f"products/{p['product_id']}";face=Decimal(details[p['product_id']]['ticket_face_value'])
        if p['price_claim']=='SUM_FACE_PRICES' and p['price'] is not None and Decimal(str(p['price']))!=face:
            g.add('Q021','BLOCK',src+'/price',str(face),p['price'],'声称等于逐场票价总和，但数值不一致')
        if p['price'] is None and p['price_claim']!='SUM_FACE_PRICES':
            g.add('Q025','BLOCK',src+'/price','独立定价必须给数字',None)
        if p['price'] is not None and p['price']<0:
            g.add('Q025','BLOCK',src+'/price','价格非负',p['price'])
        for comp in p['included_sessions']:
            if comp['ticket_quantity']>sellable(seatmap[seating_key(comp)]):
                g.add('Q025','BLOCK',src+'/included_sessions','单份占票不超过对应池',comp['ticket_quantity'])
        if p['product_type']=='TRAVEL':
            t=p['travel']
            if p['price'] is None and any(t[k] for k in ('room_cost','service_per_guest','other_cost','quoted_non_ticket')):
                g.add('Q025','BLOCK',src+'/price','含非票部分的旅行包必须显式定价',None,'禁止用SUM_FACE_PRICES隐藏旅行成本或报价')
            if t['room_quantity']!=t['expected_rooms'] or t['guests']<=0 or t['nights']<=0 or t['expected_rooms']<=0:
                g.add('Q022','BLOCK',src+'/travel','实际计费房数=产品声明房数；人数/房数/房晚为正',t)
            if any(c['ticket_quantity']!=t['guests'] for c in p['included_sessions']):
                g.add('Q025','BLOCK',src+'/included_sessions','每场占票数=旅行人数',p['included_sessions'])
            cost=Decimal(str(t['room_cost']))*t['room_quantity']*t['nights']+Decimal(str(t['service_per_guest']))*t['guests']+Decimal(str(t['other_cost']))
            rate=Decimal(str(t['rate']))
            if any(t[k]<0 for k in ('room_cost','service_per_guest','other_cost')) or (t['pricing_method']=='margin' and rate>=1):
                g.add('Q023','BLOCK',src+'/travel','非负成本且margin率小于1',t)
            else:
                quote=cost*(1+rate) if t['pricing_method']=='markup' else cost/(1-rate)
                if t['actual_method']!=t['pricing_method'] or abs(quote-Decimal(str(t['quoted_non_ticket'])))>Decimal('.005'):
                    g.add('Q023','BLOCK',src+'/travel',str(quote),t['quoted_non_ticket'],
                          'markup=成本×(1+率)，margin=成本÷(1-率)，不能混用',action='确认计费基数和目标方法，不仅改文字标签')
                if p['price'] is not None and abs(Decimal(str(p['price']))-face-Decimal(str(t['quoted_non_ticket'])))>Decimal('.005'):
                    g.add('Q025','BLOCK',src+'/price',str(face+Decimal(str(t['quoted_non_ticket']))),p['price'],'旅行售价须与票面部分＋旅游报价闭合')
