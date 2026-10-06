"""Reproducible test report; no invented PASS rows."""
import io
import json
import sys
import unittest
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tests.cases import regression_results

class RecordingResult(unittest.TextTestResult):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw);self.records=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.records.append(dict(test=test.id(),input=test.shortDescription() or test._testMethodName,expected='所有断言成立',actual='无断言失败',result='PASS'))
    def addFailure(self,test,err):
        super().addFailure(test,err);self.records.append(dict(test=test.id(),input=test.shortDescription() or test._testMethodName,expected='所有断言成立',actual=self._exc_info_to_string(err,test),result='FAIL'))
    def addError(self,test,err):
        super().addError(test,err);self.records.append(dict(test=test.id(),input=test.shortDescription() or test._testMethodName,expected='无异常',actual=self._exc_info_to_string(err,test),result='FAIL'))
    def addSkip(self,test,reason):
        super().addSkip(test,reason);self.records.append(dict(test=test.id(),input=test._testMethodName,expected='执行测试',actual='SKIP: '+reason,result='FAIL'))

def main():
    stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordingResult).run(suite)
    regressions=regression_results();ok=result.wasSuccessful() and not result.skipped and all(r['result']=='PASS' for r in regressions)
    out=ROOT/'outputs';out.mkdir(exist_ok=True)
    (out/'S7_TEST.log').write_text(stream.getvalue(),encoding='utf-8')
    report=dict(status='PASS' if ok else 'FAIL',created_at=datetime.now(timezone.utc).isoformat(),python=sys.version,
                tests_run=result.testsRun,regressions=regressions,tests=result.records)
    (out/'acceptance-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def cell(s):return str(s).replace('|','／').replace('\n',' ')
    lines=['# TEST_REPORT', '', f"验收：**{report['status']}**。实际执行 {result.testsRun} 项测试；{len(result.failures)} FAIL，{len(result.errors)} ERROR，{len(result.skipped)} SKIP。",'',
           f"运行时间：{report['created_at']}；Python {sys.version.split()[0]}。",'',
           '## 指定历史错误的10个合成回归', '', '|测试项|输入|预期|实际|PASS/FAIL|','|---|---|---|---|---|']
    for r in regressions:
        lines.append('|'+ '|'.join(cell(x) for x in [r['id'],r['input'],r['expected']+' / '+r['rule'],r['actual']+' / '+','.join(r['actual_rules']),r['result']])+'|')
    lines+=['','## 全部自动测试（实际运行记录）','','|测试项|输入／操作|预期|实际|PASS/FAIL|','|---|---|---|---|---|']
    for r in result.records:lines.append('|'+ '|'.join(cell(r[k]) for k in ['test','input','expected','actual','result'])+'|')
    lines+=['','## 阶段门禁','', '|阶段|实际执行数|结果|','|---|---:|---|']
    import re
    for stage in range(8):
        p=out/f'S{stage}_TEST.log'
        if p.exists():
            log=p.read_text();found=re.search(r'Ran (\d+) tests?',log)
            lines.append(f"|S{stage}|{found.group(1) if found else '见日志'}|{'PASS' if log.rstrip().endswith('OK') else 'FAIL'}|")
    lines+=['','## 验证范围与已修复问题','',
        '- 测试均为合成数据；没有读取公司原文件、U盘正文或真实票务平台。',
        '- 输入单价／座席变化、阶段和票档汇总、付费权益及产品映射均有可复算断言。',
        '- CLI通过子进程执行，不以直接调用函数代替命令行验收。',
        '- S6曾发现快照读回后的JSON键顺序导致幂等导出误判；统一序列化后重新运行S6全部通过，才进入S7。',
        '- Excel为限定公式引擎，不声称验证任意工作簿；未知函数会BLOCK。',
        '- 审批证据真实性、真实需求、平台并发和现场安全不在本原型可验证范围。',
        '- 重跑：python tests/run_acceptance.py。退出码非0或存在SKIP，不算完整验收通过。']
    (ROOT/'TEST_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(report['status'],result.testsRun,'tests; details: TEST_REPORT.md')
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
