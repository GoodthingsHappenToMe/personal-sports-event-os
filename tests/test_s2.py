import unittest
import tempfile
from pathlib import Path
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.validators import validate
from sports_os_legacy.validators.excel import validate_xlsx

class GateSmokeTests(unittest.TestCase):
    def test_valid_demo_passes_release(self):
        g=validate(make_demo(),for_release=True)
        self.assertEqual(g.status,'PASS',g.to_dict())
    def test_findings_have_contract(self):
        d=make_demo();d['seating'][0]['functional_hold']=99999
        g=validate(d);self.assertEqual(g.status,'BLOCK')
        for f in g.to_dict()['findings']:
            self.assertEqual(set(f),{'rule_id','severity','message','source','expected','actual','suggested_action'})
    def test_malformed_rule_blocks_not_crashes(self):
        d=make_demo();d['rules'][0]['content']={'windows':'wrong'}
        self.assertIn('Q029',[f.rule_id for f in validate(d).findings if f.severity=='BLOCK'])
    def test_draft_can_preview_not_release(self):
        d=make_demo();d['status']='DRAFT';d['approval_ref']=None
        self.assertEqual(validate(d).status,'PASS')
        self.assertEqual(validate(d,for_release=True).status,'BLOCK')
    def test_xlsx_readonly_arithmetic_and_contract(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'synthetic.xlsx';w=openpyxl.Workbook();s=w.active;s.title='Input'
            s.append([100]);s.append([200]);s.append([300]);s['A4']='=SUM(A1:A3)';w.save(p);w.close()
            before=p.read_bytes()
            g=validate_xlsx(p,{'totals':[dict(sheet='Input',components=['A1','A2','A3'],total='A4')]})
            self.assertEqual(g.status,'PASS',g.to_dict());self.assertEqual(before,p.read_bytes())

if __name__=='__main__':unittest.main()
