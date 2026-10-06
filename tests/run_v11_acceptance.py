"""Produce an actual v1.1 acceptance report without overwriting the frozen v1.0 report."""
import io
import json
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.run_acceptance import RecordingResult

def main():
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordingResult).run(suite)
    old=[r for r in result.records if any(f'.test_s{i}.' in r['test'] for i in range(8))]
    new=[r for r in result.records if r not in old]
    passed=lambda rows:sum(r['result']=='PASS' for r in rows)
    ok=result.wasSuccessful() and not result.skipped and len(old)==72
    report=dict(verdict='PASS' if ok else 'FAIL',created_at=datetime.now(timezone.utc).isoformat(),
        python=sys.version.split()[0],old_count=len(old),old_pass=passed(old),new_count=len(new),new_pass=passed(new),
        tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),tests=result.records)
    out=ROOT/'outputs/v1_1';out.mkdir(exist_ok=True,parents=True)
    (out/'acceptance-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    log=stream.getvalue().replace(str(ROOT),'<PROJECT>')
    (out/'ALL_TESTS.log').write_text(log,encoding='utf-8')
    def cell(v):return str(v).replace('|','／').replace('\n',' ')
    lines=['# V1_1_TEST_REPORT','',f"v1.1 verdict: **{report['verdict']}**",'',
        f"旧测试：{len(old)} / 通过 {passed(old)}；新增：{len(new)} / 通过 {passed(new)}。",'',
        f"实际执行 {result.testsRun} 项；FAIL {len(result.failures)}；ERROR {len(result.errors)}；SKIP {len(result.skipped)}。",'',
        f"时间：{report['created_at']}；Python {report['python']}。",'',
        '## 基线与迁移说明','',
        '- S0源代码未修改前：72/72通过；见V1_0_BASELINE.md和S0_BASELINE.log。',
        '- 保留原72项测试。test_s1分组汇总断言改为revenue_exact：分组显示金额相加可出现分币尾差，不能要求显示取整值反向闭合。',
        '- 原5项CLI测试显式追加--legacy，验证v1适配器；新增独立CLI测试验证默认v1.1 ApplicationService。',
        '- 10项历史错误另外通过显式迁移进入模块门禁再次执行，不仅验证兼容代码。',
        '- S1修复后78/78；模块主验收32/32；本表为最终完整重跑结果。',
        '- MOD-001～MOD-016均是实际测试方法，不是文档声明。外部插件测试使用临时独立distribution的entry_points元数据，没有改Kernel。','',
        '## 实际测试明细','', '|测试项|输入／操作|预期|实际|PASS/FAIL|','|---|---|---|---|---|']
    for r in result.records:lines.append('|'+ '|'.join(cell(r[k]) for k in ('test','input','expected','actual','result'))+'|')
    lines+=['','## 验收边界','',
        '完全合成离线数据；不证明真实审批、商业需求、现场容量安全或生产可用性。模块/插件为可信本地Python代码，不提供沙箱。',
        '复现：`python tests/run_v11_acceptance.py`。退出码非0、旧测试不足72项或有SKIP均不算PASS。']
    (ROOT/'V1_1_TEST_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(report['verdict'],result.testsRun,'tests;',len(old),'old;',len(new),'new')
    return 0 if ok else 1
if __name__=='__main__':raise SystemExit(main())
