import unittest
import tempfile
from pathlib import Path
from sports_os_legacy.models.demo import make_demo,make_version_b
from sports_os_legacy.validators import validate
from sports_os_legacy.revenue import calculate
from sports_os_legacy.database import Store
from sports_os_legacy.versioning import compare
from sports_os_legacy.versioning.snapshot import create_snapshot,ReleaseBlocked

class FinalAcceptanceTests(unittest.TestCase):
    def test_missing_or_competing_rules_block_release(self):
        d=make_demo();d['rules'].pop(0)
        self.assertEqual(validate(d,for_release=True).status,'BLOCK')
        d=make_demo();other=dict(d['rules'][0]);other['rule_id']='SECOND-REFUND';d['rules'].append(other)
        self.assertEqual(validate(d).status,'BLOCK')
    def test_unrepresentable_money_and_boolean_const_fail_closed(self):
        d=make_demo();d['prices'][0]['price']=1e308
        self.assertEqual(validate(d).status,'BLOCK')
        d=make_demo();d['synthetic']=1
        self.assertEqual(validate(d).status,'BLOCK')
    def test_version_b_all_categories_and_passes(self):
        a=make_demo();b=make_version_b(a)
        self.assertEqual(validate(b,for_release=True).status,'PASS')
        self.assertTrue({'price','seating','inventory','time','product','rule','text'} <= {c['category'] for c in compare(a,b)['changes']})
    def test_derived_product_price_updates(self):
        d=make_demo();a=calculate(d);d['prices'][0]['price']+=13;b=calculate(d)
        self.assertEqual(float(b['products'][1]['price'])-float(a['products'][1]['price']),13)
        self.assertIsNone(d['products'][1]['price'])
    def test_zero_capacity_and_zero_demand(self):
        d=make_demo();d['products']=[]
        for s in d['seating']:
            for key in ['physical_capacity','functional_hold','broadcast_hold','free_rights','other_hold','paid_rights']:s[key]=0
        for inv in d['inventory']:inv['quantity']=0
        self.assertEqual(validate(d).status,'PASS');r=calculate(d)['totals']
        self.assertEqual(r['full_revenue'],'0.00');self.assertIsNone(r['sellable_rate']);self.assertIsNone(r['mid']['average_price'])
    def test_version_labels_cannot_be_reused_for_different_content(self):
        with tempfile.TemporaryDirectory() as t:
            st=Store(Path(t)/'state.db');a=make_demo();create_snapshot(a,st);a['prices'][0]['price']+=11
            with self.assertRaises(ReleaseBlocked):create_snapshot(a,st)
            a['data_version']='demo-c'
            with self.assertRaises(ReleaseBlocked):create_snapshot(a,st)
            a['price_version']='prices-c'
            for p in a['prices']:p['price_version']='prices-c';p['approval_ref']='SYNTHETIC-NEW-APPROVAL'
            a['approval_ref']='SYNTHETIC-NEW-APPROVAL';record=create_snapshot(a,st)
            self.assertEqual(record['data_version'],'demo-c')
    def test_nonnumeric_summary_pointer_blocks(self):
        d=make_demo();d['quality_evidence']['summaries']=[dict(source='summary',metric='totals',value=1,mode='HARDCODED')]
        self.assertEqual(validate(d).status,'BLOCK')
    def test_schema_and_demo_no_actual_data(self):
        import json
        from sports_os_legacy.models.schema import SCHEMA
        data=json.dumps(make_demo(),ensure_ascii=False)
        for prohibited in ['身份证号','手机号','银行账号','订单号']:
            self.assertNotIn(prohibited,data)
        self.assertTrue(all(x['channel'].startswith('FICTIONAL_') for x in make_demo()['inventory']))
        self.assertEqual(make_demo()['event']['venue'],'Fictional Aurora Arena')
        self.assertTrue(make_demo()['synthetic']);self.assertEqual(SCHEMA['properties']['synthetic']['const'],True)

if __name__=='__main__':unittest.main()
