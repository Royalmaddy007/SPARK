"""ModelSim admission tests: actual functional pass and deliberate mismatch."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import dataset2 as M


class AdmissionTests(unittest.TestCase):
    def test_transcript_requires_completion_and_no_failure(self):
        self.assertTrue(M.successful('TB_PASS\n$finish', 'TB_PASS'))
        for text in ('TB_PASS', 'TB_PASS\nTB_FAIL\n$finish', 'TB_PASS\n** Fatal: bad\n$finish',
                     'TB_PASS\nfailed\n$finish', '$finish'):
            self.assertFalse(M.successful(text, 'TB_PASS'))

    def test_parameterized_dut_has_real_interface(self):
        from great import vlog
        for header, body in [
            ("#(parameter W=8) (input clk, input [W-1:0] data, output ready)", ""),
            ("#(parameter W=(4+4)) (clk, data, ready)", "input clk; input [W-1:0] data; output ready;"),
        ]:
            module = vlog.parse_modules("module dut " + header + ";" + body + " endmodule")[0]
            self.assertEqual([p['name'] for p in module.ports], ['clk', 'data', 'ready'])
            self.assertEqual(module.ports[1]['width'], '[W-1:0]')
            self.assertTrue(vlog.header_parameter_declarations(module)[0].startswith('localparam W='))

    def test_qwen_thinking_mode_is_explicit_and_cache_isolated(self):
        import os
        from great import llm
        payloads = []
        def complete(payload):
            payloads.append(dict(payload))
            return {'response': '{"ok":true}', 'eval_count': 5}
        with tempfile.TemporaryDirectory() as tmp, patch.object(llm.C, 'CACHE_DIR', Path(tmp)), \
                patch.object(llm, '_post', side_effect=complete), patch.object(llm, '_log'):
            with patch.dict(os.environ, {'GREAT_LLM_THINK': '0'}):
                llm.generate('mode-isolation', model='qwen3.8:27b')
            with patch.dict(os.environ, {'GREAT_LLM_THINK': '1'}):
                llm.generate('mode-isolation', model='qwen3.8:27b')
                llm.generate('mode-isolation', model='qwen3.8:27b', think=False)
        self.assertEqual([p['think'] for p in payloads], [False, True])
        self.assertTrue(all(p['model'] == 'qwen3.8:27b' for p in payloads))

    def test_catalog(self):
        names = (M.ROOT/'requested_cores.txt').read_text().splitlines()
        self.assertEqual(len(names), 155)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[0], 'opb_wb_wrapper')
        self.assertEqual(names[-1], 'zpu')

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'Icarus required')
    def test_parameterized_phase5_bench_compiles_and_checks_outputs(self):
        spec = importlib.util.spec_from_file_location('dataset2_phase5', ROOT/'scripts/phase5_verify.py')
        phase5 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(phase5)
        source = ('module dut #(parameter W=8, parameter BASE=(W+1)) '
                  '(input clk, input [W-1:0] data, output [W-1:0] y); '
                  'assign y=data; endmodule')
        bench, meta = phase5.build_testbench(source, source, {}, [])
        self.assertEqual(meta['n_outputs'], 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'all.v').write_text(source + '\n' + phase5.alias_redacted(source, 'dut')[0] + '\n' + bench)
            M.D.command(['iverilog', '-g2005', '-s', 'tb_equiv', '-o', root/'sim', root/'all.v'])
            self.assertIn('EQUIV_PASS', M.D.command(['vvp', root/'sim']))

    @unittest.skipUnless(all(shutil.which(t) for t in ('vsim', 'vlog', 'vlib')), 'ModelSim required')
    def test_real_simulator_accepts_pass_and_rejects_mismatch(self):
        with tempfile.TemporaryDirectory(prefix='dataset2-test-', dir=ROOT/'datasets') as tmp:
            base = Path(tmp)
            dut = base/'dut.v'
            dut.write_text('module dut(input a, output y); assign y=~a; endmodule\n')
            tb = base/'tb.v'
            config = {'files': ['tb.v'], 'top': 'tb', 'pass_regex': 'TB_PASS'}
            row = {'top': 'dut', 'sha256': M.D.digest(dut)}
            with patch.object(M, 'ROOT', base):
                for expected, status in ((1, 'passed'), (0, 'test_blocked')):
                    tb.write_text('module tb; reg a; wire y; dut d(a,y); initial begin a=0; #1; '
                                  f'if(y!=={expected}) $display("TB_FAIL"); else $display("TB_PASS"); '
                                  '$finish; end endmodule\n')
                    result = M.simulate('fixture', dut, base, row, config, 20)
                    self.assertEqual(result['status'], status, result)


if __name__ == '__main__':
    unittest.main()
