from .common import *
from .products import Products, BASE

class Travel(Products):
    module_id='product.travel'
    display_name='旅行包 Travel'
    category='Product'
    description='含门票与住宿服务的旅行包及其成本和报价'
    allowed_types=('TRAVEL',)
    row_schema=obj(dict(BASE,travel=obj(dict(guests=I,expected_rooms=I,room_quantity=I,nights=I,
        room_cost=N,service_per_guest=N,other_cost=N,pricing_method={'enum':['markup','margin']},
        actual_method={'enum':['markup','margin']},rate=RATE,quoted_non_ticket=N))))

    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g)
        for i,p in enumerate(self.rows(c)):
            t=p['travel'];at=ck.row(i)
            ck(t['room_quantity']==t['expected_rooms'],'TRAVEL_ROOMS_MISMATCH',at('travel','room_quantity'),'房间数与预期房间数不一致（重复计房）',
               t['expected_rooms'],t['room_quantity'])
            for field in ('expected_rooms','guests','nights'):
                ck(t[field]>0,'TRAVEL_NOT_POSITIVE',at('travel',field),f'{field}必须大于0','> 0',t[field])
            for j,x in enumerate(p['included_sessions']):
                ck(x['ticket_quantity']==t['guests'],'TRAVEL_TICKETS_NOT_GUESTS',at('included_sessions',j,'ticket_quantity'),
                   '每场票张必须等于人数',t['guests'],x['ticket_quantity'])
            ck(D(t['quoted_non_ticket'])==D(money(D(t['quoted_non_ticket']))),'TRAVEL_QUOTE_PRECISION',at('travel','quoted_non_ticket'),
               '非票报价最多2位小数','最多2位小数',t['quoted_non_ticket'])
            ck(t['actual_method']==t['pricing_method'],'TRAVEL_METHOD_MISMATCH',at('travel','actual_method'),
               '实际计价方式必须与声明的pricing_method一致',t['pricing_method'],t['actual_method'])
            cost=D(t['room_cost'])*t['room_quantity']*t['nights']+D(t['service_per_guest'])*t['guests']+D(t['other_cost'])
            if ck(t['pricing_method']!='margin' or t['rate']<1,'TRAVEL_MARGIN_RATE',at('travel','rate'),'margin率必须小于1','< 1',t['rate']):
                quote=cost*(1+D(t['rate'])) if t['pricing_method']=='markup' else cost/(1-D(t['rate']))
                ck(money(quote)==money(D(t['quoted_non_ticket'])),'TRAVEL_QUOTE_FORMULA',at('travel','quoted_non_ticket'),
                   'markup=成本×(1+率)；margin=成本÷(1-率)，不是相同公式',money(quote),t['quoted_non_ticket'])
            if cost or t['quoted_non_ticket']:
                ck(p['price'] is not None and p['price_claim']=='INDEPENDENT','TRAVEL_NEEDS_INDEPENDENT_PRICE',at('price_claim'),
                   '含非票成本/报价的Travel必须有明确独立总价；不得用SUM_FACE_PRICES漏价','INDEPENDENT且price非空',p['price_claim'])

    def cross_validate(self,c,g):
        before=len(g.findings);super().cross_validate(c,g)
        if any(f.severity=='BLOCK' for f in g.findings[before:]):return
        ck=self.checks(g);details={r['product_id']:r for r in self.calculate(c)}
        for i,p in enumerate(self.rows(c)):
            result=details[p['product_id']];expected=result['ticket_amount']+D(p['travel']['quoted_non_ticket'])
            ck(result['total_price']==expected,'TRAVEL_TOTAL_MISMATCH',ck.row(i)('price'),'旅行包门票金额＋非票报价必须等于产品总价',
               str(expected),str(result['total_price']))
