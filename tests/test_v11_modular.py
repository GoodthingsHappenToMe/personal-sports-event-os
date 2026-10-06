import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from sports_os.application import ApplicationService
from sports_os_legacy.migration import migrate_v10
from sports_os.application.manifest import render_manifest,parse_manifest
from sports_os.kernel import Module,ModuleState,Registry
from sports_os.kernel.data import KernelError,canonical
from sports_os.kernel.snapshot import verify_snapshot,ReleaseBlocked
from sports_os_legacy.models.demo import make_demo
from sports_os_legacy.revenue import calculate as legacy_calculate

class ModularTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=ApplicationService(self.temp.name);self.p=migrate_v10(make_demo(),self.app.registry)
    def gate(self,p=None):return self.app.validate_project(p or self.p)
    def payload(self,key):return self.p.states[key].payload
    def free_project(self):
        p=deepcopy(self.p);keys=['core.schedule','core.venue','project.tasks']
        p.manifest['modules']={k:True for k in keys};p.states={k:p.states[k] for k in keys};return p
    def test_MOD_001_kernel_schedule(self):
        """MOD-001: Kernel+Schedule，无票务 → PASS"""
        p=self.free_project();p.manifest['modules']={'core.schedule':True};p.states={'core.schedule':p.states['core.schedule']}
        self.assertEqual(self.gate(p).status,'PASS')
    def test_MOD_002_no_travel_validator(self):
        """MOD-002: 禁用Travel → validator绝不运行"""
        self.p=self.app.disable_module(self.p,'product.travel')
        with patch.object(self.app.registry.get('product.travel'),'validate',side_effect=AssertionError('must not run')):
            self.assertEqual(self.gate().status,'PASS')
    def test_MOD_003_free_event_snapshot(self):
        """MOD-003: 免费群众赛事 → validate/snapshot成功"""
        p=self.free_project();self.assertEqual(self.gate(p).status,'PASS')
        record=self.app.create_snapshot(p);verify_snapshot(record)
        self.assertFalse(any(k.startswith('ticketing.') for k in record['module_index']))
    def test_MOD_004_missing_travel_dependency(self):
        """MOD-004: Travel缺Pricing → BLOCK"""
        self.p.manifest['modules']['ticketing.pricing']=False
        self.assertEqual(self.gate().status,'BLOCK')
    def test_MOD_005_disabled_payload_quarantined(self):
        """MOD-005: 保留损坏的禁用payload，不执行/不冻结"""
        self.p=self.app.disable_module(self.p,'product.travel');self.payload('product.travel')['rows']='malformed'
        self.app.save_project(self.p);opened=self.app.open_project()
        self.assertEqual(opened.states['product.travel'].payload['rows'],'malformed')
        opened.manifest['project'].update(status='APPROVED',approval_ref='SYNTHETIC-REAPPROVAL')
        record=self.app.create_snapshot(opened)
        self.assertNotIn('product.travel',record['project']['modules'])
        self.assertFalse(record['project']['manifest']['modules']['product.travel'])
    def test_MOD_006_cycle(self):
        """MOD-006: 模块依赖环 → BLOCK"""
        class A(Module):
            module_id='test.a';dependencies=('test.b',)
            def schema(self):return {'type':'object'}
        class B(A):module_id='test.b';dependencies=('test.a',)
        for m in [A(),B()]:
            self.app.registry.register(m);self.p.manifest['modules'][m.module_id]=True
        self.assertEqual(self.gate().status,'BLOCK')
    def test_MOD_007_price_class(self):
        """MOD-007: 同tier不同zone不同price_class → 分别按价计算"""
        before=self.app.calculate_module(self.p,'finance.revenue')['totals']['full_revenue']
        seat=self.payload('ticketing.seating')['rows'][0];seat['price_class_id']='VIP-RESTRICTED-PRICE'
        price=deepcopy(self.payload('ticketing.pricing')['rows'][0]);price.update(price_class_id=seat['price_class_id'],price=700)
        self.payload('ticketing.pricing')['rows'].append(price)
        after=self.app.calculate_module(self.p,'finance.revenue')['totals']['full_revenue']
        from sports_os.modules.seating import sellable
        self.assertEqual(before-after,sellable(seat)*30)
        self.assertEqual(seat['tier'],'VIP')
    def test_MOD_008_rights_discount(self):
        """MOD-008: 权益8折 → 采用有效单价，非公开价"""
        before=self.app.calculate_module(self.p,'finance.revenue')['totals']
        row=self.payload('ticketing.rights')['rows'][0];row.update(strategy='DISCOUNT_RATE',value=.8)
        after=self.app.calculate_module(self.p,'finance.revenue')['totals']
        self.assertEqual(before['full_revenue']-after['full_revenue'],row['quantity']*Decimal('146'))
        self.assertEqual(before['scenarios']['mid']['revenue']-after['scenarios']['mid']['revenue'],row['quantity']*Decimal('146'))
    def test_MOD_009_travel_missing_price(self):
        """MOD-009: Travel含非票成本但price=null → BLOCK，不能snapshot"""
        self.payload('product.travel')['rows'][0].update(price=None,price_claim='SUM_FACE_PRICES')
        self.assertEqual(self.gate().status,'BLOCK')
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(self.p)
        self.assertFalse(self.app.store.path.exists())
    def test_MOD_010_rule_expiry(self):
        """MOD-010: 所有规则模块适用期检查 → 过期BLOCK"""
        for key in ['identity','transfer','rights_return','launch','refund']:
            with self.subTest(key=key):
                p=deepcopy(self.p);p.states['ticketing.'+key].payload['rows'][0]['valid_to']='2027-05-02T00:00:00+00:00'
                self.assertEqual(self.gate(p).status,'BLOCK')
    def test_MOD_011_zone_split(self):
        """MOD-011: 经济事实不变，zone拆分 → 精确总收入完全不变"""
        for key in ['ticketing.inventory','ticketing.rights','product.travel','product.pass']:
            self.p=self.app.disable_module(self.p,key)
        self.payload('demand.multiplicative')['scenarios']['mid']['session_rates']['S01']=.7133333333
        a=self.app.calculate_module(self.p,'finance.revenue')
        row=self.payload('ticketing.seating')['rows'][0];other=deepcopy(row);other['zone_id']='SPLIT'
        for k in ['physical_capacity','functional_hold','broadcast_hold','free_rights','other_hold']:
            other[k]=row[k]//2;row[k]-=other[k]
        self.payload('ticketing.seating')['rows'].append(other)
        b=self.app.calculate_module(self.p,'finance.revenue')
        self.assertEqual(a['totals'],b['totals'])
    def test_MOD_012_product_order(self):
        """MOD-012: 产品included_sessions仅重排 → 无业务差异"""
        b=deepcopy(self.p);b.states['product.pass'].payload['rows'][1]['included_sessions'].reverse()
        self.assertFalse(self.app.compare_versions(self.p,b)['business'])
    def test_MOD_013_only_active_findings(self):
        """MOD-013: Disabled未知模块坏payload → 不产生Finding"""
        self.p.manifest['modules']['unknown.disabled']=False
        self.p.states['unknown.disabled']=ModuleState('bad','bad',{'invalid':'ignored'})
        self.assertEqual(self.gate().status,'PASS')
        self.assertFalse(any('unknown' in f.source for f in self.gate().findings))
    def test_MOD_014_snapshot_enable(self):
        """MOD-014: snapshot后启用新模块 → 历史记录字节/索引不变"""
        p=self.free_project();old=self.app.create_snapshot(p);before=canonical(old)
        p=self.app.enable_module(p,'project.decisions',{'rows':[]})
        self.app.save_project(p)
        self.assertEqual(canonical(self.app.list_snapshots(p.manifest['project']['id'])[0]),before)
    def test_MOD_015_upgrade_without_migration(self):
        """MOD-015: 插件升级无migration → BLOCK，不静默解释"""
        m=self.app.registry.get('product.travel');m.module_version='2.0';m.schema_version='2'
        self.assertEqual(self.gate().status,'BLOCK')
        with self.assertRaises(KernelError):self.app.migrate_module(self.p,'product.travel')
    def test_MOD_016_migration(self):
        """MOD-016: v1.0迁移 → 与修正舍入后的模型精确对账"""
        old=legacy_calculate(make_demo());new=self.app.calculate_module(self.p,'finance.revenue')
        self.assertEqual(Decimal(old['totals']['full_revenue_exact']),new['totals']['full_revenue'])
        for name in ('low','mid','high'):
            self.assertEqual(Decimal(old['totals'][name]['revenue_exact']),new['totals']['scenarios'][name]['revenue'])
        self.assertEqual(self.gate().status,'PASS')
    def test_rights_fixed_price(self):
        self.payload('ticketing.rights')['rows'][0].update(strategy='FIXED_PRICE',value=321)
        result=self.app.calculate_module(self.p,'ticketing.rights')
        self.assertEqual(next(iter(result.values()))['effective_unit_price'],321)
    def test_disable_rights_requires_inventory_reconciliation(self):
        p=self.app.disable_module(self.p,'ticketing.rights')
        self.assertEqual(self.gate(p).status,'BLOCK')
        p=self.app.disable_module(p,'ticketing.inventory')
        self.assertEqual(self.gate(p).status,'PASS')
    def test_revenue_and_inventory_independent(self):
        for key in ('finance.revenue','ticketing.inventory','product.travel'):
            self.p=self.app.disable_module(self.p,key)
        self.assertEqual(self.gate().status,'PASS')
    def test_replace_demand(self):
        old=self.app.calculate_module(self.p,'finance.revenue')
        normalized=self.app.calculate_module(self.p,'demand.multiplicative')
        payload={'scenarios':{name:[dict(session_id=k[0],zone_id=k[1],tier=k[2],rate=float(rate)) for k,rate in rows.items()] for name,rows in normalized.items()}}
        p=self.app.replace_module(self.p,'demand.multiplicative','demand.direct',payload)
        self.assertEqual(self.app.calculate_module(p,'finance.revenue')['totals'],old['totals'])
    def test_demand_missing_conflicting_and_unknown(self):
        self.p.manifest['modules']['demand.multiplicative']=False
        self.assertEqual(self.gate().status,'BLOCK')
        self.p.manifest['modules']['not.installed']=True
        self.assertEqual(self.gate().status,'BLOCK')
    def test_snapshot_integrity_and_immutable(self):
        r=self.app.create_snapshot(self.p)
        with self.app.store.connect() as con:
            for table in ('snapshots','snapshot_modules'):
                with self.assertRaises(sqlite3.IntegrityError):con.execute('DELETE FROM '+table)
        b=deepcopy(r);b['created_at']='tamper'
        with self.assertRaises(ReleaseBlocked):verify_snapshot(b)
        target=self.app.export_artifact(r);self.assertEqual(target,self.app.export_artifact(r))
        (target/'artifacts.json').write_text('tamper')
        with self.assertRaises(ReleaseBlocked):self.app.export_artifact(r)
    def test_version_reuse_blocks(self):
        self.app.create_snapshot(self.p)
        self.p.states['product.pass'].payload['rows'][0]['price_claim']='INDEPENDENT'
        self.p.states['product.pass'].payload['rows'][0]['price']=700
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(self.p)
        self.p.manifest['project']['version']='next'
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(self.p)
    def test_travel_closure_and_no_double_count(self):
        before=self.app.calculate_module(self.p,'finance.revenue')['totals']
        p=self.app.disable_module(self.p,'product.travel')
        self.assertEqual(before,self.app.calculate_module(p,'finance.revenue')['totals'])
        self.payload('product.travel')['rows'][0]['price']+=1
        self.assertEqual(self.gate().status,'BLOCK')
    def test_kernel_business_independence(self):
        kernel=Path(__file__).parents[1]/'src/sports_os/kernel'
        for path in kernel.glob('*.py'):
            text=path.read_text()
            for forbidden in ('ticketing.','product.travel','refund','paid_rights','price_class','from ..modules','from ..models'):
                self.assertNotIn(forbidden,text,(path.name,forbidden))
    def test_schema_missing_false_nan_unknown(self):
        for value in (True,float('nan'),-1,1e308):
            p=deepcopy(self.p);p.states['ticketing.pricing'].payload['rows'][0]['price']=value
            self.assertEqual(self.gate(p).status,'BLOCK')
        del self.payload('ticketing.pricing')['rows'][0]['price_class_id']
        self.assertEqual(self.gate().status,'BLOCK')
    def test_old_snapshot_not_relabelled(self):
        d=make_demo();d['snapshot_id']='SN-old'
        with self.assertRaises(KernelError):migrate_v10(d,self.app.registry)
    def test_manifest_roundtrip(self):
        path=Path(self.temp.name)/'project.toml';path.write_text(render_manifest(self.p.manifest))
        self.assertEqual(parse_manifest(path),self.p.manifest)
    def test_fresh_cli(self):
        for args in [('demo',),('validate',),('revenue',),('diff','version_a','version_b'),('snapshot',),('snapshots',),('export-data',)]:
            result=subprocess.run([sys.executable,'-m','sports_os',*args,'--workspace',self.temp.name],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,(args,result.stdout,result.stderr))
        self.assertTrue((Path(self.temp.name)/'project.toml').exists())
    def test_profiles_not_runtime_modes(self):
        p=self.app.demo('non-ticketed-event')
        self.assertEqual(self.gate(p).status,'PASS')
        self.assertNotIn('profile',p.manifest['project'])
    def test_external_entrypoint_discovery(self):
        """实际通过临时独立distribution元数据发现插件，不改Kernel注册表。"""
        root=Path(self.temp.name);dist=root/'synthetic_extension-0.1.dist-info';dist.mkdir()
        (dist/'METADATA').write_text('Metadata-Version: 2.1\nName: synthetic-extension\nVersion: 0.1\n')
        (dist/'entry_points.txt').write_text('[sports_os.modules]\nsynthetic.external = synthetic_external:External\n')
        (root/'synthetic_external.py').write_text('from sports_os.kernel import Module\nclass External(Module):\n module_id="synthetic.external"\n def schema(self): return {"type":"object","properties":{},"additionalProperties":False}\n def calculate(self,c): return 42\n')
        sys.path.insert(0,str(root));self.addCleanup(lambda:sys.path.remove(str(root)))
        registry=Registry.discover();app=ApplicationService(root,registry)
        p=app.create_project(dict(id='FREE',name='Synthetic extension event',timezone='UTC'))
        p=app.enable_module(p,'synthetic.external',{})
        self.assertEqual(app.calculate_module(p,'synthetic.external'),42)
    def test_working_hash_tamper(self):
        self.app.save_project(self.p)
        with self.app.store.connect() as con:con.execute("UPDATE module_state SET payload='{}' WHERE module_id='product.travel'")
        with self.assertRaises(KernelError):self.app.open_project()

