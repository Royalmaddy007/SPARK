import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('dataset', Path(__file__).resolve().parents[1] / 'scripts/dataset.py')
D = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(D)


class DatasetTests(unittest.TestCase):
    def test_filter_archives_non_verilog_and_preserves_requested_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); data = root / 'data'; data.mkdir()
            requested = 'native\nvhdl\nsv\nmixed\n'
            (data / 'cores.txt').write_text(requested)
            for core in ('native', 'vhdl', 'sv', 'mixed'):
                folder = data / 'sources' / core; folder.mkdir(parents=True)
                D.write(folder / '.spark-provenance.json', {'revision': '1'})
                if core in {'native', 'mixed'}: (folder / 'top.v').write_text('module top; endmodule')
                if core in {'vhdl', 'mixed'}: (folder / 'entity.vhd').write_text('entity other is end; architecture a of other is begin end;')
                if core == 'sv': (folder / 'top.sv').write_text('module top; endmodule')
            old = data / 'redacted/vhdl/old.redacted.v'; old.parent.mkdir(parents=True); old.write_text('converted VHDL')
            args = SimpleNamespace(root=data, core=None, overrides=data / 'overrides.json', prepare_timeout=10)
            with patch.object(D, 'ROOT', root):
                result = D.filter_verilog(args)
                self.assertEqual(result['active'], ['native'])
                self.assertEqual((data / 'cores.txt').read_text(), 'native\n')
                self.assertEqual((data / 'requested_cores.txt').read_text(), requested)
                self.assertFalse((data / 'sources/vhdl').exists())
                self.assertTrue((data / 'excluded/sources/vhdl/entity.vhd').exists())
                self.assertTrue((data / 'excluded/redacted/vhdl/old.redacted.v').exists())
                self.assertEqual(D.filter_verilog(args)['active'], ['native'])

    @unittest.skipUnless(D.shutil.which('iverilog') and D.shutil.which('yosys') and D.shutil.which('vvp'), 'EDA tools required')
    def test_real_multifile_merge_is_standalone_and_functionally_matches_original(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); data = root / 'data'; data.mkdir()
            (data / 'cores.txt').write_text('sample\n')
            source = data / 'sources/sample'; source.mkdir(parents=True)
            (source / 'defs.vh').write_text('`define WIDTH 4\n')
            (source / 'leaf.v').write_text('`include "defs.vh"\nmodule leaf(input [`WIDTH-1:0] a,output [`WIDTH-1:0] y); assign y=~a; endmodule\n')
            (source / 'sample.v').write_text('`include "leaf.v"\nmodule sample(input [3:0] a,output [3:0] y);leaf u(a,y);endmodule\n')
            D.write(source / '.spark-provenance.json', {'revision': '1'})
            args = SimpleNamespace(root=data, prepare_timeout=20, core=None)
            with patch.object(D, 'ROOT', root):
                prepared = D.prepare_one('sample', args, {})
                self.assertEqual(prepared['status'], 'ready', prepared)
                D.write(data / 'prepare_index.json', {'cores': {'sample': prepared}})
                self.assertEqual(len(D.check_inputs(args)), 1)
            merged = root / prepared['input']
            self.assertEqual(merged, data / 'rtl/sample.v')
            self.assertEqual([m.name for m in D.vlog.parse_modules(merged.read_text())], ['sample', 'leaf'])
            self.assertEqual(list((data / 'rtl').glob('*.v')), [merged])
            tb = root / 'tb.v'
            tb.write_text('module tb;reg[3:0]a;wire[3:0]y;integer i;sample d(a,y);initial begin for(i=0;i<16;i=i+1)begin a=i;#1;if(y!==~a)$fatal(1,"mismatch");end $display("PASS");$finish;end endmodule')
            for name, files in [('original', [source / 'sample.v']), ('merged', [merged])]:
                exe = root / (name + '.out')
                D.command(['iverilog', '-g2012', '-s', 'tb', '-I', source, '-o', exe, *files, tb])
                self.assertIn('PASS', D.command(['vvp', exe]))

    def test_manifest_contains_149_unique_requested_projects(self):
        args = SimpleNamespace(root=D.DEFAULT, core=None)
        requested = D.DEFAULT / 'requested_cores.txt'
        names = requested.read_text().split() if requested.exists() else D.cores(args)
        self.assertEqual(len(names), 149)
        self.assertEqual(len(set(names)), 149)
        self.assertEqual(names[0], '16x2_lcd_controller')
        self.assertEqual(names[-1], 'opb_vga_char_display_nodac')

    def test_ambiguous_tops_require_configuration(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'cores.v'
            p.write_text('module a(input x, output y); assign y=x; endmodule\nmodule b(input x, output y); assign y=x; endmodule')
            with self.assertRaisesRegex(ValueError, 'possible tops'):
                D.choose_top([p], {})
            self.assertEqual(D.choose_top([p], {'top': 'b'})[0], 'b')
            text = D.top_first(p.read_text(), 'b')
            self.assertEqual(D.vlog.parse_modules(text)[0].name, 'b')
            self.assertEqual(len(D.vlog.parse_modules(text)), 2)

    def test_sources_exclude_testbenches_and_reject_path_escape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'rtl').mkdir(); (root / 'tb').mkdir()
            (root / 'rtl/core.v').write_text('module core; endmodule')
            (root / 'tb/core_tb.v').write_text('module tb; endmodule')
            self.assertEqual([p.name for p in D.source_files(root, {})], ['core.v'])
            with self.assertRaisesRegex(ValueError, 'escapes'):
                D.source_files(root, {'files': ['../secret.v']})

    def test_http_fallback_pins_revision_and_records_omissions(self):
        root_url = 'https://opencores.org/ocsvn/core/core/trunk'
        listing = b'<h2>core - Revision 7: /core/trunk</h2><a href="../">..</a><a href="core.v?p=7">core.v</a><a href="work/">work/</a><a href="source.c">source.c</a>'
        def response(url, **kwargs):
            if url in {root_url + '/', root_url + '/?p=7'}: return io.BytesIO(listing)
            if url == root_url + '/core.v?p=7': return io.BytesIO(b'module core;endmodule')
            self.fail(f'Unexpected or unpinned download: {url}')
        with tempfile.TemporaryDirectory() as td, patch.object(D.urllib.request, 'urlopen', side_effect=response):
            target = Path(td) / 'snapshot'
            revision, omitted = D.http_export(root_url, target, 10)
            self.assertEqual(revision, '7')
            self.assertEqual((target / 'core.v').read_text(), 'module core;endmodule')
            self.assertEqual(set(omitted), {'work/', 'source.c'})

    def test_legacy_archive_sources_are_expanded_and_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root / 'source'; source.mkdir(); work = root / 'work'; work.mkdir()
            archive = source / 'core.zip'
            with D.zipfile.ZipFile(archive, 'w') as z: z.writestr('rtl/core.v', 'module core;endmodule')
            view, identity = D.unpack_source(source, work, {}, 10)
            self.assertEqual((view / 'rtl/core.v').read_text(), 'module core;endmodule')
            self.assertEqual(identity['sha256'], D.digest(archive))
            self.assertTrue(archive.exists())
            self.assertEqual(D.unpack_source(source, work, {}, 10)[0], view)
            bad = source / 'bad.zip'
            with D.zipfile.ZipFile(bad, 'w') as z: z.writestr('../escaped.v', 'bad')
            with self.assertRaisesRegex(ValueError, 'Unsafe archive'):
                D.unpack_source(source, work, {'archive': 'bad.zip'}, 10)
            self.assertFalse((work / 'escaped.v').exists())

    def test_environment_isolates_all_artifacts_and_forces_single_local_model(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'work/core').mkdir(parents=True)
            args = SimpleNamespace(root=root, model='qwen3.8:27b')
            with patch.dict(D.os.environ, {'GREAT_CROSS_MODEL': 'other', 'GREAT_CROSS_MODEL_API_KEY': 'private'}):
                env = D.environment(args, 'core')
            self.assertEqual(env['GREAT_MODEL'], 'qwen3.8:27b')
            self.assertEqual(env['GREAT_PIPELINE_DIR'], str(root / 'work/core/pipeline'))
            self.assertEqual(env['GREAT_EXAMPLES_DIR'], str(root / 'rtl'))
            self.assertEqual(env['GREAT_DEPS_DIR'], str(root / 'work/core/deps'))
            self.assertFalse(any(k.startswith('GREAT_CROSS_MODEL') for k in env))

    def test_failure_does_not_publish_and_next_core_completes_in_order(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); data = root / 'data'; data.mkdir()
            (data / 'cores.txt').write_text('bad\ngood\n')
            (root / 'great').mkdir(); (root / 'great/__init__.py').write_text('')
            (root / 'scripts').mkdir()
            for phase in D.PHASES: (root / 'scripts' / phase[1]).write_text('')
            lib = root / 'pdk/asap7/asap7sc7p5t_RVT_TT.lib'; lib.parent.mkdir(parents=True); lib.touch()
            prep = {'cores': {}}
            for core in ('bad', 'good'):
                src = data / f'rtl/{core}.v'; src.parent.mkdir(parents=True, exist_ok=True)
                src.write_text(f'module {core}(input a,output y);assign y=a;endmodule')
                prep['cores'][core] = {'status': 'ready', 'input': str(src.relative_to(root)), 'sha256': D.digest(src), 'language': 'verilog', 'single_file': True, 'top': core}
                (data / f'work/{core}').mkdir(parents=True)
                D.write(data / f'sources/{core}/.spark-provenance.json', {'revision': '1'})
            D.write(data / 'prepare_index.json', prep)
            args = SimpleNamespace(root=data, core=None, model='qwen3.8:27b', force=False, phase_timeout=10)
            calls = []
            def execute(cmd, **kwargs):
                core = Path(cmd[-1]).stem
                phase = next(x for x in D.PHASES if x[1] == Path(cmd[1]).name)
                name, _, folder, suffix = phase
                calls.append((core, name))
                result = {}
                if suffix == 'netlist': result['mapped'] = True
                if suffix == 'verification': result['verdict'] = 'FAIL' if core == 'bad' else 'PASS'
                if suffix == 'leakage': result['measurement_valid'] = True
                if suffix == 'manifests':
                    p = data / f'work/{core}/pipeline/{folder}/{core}.redacted.v'
                    p.parent.mkdir(parents=True, exist_ok=True); p.write_text('module opaque;endmodule')
                    result['redacted_rtl'] = str(p.relative_to(root))
                D.write(data / f'work/{core}/pipeline/{folder}/{core}.{suffix}.json', result)
                return ''
            response = io.BytesIO(json.dumps({'models': [{'name': 'qwen3.8:27b', 'digest': 'weights'}]}).encode())
            with patch.object(D, 'ROOT', root), patch.object(D.shutil, 'which', return_value='/fake/tool'), patch.object(D.urllib.request, 'urlopen', return_value=response), patch.object(D, 'command', side_effect=execute):
                result = D.run(args)
            self.assertEqual(result['cores']['bad']['status'], 'failed')
            self.assertFalse((data / 'redacted/bad').exists())
            self.assertTrue((data / 'redacted/good/good.redacted.v').exists())
            self.assertEqual([p.name for p in (data / 'redacted/good').iterdir()], ['good.redacted.v'])
            self.assertTrue((data / 'reports/good/leakage.json').exists())
            self.assertEqual(calls, [('bad', x[0]) for x in D.PHASES[:6]] + [('good', x[0]) for x in D.PHASES])
            self.assertEqual(result['cores']['good']['status'], 'completed')
            calls.clear()
            args.core = ['good']
            response = io.BytesIO(json.dumps({'models': [{'name': 'qwen3.8:27b', 'digest': 'weights'}]}).encode())
            with patch.object(D, 'ROOT', root), patch.object(D.shutil, 'which', return_value='/fake/tool'), patch.object(D.urllib.request, 'urlopen', return_value=response), patch.object(D, 'command', side_effect=execute):
                D.run(args)
            self.assertEqual(calls, [], 'Completed, unchanged designs must not repeat model calls')


if __name__ == '__main__': unittest.main()
