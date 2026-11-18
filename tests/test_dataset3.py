"""Local-dataset input isolation, snapshot integrity, and actual HDL preparation."""
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import dataset3 as M


class LocalDatasetTests(unittest.TestCase):
    def test_discovery_does_not_reprocess_generated_rtl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'counter.v';source.write_text('module counter; endmodule\n')
            for folder in ['rtl','sources/counter','redacted/counter','work/counter/pipeline/phase4_transform']:
                out=root/folder;out.mkdir(parents=True,exist_ok=True)
                (out/'generated.v').write_text('module generated; endmodule\n')
            self.assertEqual(M.discover(root),[source])
            outside=root.parent/(root.name+'-outside.v');outside.write_text('module outside; endmodule\n')
            try:
                (root/'escape.v').symlink_to(outside)
                with self.assertRaisesRegex(ValueError,'symlink leaves'): M.discover(root)
            finally: outside.unlink()

    def test_snapshots_are_verified_and_changed_inputs_preserve_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'counter.v';header=root/'defs.vh'
            original='module counter; endmodule\n';src.write_text(original);header.write_text('`define W 4\n')
            with patch.object(M.D,'ROOT',root):
                first=M.snapshot('counter',src,root)
                self.assertEqual(src.read_text(),original)
                self.assertEqual(first['transport'],'local')
                self.assertTrue(M.snapshot('counter',src,root)['cached'])
                (root/'sources/counter/counter.v').write_text('tampered')
                restored=M.snapshot('counter',src,root)
                self.assertNotIn('cached',restored)
                self.assertEqual((root/'sources/counter/counter.v').read_text(),original)
                header.write_text('`define W 8\n')
                changed=M.snapshot('counter',src,root)
                self.assertNotEqual(first['input_sha256'],changed['input_sha256'])
                self.assertEqual((root/'sources/counter/defs.vh').read_text(),'`define W 8\n')
                self.assertEqual(len(list((root/'source_history/counter').iterdir())),2)

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('yosys'),'EDA tools required')
    def test_real_preparation_retains_sources_and_isolates_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);src=root/'counter.v'
            original='module counter(input clk,input rst,output reg [3:0] q); always @(posedge clk) if(rst) q<=0; else q<=q+1; endmodule\n'
            src.write_text(original)
            args=SimpleNamespace(root=root,core=None,overrides=root/'dataset3_overrides.json',prepare_timeout=30)
            with patch.object(M.D,'ROOT',root):
                result=M.prepare_local(args)
                self.assertEqual(result['cores']['counter']['status'],'ready',result)
                canonical=root/result['cores']['counter']['input']
                self.assertEqual(canonical,root/'rtl/counter.v')
                self.assertEqual(src.read_text(),original)
                self.assertTrue((root/'work/counter/hierarchy.log').exists())
                # Removing an input retires its previous generated delivery.
                final=root/'redacted/counter/counter.redacted.v';final.parent.mkdir(parents=True);final.write_text('old delivery')
                src.rename(root/'counter.saved')
                (root/'other.v').write_text('module other(input a,output y);assign y=~a;endmodule\n')
                M.prepare_local(args)
                self.assertFalse(final.exists())
                self.assertFalse((root/'rtl/counter.v').exists())
                self.assertEqual((root/'cores.txt').read_text(),'other\n')
                self.assertEqual(len(list((root/'previous/counter').glob('removed-*/redacted/counter.redacted.v'))),1)


if __name__=='__main__': unittest.main()
