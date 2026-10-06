"""Regression tests for validator gaps found in the review (rights, refund, launch, products)."""
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
import json
from sports_os.application import ApplicationService
from sports_os_legacy.migration import migrate_v10
from sports_os_legacy.models.demo import make_demo
from sports_os.kernel.snapshot import ReleaseBlocked


class ValidatorPolishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = ApplicationService(self.temp.name)
        self.p = migrate_v10(make_demo(), self.app.registry)

    def payload(self, key):
        return self.p.states[key].payload

    def gate(self):
        return self.app.validate_project(self.p)

    def rule_ids(self, gate):
        return {f.rule_id for f in gate.findings}

    def test_baseline_is_clean(self):
        self.assertEqual(self.gate().status, 'PASS')

    def test_fixed_price_rejects_more_than_two_decimals(self):
        row = self.payload('ticketing.rights')['rows'][0]
        row.update(strategy='FIXED_PRICE', value=333.3333)
        self.assertEqual(self.gate().status, 'BLOCK')
        row['value'] = 333.33
        self.assertEqual(self.gate().status, 'PASS')

    def test_face_value_requires_value_one(self):
        row = self.payload('ticketing.rights')['rows'][0]
        row['value'] = 999
        self.assertEqual(self.gate().status, 'BLOCK')

    def test_launch_round_cannot_be_zero(self):
        rounds = self.payload('ticketing.launch')['rows'][0]['content']['rounds']
        rounds[0]['fraction'] = 0
        rounds[1]['fraction'] = 0.7
        self.assertEqual(self.gate().status, 'BLOCK')

    def test_refund_fee_decreasing_is_a_warning(self):
        windows = self.payload('ticketing.refund')['rows'][0]['content']['windows']
        windows[0]['fee_rate'], windows[2]['fee_rate'] = 1, 0
        gate = self.gate()
        self.assertEqual(gate.status, 'WARNING')
        self.assertIn('REFUND_FEE_DECREASING', self.rule_ids(gate))

    def test_refund_fee_increasing_has_no_warning(self):
        self.assertNotIn('REFUND_FEE_DECREASING', self.rule_ids(self.gate()))

    def test_pass_below_face_is_a_warning_with_amounts(self):
        face = next(r['ticket_amount'] for r in self.app.calculate_module(self.p, 'product.pass')
                    if r['product_id'] == 'PASS-DEMO')
        rows = self.payload('product.pass')['rows']
        index = next(i for i, row in enumerate(rows) if row['product_id'] == 'PASS-DEMO')
        rows[index].update(price=1.0, price_claim='INDEPENDENT')
        gate = self.gate()
        self.assertEqual(gate.status, 'WARNING')
        finding = next(f for f in gate.findings if f.rule_id == 'PRODUCT_BELOW_FACE')
        # Sources are editor field paths so the desktop app can focus the field.
        self.assertEqual(finding.source, f'product.pass/rows/{index}/price')
        self.assertEqual(Decimal(finding.actual), Decimal('1'))
        self.assertIn(str(face), finding.message)
        self.assertIn(str(face-1), finding.message)

    def test_pass_at_or_above_face_has_no_warning(self):
        face = next(r['ticket_amount'] for r in self.app.calculate_module(self.p, 'product.pass')
                    if r['product_id'] == 'PASS-DEMO')
        for price in (face, face+1):
            with self.subTest(price=price):
                for row in self.payload('product.pass')['rows']:
                    if row['product_id'] == 'PASS-DEMO':
                        row.update(price=float(price), price_claim='INDEPENDENT')
                self.assertEqual(self.gate().status, 'PASS')

    def test_travel_discount_does_not_bypass_price_reconciliation(self):
        row = self.payload('product.travel')['rows'][0]
        row.update(price=1, price_claim='INDEPENDENT')
        gate = self.gate()
        self.assertEqual(gate.status, 'BLOCK')
        self.assertTrue(any(f.rule_id == 'PRODUCT_BELOW_FACE' and f.severity == 'WARNING'
                            and f.source == 'product.travel/rows/0/price' for f in gate.findings))
        self.assertTrue(any(f.rule_id == 'TRAVEL_TOTAL_MISMATCH' and f.source == 'product.travel/rows/0/price'
                            for f in gate.findings))

    def assert_warning_snapshot_requires_ack(self, module_id, payload, rule_id):
        project = self.app.update_module_data(self.p, module_id, payload)
        state = project.states[module_id]
        project = self.app.approve_module(project, module_id, 'SYNTHETIC-POLISH', state.data_version)
        project = self.app.approve_project(project, 'SYNTHETIC-POLISH', project.manifest['project']['version'])
        with self.assertRaises(ReleaseBlocked):
            self.app.create_snapshot(project)
        self.assertEqual(self.app.list_snapshots(project.manifest['project']['id']), [])
        snapshot = self.app.create_snapshot(project, ack_warnings=True)
        self.assertTrue(snapshot['warnings_acknowledged'])
        self.assertIn(rule_id, {f['rule_id'] for f in snapshot['quality_gate']['findings']})

    def test_pass_warning_snapshot_requires_ack(self):
        payload = self.app.get_module_data(self.p, 'product.pass')
        next(r for r in payload['rows'] if r['product_id'] == 'PASS-DEMO').update(price=1, price_claim='INDEPENDENT')
        self.assert_warning_snapshot_requires_ack('product.pass', payload, 'PRODUCT_BELOW_FACE')

    def test_refund_warning_snapshot_requires_ack(self):
        payload = self.app.get_module_data(self.p, 'ticketing.refund')
        windows = payload['rows'][0]['content']['windows']
        windows[0]['fee_rate'], windows[2]['fee_rate'] = 1, 0
        self.assert_warning_snapshot_requires_ack('ticketing.refund', payload, 'REFUND_FEE_DECREASING')

    def test_refund_fee_warning_uses_time_order_not_input_order(self):
        self.payload('ticketing.refund')['rows'][0]['content']['windows'].reverse()
        self.assertEqual(self.gate().status, 'PASS')


