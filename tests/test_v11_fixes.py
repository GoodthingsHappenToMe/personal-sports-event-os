import unittest
from copy import deepcopy
from decimal import Decimal
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.revenue import calculate
from sports_os_legacy.validators import validate
from sports_os_legacy.versioning import compare

class BusinessFixes(unittest.TestCase):
    def test_travel_null(self):
        d=make_demo();d['products'][2].update(price=None,price_claim='SUM_FACE_PRICES')
        self.assertEqual(validate(d,True).status,'BLOCK')
    def test_expired_rules(self):
        for kind in ('identity','transfer','rights_return','launch'):
            with self.subTest(kind=kind):
                d=make_demo();next(r for r in d['rules'] if r['rule_type']==kind)['valid_to']='2027-05-02T00:00:00+00:00'
                self.assertEqual(validate(d,True).status,'BLOCK')
    def test_split_zone_invariant(self):
        d=make_demo();d['products']=[]
        for sc in d['scenarios'].values():sc['session_rates']['S01']=.1234567
        before=calculate(d)['totals'];a=d['seating'][0];b=deepcopy(a);b['zone_id']='SPLIT'
        for k in ['physical_capacity','functional_hold','broadcast_hold','free_rights','other_hold','paid_rights']:
            b[k]=a[k]//2;a[k]-=b[k]
        d['seating'].append(b)
        self.assertEqual(before,calculate(d)['totals'])
    def test_product_order(self):
        a=make_demo();b=deepcopy(a);b['products'][1]['included_sessions'].reverse()
        self.assertFalse(compare(a,b)['changes'])
    def test_price_class(self):
        d=make_demo();d['seating'][0]['price_class_id']='VIP-SIDE';p=deepcopy(d['prices'][0]);p.update(price_class_id='VIP-SIDE',price=100);d['prices'].append(p)
        self.assertEqual(calculate(d)['rows'][0]['price'],'100.00')
    def test_rights_strategies(self):
        d=make_demo();baseline=calculate(d)
        s=d['seating'][0]
        for strategy,value,price in [('FACE_VALUE',1,730),('FIXED_PRICE',123,123),('DISCOUNT_RATE',.8,584)]:
            s['paid_rights_pricing']=dict(strategy=strategy,value=value)
            r=calculate(d)
            self.assertEqual(Decimal(baseline['totals']['full_revenue'])-Decimal(r['totals']['full_revenue']),s['paid_rights']*(730-price))
