import unittest
from copy import deepcopy
from sports_os_legacy.models.demo import make_demo,make_version_b
from sports_os_legacy.versioning import compare,render_diff

class DiffTests(unittest.TestCase):
    def test_numeric_confirmed_and_unknown(self):
        a=make_demo();b=make_version_b(a);r=compare(a,b)
        p=next(c for c in r['changes'] if c['path']=='prices/S01/VIP/price')
        self.assertEqual((p['old'],p['new'],p['fact_kind']),(730,765,'数值变化'))
        self.assertIn('已确认',p['reasons'][0]['kind'])
        rule=next(c for c in r['changes'] if c['path'].endswith('/hours_before'))
        self.assertEqual(rule['reasons'][0]['kind'],'无直接证据')
    def test_unconfirmed_never_promoted(self):
        a=make_demo();b=make_version_b(a);b['decisions'][0]['confirmed']=False
        r=compare(a,b);p=next(c for c in r['changes'] if c['path']=='prices/S01/VIP/price')
        self.assertIn('推测原因',p['reasons'][0]['kind']);self.assertNotIn('已确认',p['reasons'][0]['kind'])
    def test_seating_derived_and_product_add_delete(self):
        a=make_demo();b=deepcopy(a);b['seating'][0]['functional_hold']+=3;b['products'].pop(0)
        r=compare(a,b)
        self.assertTrue(any(c['category']=='seating' and c['path'].endswith('/sellable_capacity') and c['new']==c['old']-3 for c in r['changes']))
        self.assertTrue(any(c['category']=='product' and c['new']=='[不存在]' for c in r['changes']))
    def test_text_replacement_no_semantic_claim(self):
        r=compare('标题\n允许转让\n保留','标题\n禁止转让\n新增\n保留')
        self.assertTrue(r['changes']);self.assertTrue(all(c['reasons'][0]['kind']=='无直接证据' for c in r['changes']))
        self.assertIn('语义',render_diff(r))
    def test_reordering_not_change(self):
        a=make_demo();b=deepcopy(a)
        for key in ['prices','seating','sessions','inventory']:b[key].reverse()
        self.assertFalse(compare(a,b)['changes'])
    def test_identical(self):self.assertEqual(compare(make_demo(),make_demo())['changes'],[])

if __name__=='__main__':unittest.main()