class DesktopTracebackTests(unittest.TestCase):
    def test_health_version_matches_desktop_config(self):
        from sports_os.desktop.server import DesktopSession
        config = json.loads((Path(__file__).resolve().parents[1] /
                             'apps/desktop/src-tauri/tauri.conf.json').read_text())
        result = DesktopSession().handle('{"id":"health","method":"health","params":{}}')
        self.assertTrue(result['ok'])
        self.assertEqual(result['result']['desktop_version'], config['version'])

    def error_with_debug(self, value):
        import os
        from unittest.mock import patch
        from sports_os.desktop.server import DesktopSession
        session = DesktopSession()
        with patch.object(session, 'dispatch', side_effect=RuntimeError('boom')), \
                patch.dict(os.environ, {'SPORTS_OS_DEBUG': value}):
            return session.handle('{"id":"debug","method":"health","params":{}}')

    def test_debug_zero_does_not_enable_tracebacks(self):
        self.assertEqual(self.error_with_debug('0')['error']['details']['technical'], 'RuntimeError: boom')

    def test_debug_one_explicitly_enables_tracebacks(self):
        self.assertIn('Traceback', self.error_with_debug('1')['error']['details']['technical'])

    def test_default_error_details_do_not_include_traceback(self):
        import os
        from unittest.mock import patch
        from sports_os.desktop.server import DesktopSession
        session = DesktopSession()
        line = '{"id":"t1","method":"health","params":{}}'
        with patch.object(session, 'dispatch', side_effect=RuntimeError('boom')), \
                patch.dict(os.environ, {}, clear=False):
            os.environ.pop('SPORTS_OS_DEBUG', None)
            r = session.handle(line)
        self.assertEqual(r['error']['details']['technical'], 'RuntimeError: boom')
        self.assertNotIn('Traceback', r['error']['details']['technical'])


if __name__ == '__main__':
    unittest.main()
