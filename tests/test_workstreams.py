"""Regression checks for external measurement/attack boundaries and audit metadata."""
import gzip, json, os, subprocess, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import networkx as nx
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from great import config as C, llm, removal
from scripts.phase6d_dana_attack import cluster
from scripts.phase6c_sat_attack import classify
from scripts.report import evaluation_sections


class Workstreams(unittest.TestCase):
    def test_backend_cache_separation(self):
        args = ('prompt', 'system', .6, 33, 2048, None)
        self.assertNotEqual(llm._key(*args, backend='ollama', model='local'),
                            llm._key(*args, backend='api', model='external'))

    def test_api_dispatch(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                return json.dumps({'choices': [{'message': {'content': '{"signals":[]}'}}]}).encode()
        with tempfile.TemporaryDirectory() as td, patch.object(C, 'CACHE_DIR', Path(td)), patch.object(C, 'LLM_CACHE', False), patch.dict(os.environ, {'GREAT_CROSS_MODEL_API_URL': 'https://example.test/chat/completions', 'GREAT_CROSS_MODEL_API_KEY': 'test-key'}), patch('urllib.request.urlopen', return_value=Response()) as post:
            self.assertEqual(llm.generate('p', backend='api', model='different'), '{"signals":[]}')
            payload = json.loads(post.call_args.args[0].data)
            self.assertEqual(payload['model'], 'different')
            self.assertEqual(payload['messages'][0]['content'], 'p')

    def test_configuration_is_honest(self):
        with patch.dict(os.environ, {'GREAT_CROSS_MODEL': 'different', 'GREAT_CROSS_MODEL_API_KEY': 'k', 'GREAT_CROSS_MODEL_API_URL': 'https://example.test'}):
            self.assertEqual(C.ensemble_kind(C.effective_jurors()), 'cross_model_partial')
        self.assertEqual(C.ensemble_kind([{'model': 'same', 'backend': 'api'}, {'model': 'same', 'backend': 'ollama'}]), 'single_model_multi_persona')

    def test_scan_clustering_stops_at_registers(self):
        g = nx.MultiDiGraph()
        g.add_nodes_from((n, {'kind': 'cell'}) for n in ('a','b','c','gate'))
        g.add_edges_from([('a','gate'), ('gate','b')])
        g.graph['seq_cells'] = {'a','b','c'}
        self.assertEqual(cluster(g), [2, 1])

    def test_sat_does_not_claim_unverified_keys(self):
        self.assertEqual(classify('key=01\n', 0, 2)[0], 'candidate_key_unverified')
        self.assertEqual(classify('Average Hamming distance: 0 %\nkey=01\n', 0, 2), ('SAT', '01'))
        self.assertNotEqual(classify('Average Hamming distance: 0 %\nkey=01\n', 1, 2)[0], 'SAT')
        self.assertEqual(classify('I/O mismatch', 1, 2)[0], 'io_mismatch')
        self.assertNotEqual(classify('UNSAT model!\nkey=xx\n', 0, 2)[0], 'SAT')

    def test_removal_uses_masked_value_not_truth(self):
        rtl = "module m(input a,output y); wire [7:0] foo_v = a; wire foo_m = foo_v; wire foo_dbg = foo_m; assign y = ((8'h15 - 8'h02) ^ 8'h03); endmodule"
        mf = {'decoy_manifest': [{'signal': 'foo_m', 'sinks': ['foo_dbg']}],
              'masked_constants': [{'width':8, 'masked':21, 'add':2, 'xor':3}]}
        stripped, edits = removal.strip(rtl, mf)
        self.assertNotIn('foo_m', stripped)
        self.assertIn("8'h15", stripped)
        self.assertEqual(edits['mask_reconstructions_replaced'], 1)
        self.assertEqual(len(edits['removed_signals']), 3)

    def test_compressed_phase0_cache(self):
        from great.netlist import load_mapped_json
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'design.mapped.json'
            with gzip.open(str(path) + '.gz', 'wt') as stream:
                json.dump({'modules': {'top': {}}}, stream)
            self.assertEqual(load_mapped_json(path), {'modules': {'top': {}}})

    def test_merge_keeps_templates_from_every_group(self):
        from scripts import setup_asap7
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / 'a.lib').write_text('library(a) {cell(A) {area:1;}}')
            (td / 'b.lib').write_text('library(b) {lu_table_template(t) {variable_1:input_net_transition;} cell(B) {area:2;}}')
            with patch.object(setup_asap7, 'MERGED', td / 'combined.lib'):
                self.assertEqual(setup_asap7._merge(td), 2)
            self.assertIn('lu_table_template(t)', (td / 'combined.lib').read_text())

    @unittest.skipUnless((C.ROOT / 'tools/PSAT/bin/sld').exists(), 'PSAT not installed')
    def test_external_psat_recovers_known_key(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            inputs = ''.join(f'INPUT(a{i})\n' for i in range(8))
            outputs = ''.join(f'OUTPUT(y{i})\n' for i in range(8))
            locked, golden = td / 'locked.bench', td / 'golden.bench'
            locked.write_text(inputs + 'INPUT(keyinput0)\n' + outputs + ''.join(f'y{i} = XOR(a{i}, keyinput0)\n' for i in range(8)))
            golden.write_text(inputs + outputs + ''.join(f'y{i} = NOT(a{i})\n' for i in range(8)))
            Path(str(locked) + '.stoch').write_text('# OUTPUT_SAMPLING_ON OUTPUT_SAMPLING_ITERATIONS OUTPUT_SAMPLING_FOR_TEST_ON TEST_PATTERNS\nfalse 1 false 10000\nNEXT_GATE\n')
            result = subprocess.run([str(C.ROOT / 'tools/PSAT/bin/sld'), str(locked), str(golden)],
                                    capture_output=True, text=True, timeout=15,
                                    env=dict(os.environ, OMP_NUM_THREADS='1'))
            self.assertEqual(classify(result.stdout + result.stderr, result.returncode, 1), ('SAT', '1'))

    def test_missing_measurements_not_zero(self):
        md = '\n'.join(evaluation_sections({'test': {}}))
        self.assertIn('not measured', md)
        self.assertNotIn('0.0%', md)
        self.assertIn('not the hal plugin', md)

if __name__ == '__main__':
    unittest.main()
