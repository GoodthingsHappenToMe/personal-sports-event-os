from .common import *

COMPONENT=obj(dict(session_id=S,zone_id=S,tier=S,ticket_quantity=I))
BASE=dict(product_id=S,product_type={'enum':['SINGLE','PASS','TRAVEL']},included_sessions=arr(COMPONENT),
          price={'type':['number','null'],'minimum':0,'maximum':10**12},price_claim={'enum':['INDEPENDENT','SUM_FACE_PRICES']})

class Products(RowsModule):
    requires_capabilities=('capacity','prices')
    identity=('product_id',)
    row_schema=obj(BASE)
    allowed_types=()

    def canonical_row(self,row):
        return dict(row,included_sessions=sorted(row['included_sessions'],key=pool_key))

    def validate(self,c,g):
        super().validate(c,g);ck=self.checks(g)
        for i,r in enumerate(self.rows(c)):
            at=ck.row(i);parts=r['included_sessions']
            ck(r['product_type'] in self.allowed_types,'PRODUCT_WRONG_TYPE',at('product_type'),'产品类型不属于此模块',list(self.allowed_types),r['product_type'])
            if r['price'] is not None:
                ck(D(r['price'])==D(money(D(r['price']))),'PRODUCT_PRICE_PRECISION',at('price'),'产品总价最多2位小数','最多2位小数',r['price'])
            ck(bool(parts),'PRODUCT_NO_SESSIONS',at('included_sessions'),'产品占票映射为空')
            ck.unique(parts,pool_key,collection=f'rows/{i}/included_sessions',rule='PRODUCT_DUPLICATE_COMPONENT')
            for j,x in enumerate(parts):
                ck(x['ticket_quantity']>0,'PRODUCT_ZERO_QUANTITY',at('included_sessions',j,'ticket_quantity'),'每份占票数必须为正','> 0',x['ticket_quantity'])
            if r['product_type']=='SINGLE':
                total=sum(x['ticket_quantity'] for x in parts)
                ck(total==1,'PRODUCT_SINGLE_QUANTITY',at('included_sessions'),'单场票只占一张',1,total)

    def calculate(self,c):
        pools=c.provider('capacity');prices=c.provider('prices');out=[]
        for p in self.rows(c):
            face=sum((prices[price_key(pools[pool_key(x)])]*x['ticket_quantity'] for x in p['included_sessions']),ZERO)
            price=face if p['price'] is None else D(p['price'])
            out.append(dict(product_id=p['product_id'],ticket_quantity=sum(x['ticket_quantity'] for x in p['included_sessions']),
                            ticket_amount=face,non_ticket_amount=price-face,total_price=price))
        return out

    def export(self,c):
        return dict(inputs=c.payload(self.module_id),calculated=c.calculate(self.module_id))

    def cross_validate(self,c,g):
        ck=self.checks(g);pools=c.provider('capacity');resolvable=True
        for i,p in enumerate(self.rows(c)):
            for j,x in enumerate(p['included_sessions']):
                at=ck.row(i)
                if not ck(pool_key(x) in pools,'PRODUCT_UNKNOWN_POOL',at('included_sessions',j,'zone_id'),'产品占票引用不存在的座区池','已有容量池',list(pool_key(x))):
                    resolvable=False;continue
                ck(x['ticket_quantity']<=pools[pool_key(x)]['sellable_capacity'],'PRODUCT_EXCEEDS_POOL',at('included_sessions',j,'ticket_quantity'),
                   '单份占票超过可售池',f"<= {pools[pool_key(x)]['sellable_capacity']}",x['ticket_quantity'])
        if not resolvable:return
        details={x['product_id']:x for x in self.calculate(c)}
        for i,p in enumerate(self.rows(c)):
            at=ck.row(i);result=details[p['product_id']]
            ck(p['price'] is not None or p['price_claim']=='SUM_FACE_PRICES','PRODUCT_MISSING_PRICE',at('price'),
               'INDEPENDENT产品必须填写总价','非空price',None)
            ck(p['price_claim']!='SUM_FACE_PRICES' or result['total_price']==result['ticket_amount'],'PRODUCT_SUM_CLAIM_MISMATCH',at('price'),
               '声称票价之和但价格不符',str(result['ticket_amount']),str(result['total_price']))
            if result['total_price']<result['ticket_amount']:
                g.add('PRODUCT_BELOW_FACE',at('price'),'产品总价不低于所含门票面值之和（折扣请确认）',
                      str(result['total_price']),'产品总价低于面值之和 %s（差额 %s），请确认是有意折扣而非输入错误'%(result['ticket_amount'],result['ticket_amount']-result['total_price']),'WARNING')

class Pass(Products):
    module_id='product.pass'
    display_name='票务产品 Pass'
    category='Product'
    description='单场票与通票产品及其占用的场次座区'
    allowed_types=('SINGLE','PASS')
