"""A missing LLM posterior must never become a measured zero-leakage result."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('phase6',Path(__file__).parents[1]/'scripts/phase6_leakage.py')
p6=importlib.util.module_from_spec(spec);spec.loader.exec_module(p6)

class PosteriorTests(unittest.TestCase):
    def test_candidate_value_formats(self):
        self.assertEqual(p6.candidate_value('02000000'),0x02000000)
        self.assertEqual(p6.candidate_value("8'hFF"),255)
        self.assertEqual(p6.candidate_value('0b101'),5)
        self.assertEqual(p6.candidate_value(42),42)
        self.assertEqual(p6.candidate_value('42'),42)

    def evaluate(self, answer):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rtl=root/'red.v';rtl.write_text('module red(input a, output y);assign y=a;endmodule')
            folders={n:root/f'p{n}' for n in (1,3,6)}
            for p in folders.values():p.mkdir()
            (folders[1]/'sample.profile.json').write_text(json.dumps({'llm':{'design_purpose':'test logic','security_role':'none'}}))
            (folders[3]/'sample.strategy.json').write_text(json.dumps({'design_budget_tier':'B2'}))
            manifest={'redacted_rtl':'red.v','masked_constants':[{'width':8,'value':i+1,'original':f"8'd{i+1}",'line':1} for i in range(25)]}
            with patch.object(p6.C,'ROOT',root),patch.dict(p6.C.PHASE_DIRS,folders),patch.object(p6.llm,'generate_json',side_effect=answer):
                return p6.analyse(root/'sample.v',manifests_override=manifest,rtl_override=rtl)

    def test_removed_mask_declarations_are_excluded_from_delivered_sites(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'red.v').write_text("module m(output [7:0] y);assign y=((8'h44 - 8'h11) ^ 8'h22);endmodule")
            manifest={'redacted_rtl':'red.v','masked_constants':[
                {'width':8,'value':17,'masked':68,'add':17,'xor':34,'original':"8'h11",'line':1},
                {'width':8,'value':18,'masked':69,'add':18,'xor':35,'original':"8'h12",'line':2}]}
            with patch.object(p6.C,'ROOT',root):
                self.assertEqual(len(p6.truth_secrets(manifest,surviving_only=True)),1)
                # Comparison experiments may deliberately attack the original
                # target set in a different representation.
                self.assertEqual(len(p6.truth_secrets(manifest)),2)

    def test_all_sites_above_old_24_site_limit_are_requested(self):
        requested=[]
        def answer(prompt,**kwargs):
            if 'SECRETS TO ESTIMATE' in prompt:
                ids=re.findall(r'^  (K\d+):',prompt,re.M);requested.extend(ids)
                return {'posteriors':[{'secret_id':s,'candidates':[{'value':'0x01','p':0.5}]} for s in ids]},{'parsed':True}
            return {'module_purpose':'test logic','recovered_constants':[]},{'parsed':True}
        result=self.evaluate(answer)
        self.assertTrue(result['measurement_valid'])
        self.assertEqual(len(set(requested)),25)
        self.assertEqual(len(result['per_secret_leakage']),25)
        self.assertTrue(all(s['n_candidates'] for s in result['per_secret_leakage']))

    def test_missing_posteriors_invalidate_measurement(self):
        def answer(prompt,**kwargs):
            return ({'posteriors':[]} if 'SECRETS TO ESTIMATE' in prompt else {'module_purpose':'test logic','recovered_constants':[]}),{'parsed':True}
        self.assertFalse(self.evaluate(answer)['measurement_valid'])
