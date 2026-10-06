import unittest
import tempfile
import subprocess
import sys
import json
from pathlib import Path
from tests.cases import case_data

class CLITests(unittest.TestCase):
    def run_cli(self,root,*args):
        return subprocess.run([sys.executable,'-m','sports_os','--legacy',*args,'--workspace',str(root)],text=True,capture_output=True)
    def test_full_cli_workflow(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for cmd in [('demo',),('validate',),('revenue',),('diff','version_a','version_b'),('snapshot',),('export-data',)]:
                r=self.run_cli(root,*cmd);self.assertEqual(r.returncode,0,(cmd,r.stdout,r.stderr))
            self.assertEqual(len(list((root/'outputs/releases').glob('SN-*'))),1)
            r=self.run_cli(root,'snapshot');self.assertEqual(r.returncode,0,r.stdout)
    def test_block_cannot_publish(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.run_cli(root,'demo');p=root/'bad.json';p.write_text(json.dumps(case_data('TEST-010')))
            for cmd in ['validate','revenue','snapshot']:
                r=self.run_cli(root,cmd,'--data','bad.json');self.assertEqual(r.returncode,2,r.stdout)
            self.assertFalse((root/'outputs/releases').exists())
    def test_json_edit_not_silently_authoritative(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.run_cli(root,'demo')
            p=root/'data/demo/version_a.json';d=json.loads(p.read_text());d['prices'][0]['price']+=7
            p.write_text(json.dumps(d));self.run_cli(root,'revenue')
            r=json.loads((root/'outputs/REVENUE.json').read_text());self.assertEqual(r['rows'][0]['price'],'730.00')
            result=self.run_cli(root,'load','data/demo/version_a.json');self.assertEqual(result.returncode,0,result.stdout)
            self.run_cli(root,'revenue');r=json.loads((root/'outputs/REVENUE.json').read_text());self.assertEqual(r['rows'][0]['price'],'737.00')
            self.assertEqual(self.run_cli(root,'demo').returncode,2)
    def test_escape_and_usb_prohibited(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self.run_cli(Path(t),'validate','--data','../outside.json').returncode,2)
            self.assertEqual(self.run_cli(Path('/Volumes/NO NAME'),'demo').returncode,2)
    def test_warning_not_blocked_validate_but_requires_snapshot_ack(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.run_cli(root,'demo');(root/'warning.json').write_text(json.dumps(case_data('TEST-009')))
            self.assertEqual(self.run_cli(root,'validate','--data','warning.json').returncode,0)
            self.assertEqual(self.run_cli(root,'snapshot','--data','warning.json').returncode,2)
            self.assertEqual(self.run_cli(root,'snapshot','--data','warning.json','--ack-warnings').returncode,0)

if __name__=='__main__':unittest.main()
