import unittest
import tempfile
from copy import deepcopy
from sports_os.application import ApplicationService
from sports_os_legacy.models.demo import make_demo
from sports_os.kernel import Module, ModuleState
from sports_os.kernel.data import KernelError, canonical
from sports_os.kernel.snapshot import ReleaseBlocked

class HardeningTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.app=ApplicationService(t.name);self.p=self.app.migrate_v10(make_demo())
    def edit(self):
        return self.app.apply_changeset(self.p,'ticketing.pricing',[dict(path=['rows',0,'price'],value=731)])
    def reapprove(self,p,key='ticketing.pricing'):
        p=self.app.approve_module(p,key,'SYNTHETIC-NEW-MODULE',p.states[key].data_version)
        return self.app.approve_project(p,'SYNTHETIC-NEW-PROJECT',p.manifest['project']['version'])
    def gate(self,p):return self.app.validate_project(p).status
    def test_HARD_001(self):
        """HARD-001 | 已批准票价改为731 | 模块/项目DRAFT且新版本、清批准"""
        p=self.edit();s=p.states['ticketing.pricing'];m=p.manifest['project']
        self.assertEqual((s.status,s.approval_ref,m['status'],m['approval_ref']),('DRAFT',None,'DRAFT',''))
        self.assertNotEqual(s.data_version,self.p.states['ticketing.pricing'].data_version)
        self.assertNotEqual(m['version'],self.p.manifest['project']['version'])
        self.assertEqual(self.p.states['ticketing.pricing'].payload['rows'][0]['price'],730)
        self.assertEqual(self.gate(p),'PASS')
    def test_HARD_002(self):
        """HARD-002 | 相同payload | 版本/批准保持"""
        p=self.app.update_module_data(self.p,'ticketing.pricing',self.app.get_module_data(self.p,'ticketing.pricing'))
        self.assertEqual(p.to_dict(),self.p.to_dict())
    def test_HARD_003(self):
        """HARD-003 | edit后snapshot | BLOCK"""
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(self.edit())
    def test_HARD_004(self):
        """HARD-004 | edit后显式人工重新批准 | snapshot成功"""
        self.assertTrue(self.app.create_snapshot(self.reapprove(self.edit()))['snapshot_id'])
    def test_HARD_005(self):
        """HARD-005 | 旧snapshot后编辑并再批准 | 旧snapshot不变"""
        old=self.app.create_snapshot(self.p);before=canonical(old)
        self.app.create_snapshot(self.reapprove(self.edit()))
        records=self.app.list_snapshots(self.p.manifest['project']['id'])
        self.assertIn(before,[canonical(r) for r in records])

    def custom_prices(self):
        prices=self.app.calculate_module(self.p,'ticketing.pricing')
        class CustomPrices(Module):
            module_id='custom.pricing';provides=('prices',)
            def schema(self):return {'type':'object','additionalProperties':False}
            def calculate(self,c):return prices
        m=CustomPrices();self.app.registry.register(m)
        return m
    def test_HARD_006(self):
        """HARD-006 | Revenue仅缺schedule，其他capabilities存在 | BLOCK"""
        from sports_os.kernel import Registry
        from sports_os.modules.revenue import Revenue
        registry=Registry();registry.register(Revenue())
        class Stub(Module):
            module_id='custom.all_except_schedule';provides=('prices','capacity','demand')
        registry.register(Stub())
        with self.assertRaisesRegex(KernelError,'schedule'):registry.order(['finance.revenue',Stub.module_id])
    def test_HARD_007(self):
        """HARD-007 | 自定义prices替代官方Pricing | Revenue相同"""
        expected=self.app.calculate_module(self.p,'finance.revenue')
        m=self.custom_prices();p=self.app.replace_module(self.p,'ticketing.pricing',m.module_id,{})
        self.assertEqual(self.app.calculate_module(p,'finance.revenue'),expected)
    def test_HARD_008(self):
        """HARD-008 | 两个prices提供者 | BLOCK"""
        m=self.custom_prices();p=deepcopy(self.p);p.manifest['modules'][m.module_id]=True
        p.states[m.module_id]=ModuleState(m.module_version,m.schema_version,{})
        self.assertEqual(self.gate(p),'BLOCK')

    def multi_venue(self):
        p=deepcopy(self.p)
        p.states['core.venue'].payload['rows']=[dict(venue_id='SYNTHETIC-'+x,name='Synthetic '+x,timezone='UTC') for x in ('A','B','C')]
        for i,row in enumerate(p.states['core.schedule'].payload['rows']):row['venue_id']='SYNTHETIC-'+('ABC'[i%3])
        return p
    def test_HARD_009(self):
        """HARD-009 | 多session关联三个虚构场馆 | PASS"""
        self.assertEqual(self.gate(self.multi_venue()),'PASS')
    def test_HARD_010(self):
        """HARD-010 | session引用不存在的venue | BLOCK"""
        p=self.multi_venue();p.states['core.schedule'].payload['rows'][0]['venue_id']='MISSING'
        self.assertEqual(self.gate(p),'BLOCK')
    def test_HARD_011(self):
        """HARD-011 | 禁用Venue且没有venue_id | PASS"""
        self.assertEqual(self.gate(self.app.disable_module(self.p,'core.venue')),'PASS')

    def rights_result(self,basis,fulfillment=.8):
        p=self.app.disable_module(self.p,'ticketing.inventory')
        rows=p.states['ticketing.rights'].payload['rows']
        r=rows[0];r.update(quantity=100,strategy='FIXED_PRICE',value=300,billing_basis=basis,
                         expected_fulfillment={n:fulfillment for n in ('low','mid','high')})
        for row in rows[1:]:row['quantity']=0
        return self.app.calculate_module(p,'finance.revenue')['totals']['scenarios']['mid']
    def test_HARD_012(self):
        """HARD-012 | 100权益×300，fulfillment=.8，ALLOCATED | 收入30000/履约80"""
        r=self.rights_result('ALLOCATED');self.assertEqual(r['rights_revenue'],30000)
        self.assertEqual(r['rights_expected_fulfilled'],80);self.assertEqual(r['rights_revenue_tickets'],100)
    def test_HARD_013(self):
        """HARD-013 | 相同权益，REDEEMED | 收入24000/履约80"""
        r=self.rights_result('REDEEMED');self.assertEqual(r['rights_revenue'],24000)
        self.assertEqual(r['rights_expected_fulfilled'],80);self.assertEqual(r['rights_revenue_tickets'],80)
    def test_HARD_014(self):
        """HARD-014 | 只改billing_basis | Public收入/票张不变"""
        a,b=self.rights_result('ALLOCATED'),self.rights_result('REDEEMED')
        self.assertEqual(a['public_revenue'],b['public_revenue'])
        self.assertEqual(a['public_expected_tickets'],b['public_expected_tickets'])

    def refund_pair(self,overlap=False):
        p=deepcopy(self.p);rows=p.states['ticketing.refund'].payload['rows'];r=rows[0]
        r['scope']={'type':'SESSION','session_ids':['S01','S02']}
        other=deepcopy(r);other['rule_id']='SYNTHETIC-REFUND-B'
        other['scope']={'type':'SESSION','session_ids':['S02','S03'] if overlap else ['S03','S04']}
        rows.append(other);return p
    def test_HARD_015(self):
        """HARD-015 | 一个Refund ALL | PASS"""
        self.assertEqual(self.gate(self.p),'PASS')
    def test_HARD_016(self):
        """HARD-016 | 两个Refund，Session集合不相交 | PASS"""
        self.assertEqual(self.gate(self.refund_pair()),'PASS')
    def test_HARD_017(self):
        """HARD-017 | 两个Refund共享Session且有效期重叠 | BLOCK"""
        self.assertEqual(self.gate(self.refund_pair(True)),'BLOCK')
    def test_HARD_018(self):
        """HARD-018 | Scope引用不存在Session | BLOCK"""
        p=self.refund_pair();p.states['ticketing.refund'].payload['rows'][0]['scope']['session_ids']=['NOT-A-SESSION']
        self.assertEqual(self.gate(p),'BLOCK')

    def test_service_copy_atomic_revision(self):
        """边界 | 返回payload副本、无效patch | 原对象不变，版本-r1/-r2"""
        copy=self.app.get_module_data(self.p,'ticketing.pricing');copy['rows'][0]['price']=1
        self.assertEqual(self.p.states['ticketing.pricing'].payload['rows'][0]['price'],730)
        p=self.edit();p=self.app.apply_changeset(p,'ticketing.pricing',[dict(path=['rows',0,'price'],value=732)])
        self.assertTrue(p.states['ticketing.pricing'].data_version.endswith('-r2'))
        before=canonical(p.to_dict())
        for path in (['rows',-1],['rows',True],['missing'],['rows',0,'price','bad']):
            with self.assertRaises(KernelError):self.app.apply_changeset(p,'ticketing.pricing',[dict(path=path,value=0)])
        self.assertEqual(before,canonical(p.to_dict()))
    def test_approval_stale_and_empty(self):
        """边界 | 空批准引用/旧版本批准 | BLOCK"""
        p=self.edit()
        for ref,version in [(' ',p.states['ticketing.pricing'].data_version),('SYNTHETIC','old')]:
            with self.assertRaises(KernelError):self.app.approve_module(p,'ticketing.pricing',ref,version)
        with self.assertRaises(KernelError):self.app.approve_project(p,'SYNTHETIC','old')
    def test_import_cannot_transfer_approval(self):
        """边界 | 从JSON导入已修改且声称APPROVED数据 | DRAFT/发布BLOCK"""
        raw=self.p.to_dict();raw['modules']['ticketing.pricing']['payload']['rows'][0]['price']=731
        p=self.app.import_project(raw)
        self.assertEqual(p.states['ticketing.pricing'].status,'DRAFT')
        self.assertEqual(self.gate(p),'PASS')
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(p)
    def test_existing_enable_uses_revision_lifecycle(self):
        """边界 | 对已存在模块enable时替换payload | 新revision/DRAFT"""
        data=self.app.get_module_data(self.p,'ticketing.pricing');data['rows'][0]['price']=731
        p=self.app.enable_module(self.p,'ticketing.pricing',data)
        self.assertEqual(p.states['ticketing.pricing'].data_version,self.p.states['ticketing.pricing'].data_version+'-r1')
        self.assertEqual(p.states['ticketing.pricing'].status,'DRAFT')
        self.assertEqual(self.app.enable_module(self.p,'ticketing.pricing').to_dict(),self.p.to_dict())
    def test_cli_edit_and_manual_approval(self):
        """CLI | patch→snapshot BLOCK→approve-module→approve-project→snapshot | PASS"""
        import json
        import subprocess
        import sys
        from pathlib import Path
        self.app.save_project(self.p)
        path=Path(self.app.root)/'patch.json';path.write_text(json.dumps([dict(path=['rows',0,'price'],value=731)]))
        def run(*args):return subprocess.run([sys.executable,'-m','sports_os',*args,'--workspace',str(self.app.root)],text=True,capture_output=True)
        r=run('patch','ticketing.pricing','patch.json');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertEqual(run('snapshot').returncode,1)  # 1 = blocked by the gate (v1.2 exit codes)
        p=self.app.open_project()
        r=run('approve-module','ticketing.pricing','--approval-ref','SYNTHETIC-CLI-MODULE','--version',p.states['ticketing.pricing'].data_version)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        r=run('approve-project','--approval-ref','SYNTHETIC-CLI-PROJECT','--version',p.manifest['project']['version'])
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        r=run('snapshot');self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_explicit_v11_working_migration(self):
        """兼容 | 原v1.1工作态 | 升级前BLOCK、显式迁移后DRAFT/PASS"""
        from pathlib import Path
        from sports_os.kernel import Project
        from sports_os.kernel.data import load_json
        raw=load_json(Path(__file__).parents[1]/'data/modular_demo/version_a.json')
        old=Project.from_dict(raw);before=canonical(old.to_dict())
        self.assertEqual(self.gate(old),'BLOCK')
        new=self.app.migrate_project(old)
        self.assertEqual(self.gate(new),'PASS');self.assertEqual(canonical(old.to_dict()),before)
        self.assertEqual(new.states['ticketing.rights'].payload['rows'][0]['billing_basis'],'REDEEMED')
        self.assertEqual(new.states['ticketing.refund'].payload['rows'][0]['scope'],{'type':'ALL'})
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(new)
        for key in new.enabled:
            if new.states[key].status=='DRAFT':new=self.app.approve_module(new,key,'SYNTHETIC-MIGRATION-'+key,new.states[key].data_version)
        new=self.app.approve_project(new,'SYNTHETIC-MIGRATION-PROJECT',new.manifest['project']['version'])
        self.assertTrue(self.app.create_snapshot(new)['snapshot_id'])
        self.assertEqual(new.to_dict(),self.app.migrate_project(new).to_dict())
    def test_old_snapshot_preserved_and_not_reinterpreted(self):
        """兼容 | 仓库原v1.1发布件 | hash仍有效、新模块拒绝静默重解释"""
        from pathlib import Path
        from sports_os.kernel.snapshot import verify_snapshot
        from sports_os.kernel.data import load_json
        path=Path(__file__).parents[1]/'outputs/releases/SN11-646bf98adf7253f45bcebe3a/snapshot.json'
        before=path.read_bytes();record=load_json(path);verify_snapshot(record)
        with self.assertRaises(ReleaseBlocked):self.app.export_artifact(record)
        self.assertEqual(path.read_bytes(),before)
    def test_cli_explicit_project_migration(self):
        """兼容CLI | 旧工作库执行migrate-project | 成功且重新批准前发布BLOCK"""
        import subprocess
        import sys
        from pathlib import Path
        from sports_os.kernel import Project
        from sports_os.kernel.data import load_json
        from sports_os.application.manifest import render_manifest
        old=Project.from_dict(load_json(Path(__file__).parents[1]/'data/modular_demo/version_a.json'))
        self.app.store.save(old);self.app.write_artifact('project.toml',render_manifest(old.manifest))
        result=subprocess.run([sys.executable,'-m','sports_os','migrate-project','--workspace',str(self.app.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(self.gate(self.app.open_project()),'PASS')
        self.assertEqual(self.app.validate_project(self.app.open_project(),True).status,'BLOCK')
    def test_HARD_019(self):
        """HARD-019 | edit后仅手工把项目改APPROVED，模块DRAFT | 发布BLOCK"""
        p=self.edit();p.manifest['project'].update(status='APPROVED',approval_ref='SYNTHETIC-ONLY-PROJECT')
        self.assertEqual(self.app.validate_project(p,True).status,'BLOCK')
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(p)
    def test_HARD_020(self):
        """HARD-020 | edit后仅调用approve_project，不批准模块 | BLOCK"""
        p=self.edit()
        with self.assertRaises(KernelError):self.app.approve_project(p,'SYNTHETIC-ONLY-PROJECT',p.manifest['project']['version'])
        self.assertEqual(p.manifest['project']['status'],'DRAFT')
    def test_HARD_021(self):
        """HARD-021 | 删除多个venue中仍被引用的一个 | BLOCK"""
        p=self.multi_venue();data=self.app.get_module_data(p,'core.venue');data['rows'].pop()
        p=self.app.update_module_data(p,'core.venue',data)
        self.assertEqual(self.gate(p),'BLOCK')
    def test_HARD_022(self):
        """HARD-022 | ALLOCATED权益履约率0 | 收入30000/履约0"""
        r=self.rights_result('ALLOCATED',0)
        self.assertEqual(r['rights_revenue'],30000);self.assertEqual(r['rights_expected_fulfilled'],0)
    def test_HARD_023(self):
        """HARD-023 | REDEEMED权益履约率0 | 收入0/履约0"""
        r=self.rights_result('REDEEMED',0)
        self.assertEqual(r['rights_revenue'],0);self.assertEqual(r['rights_expected_fulfilled'],0)
    def test_HARD_024(self):
        """HARD-024 | 不同Scope共享S02但有效时间仅边界相接 | PASS"""
        p=self.refund_pair(True);a,b=p.states['ticketing.refund'].payload['rows']
        boundary='2027-06-01T00:00:00+00:00';a['valid_to']=boundary;b['valid_from']=boundary
        for r in (a,b):
            r['content']=dict(coverage_start=r['valid_from'],coverage_end=r['valid_to'],
                              windows=[dict(start=r['valid_from'],end=r['valid_to'],fee_rate=0)])
        self.assertEqual(self.gate(p),'PASS')
    def test_schedule_provider_and_tasks(self):
        """Provider边界 | 替换Schedule，Tasks仍校验赛前时序 | 计算不变/坏任务BLOCK"""
        from sports_os.modules.schedule import Schedule
        class CustomSchedule(Schedule):module_id='custom.schedule'
        self.app.registry.register(CustomSchedule())
        expected=self.app.calculate_module(self.p,'finance.revenue')
        p=self.app.replace_module(self.p,'core.schedule','custom.schedule',self.app.get_module_data(self.p,'core.schedule'))
        self.assertEqual(self.app.calculate_module(p,'finance.revenue'),expected)
        rows=p.states['project.tasks'].payload['rows'];rows[0].update(phase='PRE_EVENT',due_at='2027-12-31T00:00:00+00:00')
        self.assertEqual(self.gate(p),'BLOCK')
    def test_rights_provider_and_inventory(self):
        """Provider边界 | 替换Rights | Revenue及Inventory使用能力、不依赖官方ID"""
        from sports_os.modules.rights import Rights
        class CustomRights(Rights):module_id='custom.rights'
        self.app.registry.register(CustomRights())
        expected=self.app.calculate_module(self.p,'finance.revenue')
        p=self.app.replace_module(self.p,'ticketing.rights','custom.rights',self.app.get_module_data(self.p,'ticketing.rights'))
        self.assertEqual(self.app.calculate_module(p,'finance.revenue'),expected)
        p.states['custom.rights'].payload['rows'][0]['quantity']+=1
        self.assertEqual(self.gate(p),'BLOCK')
    def test_rule_scope_contracts(self):
        """Scope边界 | 所有规则支持SESSION；ALL/SESSION重叠、重复ID、无scope | BLOCK"""
        for key in ('refund','identity','transfer','rights_return','launch'):
            p=deepcopy(self.p);r=p.states['ticketing.'+key].payload['rows'][0]
            r['scope']={'type':'SESSION','session_ids':['S01','S02']}
            self.assertEqual(self.gate(p),'PASS',key)
            for scope in ({'type':'SESSION','session_ids':[]},{'type':'SESSION','session_ids':['S01','S01']},{'type':'ALL','session_ids':['S01']}):
                r['scope']=scope;self.assertEqual(self.gate(p),'BLOCK',key)
        p=self.refund_pair();p.states['ticketing.refund'].payload['rows'][0]['scope']={'type':'ALL'}
        self.assertEqual(self.gate(p),'BLOCK')
        p=self.refund_pair();rows=p.states['ticketing.refund'].payload['rows'];rows[1]['rule_id']=rows[0]['rule_id']
        self.assertEqual(self.gate(p),'BLOCK')
    def test_scoped_identity_temporal_coverage(self):
        """Scope边界 | Identity两段相接覆盖销售至场次结束 | PASS；留空档BLOCK"""
        p=deepcopy(self.p);rows=p.states['ticketing.identity'].payload['rows'];a=rows[0];b=deepcopy(a)
        b['rule_id']='SYNTHETIC-IDENTITY-SECOND';a['valid_to']=b['valid_from']='2027-06-01T00:00:00+00:00';rows.append(b)
        self.assertEqual(self.gate(p),'PASS')
        b['valid_from']='2027-06-02T00:00:00+00:00';self.assertEqual(self.gate(p),'BLOCK')
        p=deepcopy(self.p);p.manifest['modules']={'core.schedule':True,'ticketing.identity':True}
        schedule=p.states['core.schedule'].payload
        schedule['sales_start']=schedule['rows'][1]['end_time']
        self.assertEqual(self.gate(p),'BLOCK')
    def test_rights_schema_and_provider_basis_required(self):
        """Rights边界 | 缺失/未知billing_basis | BLOCK而非静默默认"""
        for value in ('UNKNOWN',None):
            p=deepcopy(self.p);p.states['ticketing.rights'].payload['rows'][0]['billing_basis']=value
            self.assertEqual(self.gate(p),'BLOCK')
        p=deepcopy(self.p);del p.states['ticketing.rights'].payload['rows'][0]['billing_basis']
        self.assertEqual(self.gate(p),'BLOCK')

    def test_external_manifest_change_is_not_approval(self):
        """写边界 | 手改TOML禁用模块并保留批准 | open后DRAFT/新revision"""
        from sports_os.application.manifest import render_manifest
        self.app.save_project(self.p)
        manifest=deepcopy(self.p.manifest);manifest['modules']['product.travel']=False
        self.app.write_artifact('project.toml',render_manifest(manifest))
        p=self.app.open_project();self.assertEqual(p.manifest['project']['status'],'DRAFT')
        self.assertNotEqual(p.manifest['project']['version'],self.p.manifest['project']['version'])
        with self.assertRaises(ReleaseBlocked):self.app.create_snapshot(p)
    def test_replace_with_already_enabled_invalidates(self):
        """写边界 | replace为已启用模块、payload不变但配置改变 | 项目DRAFT"""
        p=self.app.replace_module(self.p,'product.travel','product.pass',self.app.get_module_data(self.p,'product.pass'))
        self.assertEqual(p.manifest['project']['status'],'DRAFT')
        self.assertFalse(p.manifest['modules']['product.travel'])
    def test_patch_malformed_is_atomic(self):
        """写边界 | 非数组/非对象changeset | KernelError且无写入"""
        before=self.p.to_dict()
        for value in ({},[1],['x']):
            with self.assertRaises(KernelError):self.app.apply_changeset(self.p,'ticketing.pricing',value)
        self.assertEqual(before,self.p.to_dict())
