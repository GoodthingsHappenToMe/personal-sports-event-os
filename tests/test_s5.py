import unittest
import tempfile
import sqlite3
from pathlib import Path
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.database import Store
from sports_os_legacy.versioning.snapshot import create_snapshot,verify_snapshot,ReleaseBlocked
from sports_os_legacy.exporters import export_release
from tests.cases import case_data

class SnapshotTests(unittest.TestCase):
    def test_immutable_and_repeatable(self):
        with tempfile.TemporaryDirectory() as t:
            st=Store(Path(t)/'state.db');a=create_snapshot(make_demo(),st);b=create_snapshot(make_demo(),st)
            self.assertEqual(a,b);verify_snapshot(a)
            with st.connect() as c:
                with self.assertRaises(sqlite3.IntegrityError):c.execute('UPDATE snapshots SET record=record')
                with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM snapshots')
    def test_block_writes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            st=Store(Path(t)/'new.db')
            with self.assertRaises(ReleaseBlocked):create_snapshot(case_data('TEST-010'),st)
            self.assertFalse(st.path.exists())
    def test_warning_requires_ack(self):
        with tempfile.TemporaryDirectory() as t:
            st=Store(Path(t)/'state.db');d=case_data('TEST-009')
            with self.assertRaises(ReleaseBlocked):create_snapshot(d,st)
            r=create_snapshot(d,st,ack_warnings=True);self.assertTrue(r['warnings_acknowledged'])
    def test_tamper_blocks_export(self):
        with tempfile.TemporaryDirectory() as t:
            st=Store(Path(t)/'state.db');r=create_snapshot(make_demo(),st);r['data']['prices'][0]['price']+=1
            path=Path(t)/'releases'
            with self.assertRaises(ReleaseBlocked):export_release(r,path)
            self.assertFalse(path.exists())
    def test_metadata_tamper(self):
        with tempfile.TemporaryDirectory() as t:
            r=create_snapshot(make_demo(),Store(Path(t)/'state.db'));r['price_version']='unrelated'
            with self.assertRaises(ReleaseBlocked):verify_snapshot(r)
    def test_release_single_snapshot_and_idempotent(self):
        import json
        with tempfile.TemporaryDirectory() as t:
            r=create_snapshot(make_demo(),Store(Path(t)/'state.db'));p=export_release(r,Path(t)/'releases')
            self.assertEqual(p,export_release(r,Path(t)/'releases'))
            for name in ['snapshot.json','revenue.json','manifest.json']:
                self.assertEqual(json.loads((p/name).read_text())['snapshot_id'],r['snapshot_id'])
            (p/'REVENUE.md').write_text('tampered')
            with self.assertRaises(ReleaseBlocked):export_release(r,Path(t)/'releases')

if __name__=='__main__':unittest.main()
