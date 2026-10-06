import unittest
import tempfile
from pathlib import Path
from sports_os_legacy.models import assert_model, ModelError, sellable, occupancy
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.database import Store

class ModelTests(unittest.TestCase):
    def test_demo_shape(self):
        d=assert_model(make_demo());self.assertEqual(len(d['sessions']),16)
        self.assertEqual(len({s['stage'] for s in d['sessions']}),4)
        self.assertEqual(sum(s['physical_capacity'] for s in d['seating'] if s['session_id']=='S01'),8040)
    def test_derived_and_paid_rights(self):
        s=make_demo()['seating'][0];n=sellable(s);s['paid_rights']+=1
        self.assertEqual(sellable(s),n)
    def test_product_mapping(self):
        d=make_demo();self.assertEqual(sum(occupancy(d['products'][1]).values()),16)
        self.assertEqual(sum(occupancy(d['products'][2],3).values()),6)
    def test_sqlite_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            st=Store(Path(t)/'test.sqlite');d=make_demo();st.save(d);self.assertEqual(st.load(),d)
            with st.connect() as con:
                self.assertEqual(con.execute('SELECT count(*) FROM sessions').fetchone()[0],16)
                self.assertEqual(con.execute("SELECT ticket_quantity FROM products WHERE product_id='TRAVEL-TWIN-DEMO'").fetchone()[0],2)
                self.assertEqual(con.execute('SELECT sellable_capacity FROM seating LIMIT 1').fetchone()[0],sellable(d['seating'][0]))
    def test_invalid_key_type_and_missing(self):
        for mutate in [lambda d:d['seating'][0].update(physical_capacity=True),lambda d:d['sessions'].append(d['sessions'][0]),
                       lambda d:d['prices'].pop(0),lambda d:d['event'].update(phone='private')]:
            d=make_demo();mutate(d)
            with self.assertRaises(ModelError):assert_model(d)
    def test_dependency_cycle(self):
        d=make_demo();d['tasks'][0]['depends_on']=['T1']
        with self.assertRaises(ModelError):assert_model(d)

if __name__=='__main__':unittest.main()