class MigratedHistoricalTests(unittest.TestCase):
    pass

def historic(case):
    def run(self):
        from tests.cases import case_data
        with tempfile.TemporaryDirectory() as t:
            app=ApplicationService(t);p=app.migrate_v10(case_data(case['id']))
            self.assertEqual(app.validate_project(p).status,case['expected'])
    run.__doc__='模块化迁移 '+case['id']+': '+case['input']+' → '+case['expected']
    return run
from tests.cases import CASES
for case in CASES:setattr(MigratedHistoricalTests,'test_migrated_'+case['id'].replace('-','_'),historic(case))

class AdditionalBoundaryTests(ModularTests):
    # Reuse fixtures without re-running inherited tests (loader overridden below).
    def test_evidence_confirmed_vs_unconfirmed(self):
        from sports_os_legacy.models.demo import make_version_b
        b=self.app.migrate_v10(make_version_b(make_demo()))
        diff=self.app.compare_versions(self.p,b)
        fact=next(x for x in diff['business']['ticketing.pricing'] if x['path']=='/S01/VIP/price')
        self.assertIn('已确认',fact['reasons'][0]['kind'])
        b.evidence[-1]['confirmed']=False
        fact=next(x for x in self.app.compare_versions(self.p,b)['business']['ticketing.pricing'] if x['path']=='/S01/VIP/price')
        self.assertIn('推测原因',fact['reasons'][0]['kind'])
    def test_optional_module_no_calculation(self):
        self.assertIsNone(self.app.calculate_module(self.p,'project.tasks'))
    def test_all_module_calculations_json_serializable(self):
        for key in self.p.enabled:
            result=self.app.calculate_module(self.p,key)
            json.loads(self.app.json_text(result))
    def test_schema_upgrade_explicit_migration(self):
        from sports_os.modules.venue import Venue
        class NewVenue(Venue):
            module_version='1.2.0';schema_version='2'
            def migrate(self,old_version,old_schema,payload):
                if (old_version,old_schema)!=('1.1.0','1'):raise KernelError('unsupported migration')
                return payload
        self.app.registry.register(NewVenue(),replace=True)
        self.assertEqual(self.gate().status,'BLOCK')
        p=self.app.migrate_module(self.p,'core.venue')
        self.assertEqual(self.app.validate_project(p).status,'PASS')
        self.assertEqual(self.app.validate_project(p,True).status,'BLOCK')
        self.assertEqual(p.states['core.venue'].status,'DRAFT')
    def test_unknown_disabled_plugin_not_loaded(self):
        p=self.free_project();p.manifest['modules']['external.uninstalled']=False
        self.assertEqual(self.gate(p).status,'PASS')
    def test_warning_ack_snapshot(self):
        self.payload('quality.declarations')['metrics']=[dict(metric_id='count',source='demo',unit=u) for u in ('订单','票张')]
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(self.p)
        self.assertTrue(self.app.create_snapshot(self.p,True)['warnings_acknowledged'])
    def test_no_mutation_by_calculation_or_export(self):
        before=canonical(self.p.to_dict());result=self.app.calculate_module(self.p,'finance.revenue')
        result['totals']['full_revenue']=0
        self.assertEqual(canonical(self.p.to_dict()),before)
        self.assertNotEqual(self.app.calculate_module(self.p,'finance.revenue')['totals']['full_revenue'],0)
    def test_missing_demand_rate_no_default(self):
        del self.payload('demand.multiplicative')['scenarios']['mid']['session_rates']['S01']
        self.assertEqual(self.gate().status,'BLOCK')
    def test_demand_provider_conflict(self):
        self.p.manifest['modules']['demand.direct']=True
        self.assertEqual(self.gate().status,'BLOCK')
    def test_sales_window_and_last_rights_node(self):
        p=deepcopy(self.p)
        p.states['ticketing.rights_return'].payload['rows'][0]['valid_to']='2027-07-10T00:00:00+00:00'
        self.assertEqual(self.gate(p).status,'BLOCK')
        p=deepcopy(self.p)
        p.states['ticketing.launch'].payload['rows'][0]['content']['rounds'][0]['at']='2027-04-01T00:00:00+00:00'
        self.assertEqual(self.gate(p).status,'BLOCK')
    def test_sensitivity_and_group_exactness(self):
        r=self.app.calculate_module(self.p,'finance.revenue')
        for group in ('by_stage','by_tier','by_session'):
            for name in ('low','mid','high'):
                self.assertEqual(sum(x['scenarios'][name]['revenue'] for x in r[group].values()),r['totals']['scenarios'][name]['revenue'])
        self.assertGreater(r['sensitivity']['mid']['public_demand_plus_1pp_delta'],0)
    def test_seat_edit_propagates_and_inventory_blocks(self):
        before=self.app.calculate_module(self.p,'finance.revenue')['totals']['full_revenue']
        self.payload('ticketing.seating')['rows'][0]['physical_capacity']+=1
        self.assertEqual(self.gate().status,'BLOCK')
        self.p=self.app.disable_module(self.p,'ticketing.inventory')
        self.assertEqual(self.app.calculate_module(self.p,'finance.revenue')['totals']['full_revenue']-before,730)
    def test_blank_evidence_role_not_confirmed(self):
        b=deepcopy(self.p);b.states['ticketing.pricing'].payload['rows'][0]['price']+=1
        b.evidence.append(dict(module_id='ticketing.pricing',changed_paths=['/S01/VIP/price'],reason='Synthetic reason',source_ref='SYNTHETIC-SOURCE',confirmed=True,approved_by_role=' '))
        fact=self.app.compare_versions(self.p,b)['business']['ticketing.pricing'][0]
        self.assertIn('推测原因',fact['reasons'][0]['kind'])
    def test_decimal_context_does_not_change_result(self):
        from decimal import localcontext,ROUND_FLOOR
        expected=self.app.calculate_module(self.p,'finance.revenue')
        with localcontext() as context:
            context.prec=5;context.rounding=ROUND_FLOOR
            self.assertEqual(expected,self.app.calculate_module(self.p,'finance.revenue'))
    def test_snapshot_diff_metadata(self):
        a=self.app.create_snapshot(self.p)
        p=deepcopy(self.p);p.manifest['project']['version']='second-version'
        b=self.app.create_snapshot(p)
        diff=self.app.compare_versions(a,b)
        self.assertFalse(diff['business']);self.assertTrue(diff['snapshot_metadata'])
    def test_configuration_edit_invalidates_approval_in_service(self):
        p=self.app.disable_module(self.p,'product.travel')
        self.assertEqual(p.manifest['project']['status'],'DRAFT')
        self.assertFalse(p.manifest['project']['approval_ref'])
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(p)
        self.assertEqual(self.p.manifest['project']['status'],'APPROVED')
    def test_failed_dependency_change_is_atomic(self):
        before=canonical(self.p.to_dict())
        with self.assertRaises(KernelError):self.app.disable_module(self.p,'ticketing.pricing')
        self.assertEqual(canonical(self.p.to_dict()),before)
    def test_unknown_schema_properties_block(self):
        self.payload('ticketing.pricing')['rows'][0]['unknown_input']='not accepted'
        self.assertEqual(self.gate().status,'BLOCK')
    def test_numeric_input_precision_is_not_silently_rounded(self):
        self.payload('product.travel')['rows'][0]['price']=2828.004
        self.assertEqual(self.gate().status,'BLOCK')
    def test_empty_kernel_snapshot_with_explicit_approval(self):
        p=self.app.create_project(dict(id='SYNTHETIC-BARE',name='Synthetic bare project',timezone='UTC'))
        self.assertEqual(self.app.validate_project(p).status,'PASS')
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(p)
        p.manifest['project'].update(status='APPROVED',approval_ref='SYNTHETIC-BARE-APPROVAL')
        record=self.app.create_snapshot(p);self.assertEqual(record['module_index'],{})

def load_tests(loader,tests,pattern):
    suite=unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(ModularTests))
    suite.addTests(loader.loadTestsFromTestCase(MigratedHistoricalTests))
    suite.addTests(AdditionalBoundaryTests(name) for name in AdditionalBoundaryTests.__dict__ if name.startswith('test_'))
    return suite
