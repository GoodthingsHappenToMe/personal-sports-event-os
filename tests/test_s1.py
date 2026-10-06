import unittest
from decimal import Decimal
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.models import sellable
from sports_os_legacy.revenue import calculate

class RevenueTests(unittest.TestCase):
    def test_recompute_and_rollups(self):
        d=make_demo();r=calculate(d);prices={(p['session_id'],p['tier']):p['price'] for p in d['prices']}
        expected=sum(sellable(s)*prices[s['session_id'],s['tier']] for s in d['seating'])
        self.assertEqual(Decimal(r['totals']['full_revenue']),expected)
        for group in ['by_stage','by_tier','by_session']:
            self.assertEqual(sum(Decimal(x['mid']['revenue_exact']) for x in r[group].values()),Decimal(r['totals']['mid']['revenue_exact']))
    def test_one_price_updates_all(self):
        d=make_demo();before=calculate(d);p=d['prices'][0];p['price']+=11;after=calculate(d)
        seats=sum(sellable(s) for s in d['seating'] if s['session_id']==p['session_id'] and s['tier']==p['tier'])
        delta=Decimal(after['totals']['full_revenue'])-Decimal(before['totals']['full_revenue'])
        self.assertEqual(delta,seats*11)
        for group,key in [('by_stage','QUALIFYING'),('by_tier','VIP'),('by_session','S01')]:
            self.assertEqual(Decimal(after[group][key]['full_revenue'])-Decimal(before[group][key]['full_revenue']),delta)
        self.assertNotEqual(after['totals']['mid'],before['totals']['mid'])
    def test_one_seat_updates_all(self):
        d=make_demo();before=calculate(d);d['seating'][0]['physical_capacity']+=1;after=calculate(d)
        self.assertEqual(Decimal(after['totals']['full_revenue'])-Decimal(before['totals']['full_revenue']),730)
        self.assertEqual(after['totals']['sellable_seat_opportunities']-before['totals']['sellable_seat_opportunities'],1)
    def test_paid_rights_not_lost(self):
        d=make_demo()
        for sc in d['scenarios'].values():
            sc['session_rates']={k:0 for k in sc['session_rates']}
        r=calculate(d);prices={(p['session_id'],p['tier']):p['price'] for p in d['prices']}
        expected=sum(s['paid_rights']*prices[s['session_id'],s['tier']] for s in d['seating'])
        self.assertEqual(Decimal(r['totals']['mid']['revenue']),expected)
    def test_scenario_order(self):
        r=calculate(make_demo())['totals']
        self.assertLess(Decimal(r['low']['revenue']),Decimal(r['mid']['revenue']))
        self.assertLess(Decimal(r['mid']['revenue']),Decimal(r['high']['revenue']))
        self.assertLess(Decimal(r['high']['revenue']),Decimal(r['full_revenue']))

if __name__=='__main__':unittest.main()
