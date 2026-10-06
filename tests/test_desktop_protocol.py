import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from sports_os.desktop.server import DesktopSession

class DesktopProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.session=DesktopSession();self.i=0
    def call(self,method,**params):
        self.i+=1;return self.session.handle(json.dumps(dict(id=str(self.i),method=method,params=params)))
    def demo(self):
        r=self.call('create_demo',workspace=self.temp.name);self.assertTrue(r['ok'],r);return r['result']
    def test_health_registry(self):
        r=self.call('health');self.assertTrue(r['ok']);self.assertEqual(len(r['result']['modules']),19)
    def test_create_profile_incomplete_persists_safely(self):
        r=self.call('create_project',workspace=self.temp.name,identity=dict(id='SYNTHETIC-X',name='Synthetic X',timezone='UTC'),modules=['core.schedule','ticketing.refund'])
        self.assertTrue(r['ok'],r);self.assertEqual(r['result']['quality']['status'],'BLOCK')
        self.assertFalse(self.call('create_snapshot')['ok'])
        opened=DesktopSession();self.session=opened
        r=self.call('open_project',workspace=self.temp.name);self.assertTrue(r['ok']);self.assertEqual(r['result']['project']['manifest']['project']['status'],'DRAFT')
    def test_create_open_empty_project(self):
        r=self.call('create_project',workspace=self.temp.name,identity=dict(id='SYNTHETIC',name='Synthetic project',timezone='UTC'),modules=[])
        self.assertTrue(r['ok']);self.assertTrue(self.call('save_project')['ok'])
        self.assertTrue(self.call('open_project',workspace=self.temp.name)['ok'])
        # Creating into a folder that already holds a project now makes a sub-folder instead of failing,
        # and never touches the existing project.
        before=self.call('get_project')['result']['project']
        r=self.call('create_project',workspace=self.temp.name,identity=dict(id='B',name='B',timezone='UTC'),modules=[])
        self.assertTrue(r['ok'],r);self.assertEqual(Path(r['result']['workspace']).parent,Path(self.temp.name).resolve())
        self.session=DesktopSession()
        self.assertEqual(self.call('open_project',workspace=self.temp.name)['result']['project'],before)
    def test_end_to_end(self):
        state=self.demo();before=self.call('create_snapshot');self.assertTrue(before['ok'],before)
        snap=before['result']['snapshot']['snapshot_id']
        old_revenue=self.call('calculate_module',module_id='finance.revenue',snapshot_id=snap)['result']
        self.assertTrue(self.call('list_modules')['ok']);self.assertTrue(self.call('list_enabled_modules')['ok'])
        self.assertTrue(self.call('get_module_schema',module_id='ticketing.pricing')['ok'])
        data=self.call('get_module_data',module_id='ticketing.pricing')['result'];data['rows'][0]['price']=731
        edit=self.call('update_module_data',module_id='ticketing.pricing',payload=data)
        self.assertTrue(edit['ok'],edit);state=edit['result'];self.assertEqual(state['project']['manifest']['project']['status'],'DRAFT')
        self.assertFalse(self.call('create_snapshot')['ok'])
        self.assertEqual(self.call('validate_project')['result']['status'],'PASS')
        revenue=self.call('calculate_module',module_id='finance.revenue');self.assertTrue(revenue['ok'])
        self.assertNotEqual(revenue['result'],old_revenue)
        self.assertEqual(self.call('calculate_module',module_id='finance.revenue',snapshot_id=snap)['result'],old_revenue)
        self.assertTrue(self.call('approve_module',module_id='ticketing.pricing',approval_ref='SYNTHETIC-MANUAL',data_version=state['project']['modules']['ticketing.pricing']['data_version'])['ok'])
        self.assertTrue(self.call('approve_project',approval_ref='SYNTHETIC-PROJECT',version=state['project']['manifest']['project']['version'])['ok'])
        self.assertTrue(self.call('create_snapshot')['ok']);self.assertEqual(len(self.call('list_snapshots')['result']),2)
        self.assertEqual(self.call('get_snapshot',snapshot_id=snap)['result'],before['result']['snapshot'])
        self.assertTrue(self.call('compare_versions',old=snap,new='WORKING')['result']['business'])
        self.assertTrue(self.call('open_project',workspace=self.temp.name)['ok'])
    def test_patch_and_dependency(self):
        self.demo();self.assertFalse(self.call('disable_module',module_id='core.schedule')['ok'])
        self.assertTrue(self.call('disable_module',module_id='product.travel')['ok'])
        self.assertTrue(self.call('enable_module',module_id='product.travel')['ok'])
        self.assertTrue(self.call('apply_changeset',module_id='ticketing.pricing',changes=[dict(path=['rows',0,'price'],value=732)])['ok'])
    def test_malformed(self):
        for line in ('{','[]','{"id":"x","method":"health","params":{},"id":"y"}','{"id":2,"method":"health","params":{}}'):
            r=self.session.handle(line);self.assertFalse(r['ok']);self.assertEqual(r['error']['code'],'PROTOCOL')
    def test_unknown_method(self):
        self.demo();r=self.call('eval',code='bad');self.assertEqual(r['error']['code'],'UNKNOWN_METHOD')
    def test_exception_is_structured(self):
        with patch.object(self.session,'dispatch',side_effect=RuntimeError('synthetic failure')):
            r=self.call('health');self.assertEqual(r['error']['code'],'UNEXPECTED');self.assertIn('technical',r['error']['details'])
    def test_duplicate_concurrent_id(self):
        req=json.dumps(dict(id='same',method='health',params={}))
        with ThreadPoolExecutor(2) as pool:responses=list(pool.map(self.session.handle,[req,req]))
        self.assertEqual(sum(r['ok'] for r in responses),1)
        self.assertIn('DUPLICATE_ID',[r.get('error',{}).get('code') for r in responses])
    def test_stdout_is_protocol(self):
        lines=[dict(id=str(i),method='health',params={}) for i in range(2)]
        p=subprocess.run([sys.executable,'-m','sports_os.desktop.server'],input='\n'.join(json.dumps(x) for x in lines)+'\n',text=True,capture_output=True)
        self.assertEqual(p.returncode,0);self.assertEqual(len(p.stdout.splitlines()),2)
        self.assertTrue(all(json.loads(line)['ok'] for line in p.stdout.splitlines()))
    def test_draft_tamper_blocks(self):
        # An incomplete new project starts as a draft.
        self.call('create_project',workspace=self.temp.name,identity=dict(id='S',name='Synthetic',timezone='UTC'),modules=['core.schedule','ticketing.refund'])
        # Drafts live in the working store; a forged approval claim inside one must not open.
        import sqlite3
        con=sqlite3.connect(Path(self.temp.name)/'data/modular.sqlite')
        record=json.loads(con.execute('SELECT record FROM drafts').fetchone()[0]);record['manifest']['project']['status']='APPROVED'
        con.execute('UPDATE drafts SET record=?',(json.dumps(record),));con.commit();con.close()
        self.assertFalse(self.call('open_project',workspace=self.temp.name)['ok'])
    def test_approve_requires_reference_current_version(self):
        state=self.demo();self.call('apply_changeset',module_id='ticketing.pricing',changes=[dict(path=['rows',0,'price'],value=731)])
        r=self.call('approve_module',module_id='ticketing.pricing',approval_ref='SYNTHETIC',data_version=state['project']['modules']['ticketing.pricing']['data_version'])
        self.assertFalse(r['ok']);self.assertEqual(r['error']['code'],'APPROVAL')
    def test_failed_persist_does_not_replace_session(self):
        self.demo();before=self.session.project.to_dict()
        with patch.object(self.session.app,'persist_desktop_project',side_effect=OSError('Synthetic disk failure')):
            self.assertFalse(self.call('apply_changeset',module_id='ticketing.pricing',changes=[dict(path=['rows',0,'price'],value=731)])['ok'])
        self.assertEqual(before,self.session.project.to_dict())
