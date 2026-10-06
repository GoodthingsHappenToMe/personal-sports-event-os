import unittest
import tempfile
from pathlib import Path
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.models import ModelError,load_json
from sports_os_legacy.validators import validate
from sports_os_legacy.validators.excel import validate_xlsx
from tests.cases import CASES,case_data

class HistoricalRegressionTests(unittest.TestCase):pass

def regression(case):
    def run(self):
        g=validate(case_data(case['id']))
        self.assertEqual(g.status,case['expected'],g.to_dict())
        self.assertIn(case['rule'],{f.rule_id for f in g.findings if f.severity!='PASS'})
    run.__doc__=case['input']+' → '+case['expected']
    return run
for case in CASES:setattr(HistoricalRegressionTests,'test_'+case['id'].replace('-','_'),regression(case))

class EdgeTests(unittest.TestCase):
    def check(self,d,rule,severity='BLOCK'):
        g=validate(d)
        self.assertIn((rule,severity),{(f.rule_id,f.severity) for f in g.findings},g.to_dict())
    def test_refund_gap(self):
        d=make_demo();d['rules'][0]['content']['windows'][1]['start']='2027-07-02T00:00:00+00:00';self.check(d,'Q015')
    def test_deduction_duplicate(self):
        d=make_demo();s=d['seating'][0];s['deduction_refs']['broadcast_hold']=s['deduction_refs']['functional_hold'];self.check(d,'Q010')
    def test_percentage_120(self):
        d=make_demo();d['rules'][-1]['content']['rounds'][0]['fraction']=.45;self.check(d,'Q006')
    def test_unit_warning_and_old_year_noncritical(self):
        d=case_data('TEST-009');d['quality_evidence']['documents'][0].update(text='2026年历史说明',critical=False)
        self.assertEqual(validate(d).status,'WARNING');self.check(d,'Q011','WARNING')
    def test_negative_and_over_capacity(self):
        d=make_demo();d['seating'][0]['functional_hold']=9999;self.check(d,'Q008')
        d=make_demo();d['inventory'][0]['quantity']=-1;self.check(d,'Q001')
    def test_paid_rights_sold_not_lost(self):
        d=make_demo();d['inventory'][0]['status']='SOLD';self.assertEqual(validate(d).status,'PASS')
    def test_mismatched_inventory_times(self):
        d=make_demo();d['inventory'][0]['as_of']='2027-05-02T00:00:00+00:00';self.check(d,'Q024')
    def test_stale_hardcoded_summary(self):
        d=make_demo();d['quality_evidence']['summaries']=[dict(source='report/total',metric='totals.full_revenue',value=1,mode='HARDCODED')];self.check(d,'Q004')
    def test_missing_cell_reference(self):
        d=make_demo();d['quality_evidence']['cells']=[dict(source='Model!A1',value=None)];self.check(d,'Q003')
    def test_approved_with_draft_rule(self):
        d=make_demo();d['rules'][0]['status']='DRAFT';self.check(d,'Q019')
    def test_inconsistent_versions(self):
        d=make_demo();d['prices'][0]['price_version']='wrong-version';self.check(d,'Q027')
    def test_outputs_different_snapshot(self):
        d=make_demo();d['snapshot_id']='SN-A';d['quality_evidence']['output_refs']=[dict(source='report',snapshot_id='SN-B')];self.check(d,'Q020')
    def test_same_name_different_content(self):
        d=make_demo();d['quality_evidence']['named_models']=[dict(name='model',content=c,source='synthetic/'+c) for c in ['A','B']];self.check(d,'Q018')
    def test_time_order_and_preparation(self):
        d=make_demo();d['sessions'][0]['end_time']='2027-07-09T00:00:00+00:00';self.check(d,'Q012')
        d=make_demo();d['tasks'][0]['due_at']='2027-08-01T00:00:00+00:00';self.check(d,'Q013')
    def test_no_silent_nan_boolean_or_fractional_count(self):
        for value in [float('nan'),True,10.5]:
            d=make_demo();d['seating'][0]['physical_capacity']=value;self.check(d,'Q001')
    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad.json';p.write_text('{"year":2027,"year":2026}')
            with self.assertRaises(ModelError):load_json(p)
    def test_required_rate_no_silent_default(self):
        d=make_demo();del d['scenarios']['mid']['session_rates']['S01'];self.check(d,'Q001')
    def test_scenarios_order(self):
        d=make_demo();d['scenarios']['low']['session_rates']['S01']=1;self.check(d,'Q026')

class ExcelEdgeTests(unittest.TestCase):
    def run_book(self,values,contract=None):
        import openpyxl
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'fixture.xlsx';w=openpyxl.Workbook();s=w.active;s.title='Model'
            for cell,v in values.items():s[cell]=v
            w.save(p);w.close();before=p.read_bytes();g=validate_xlsx(p,contract)
            self.assertEqual(before,p.read_bytes());return g
    def test_errors_and_blank(self):
        for value,rule in [('=A1+#REF!','Q002'),('=1/0','Q002'),('=#VALUE!','Q002'),('=A99+1','Q003'),('=IF(1,2,3)','Q030'),('=A1','Q030')]:
            with self.subTest(value=value):
                g=self.run_book({'A1':value});self.assertEqual(g.status,'BLOCK')
                self.assertIn(rule,{f.rule_id for f in g.findings})
    def test_hardcoded_contract_mismatch(self):
        g=self.run_book({'A1':100,'A2':200,'A3':300,'A4':650},{'totals':[dict(sheet='Model',components=['A1','A2','A3'],total='A4')]})
        self.assertEqual(g.status,'BLOCK')
    def test_percent_and_parentheses(self):
        g=self.run_book({'A1':100,'A2':'=A1*(1+10%)','A3':110},{'totals':[dict(sheet='Model',components=['A2'],total='A3')]})
        self.assertEqual(g.status,'PASS',g.to_dict())

if __name__=='__main__':unittest.main()
