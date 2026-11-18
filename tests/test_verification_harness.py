"""Exercise real elaboration and simulation, including negative controls."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from great.changelog import ChangeLog

spec = importlib.util.spec_from_file_location('phase5_verify', Path(__file__).parents[1] / 'scripts/phase5_verify.py')
p5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p5)

class HarnessTests(unittest.TestCase):
    def test_nonansi_register_range_without_space(self):
        src='module top(a,y);input[7:0] a;output reg[7:0] y;always @* y=a;endmodule'
        ports=p5.vlog.parse_modules(src)[0].ports
        self.assertEqual([p['name'] for p in ports],['a','y'])
        self.assertTrue(p5.check_interface(src,src,{},ChangeLog('test','nonansi'))['ok'])

    def test_analysis_view_keeps_logic_after_large_rom(self):
        rows="\n".join(f"8'd{i}: y = 8'd{i};" for i in range(64))
        source="module rom(input [7:0] a,output reg [7:0] y);always @* case(a)\n"+rows+"\nendcase endmodule\nmodule logic_after(input a,output y);assign y=~a;endmodule"
        view,meta=p5.vlog.analysis_view(source,900)
        self.assertEqual(len(p5.vlog.parse_modules(view)),2)
        self.assertIn("8'd0:",view)
        self.assertIn("8'd63:",view)
        self.assertIn('assign y=~a',view)
        self.assertEqual(meta['omitted_literal_rom_rows'],56)
        self.assertFalse(meta['truncated'])
        self.assertEqual(p5.vlog.analysis_view(source,100000)[0],source)

    def test_hierarchical_namespace_and_parameter_widths(self):
        gold = '''module top(a,y); parameter WIDTH=9; input [WIDTH-1:0] a; output [WIDTH-1:0] y; child u(a,y); endmodule
module child(input [8:0] a, output [8:0] y); assign y=a ^ 9'h12; endmodule'''
        red = gold.replace('WIDTH', 'opaque_width')
        cl = ChangeLog('test', 'harness')
        self.assertTrue(p5.check_interface(gold, red, {}, cl)['ok'])
        tb, _ = p5.build_testbench(gold, red, {}, [])
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder)/'a.v', Path(folder)/'b.v'
            a.write_text(gold); b.write_text(red)
            self.assertTrue(p5.simulate(a,b,tb,cl,'harness')['passed'])
            b.write_text(red.replace("9'h12", "9'h13"))
            self.assertFalse(p5.simulate(a,b,tb,cl,'harness')['passed'])
        self.assertFalse(p5.check_interface(gold, red.replace('opaque_width=9','opaque_width=8'), {}, cl)['ok'])

    def test_inouts_have_independent_resolved_nets(self):
        gold="module top(input en, inout bus); assign bus=en ? 1'bz : 1'b0; endmodule"
        red=gold.replace(": 1'b0", ": 1'b1")
        cl=ChangeLog('test','inout')
        tb,_=p5.build_testbench(gold,red,{},[])
        self.assertIn('.bus(bus_ref)',tb)
        self.assertIn('.bus(bus_red)',tb)
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.v',Path(folder)/'b.v'
            a.write_text(gold);b.write_text(red)
            self.assertFalse(p5.simulate(a,b,tb,cl,'inout')['passed'])

    def test_formal_name_normalization_keeps_logic_mutations_visible(self):
        gold="module top(input [7:0] a,output [7:0] y);wire [7:0] sum;assign sum=a+8'd3;assign y=sum;endmodule"
        red=gold.replace('sum','opaque_sum')
        mf={'identifier_manifest':{'sum':'opaque_sum'}}
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.v',Path(folder)/'b.v';a.write_text(gold);b.write_text(red)
            self.assertTrue(p5.formal(a,b,mf,ChangeLog('test','alpha'),budget_s=5)['proved'])
            b.write_text(red.replace("8'd3","8'd4"))
            self.assertEqual(p5.formal(a,b,mf,ChangeLog('test','alpha_mutation'),budget_s=5)['method'],'refuted')

    def test_formal_proves_recorded_fsm_encoding_and_rejects_wrong_output(self):
        gold="""module top(input clk,rst,go,output reg y);
localparam IDLE=2'd0, RUN=2'd1;reg [1:0] state;
always@(posedge clk)if(rst)state<=IDLE;else if(go)state<=RUN;
always @* case(state)
IDLE:y=0;
RUN:y=1;
default:y=0;
endcase endmodule"""
        red=gold.replace("IDLE=2'd0, RUN=2'd1","IDLE=2'd3, RUN=2'd2")
        mf={'fsm_encoding':{'top.IDLE':"2'h3",'top.RUN':"2'h2"}}
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.v',Path(folder)/'b.v';a.write_text(gold);b.write_text(red)
            self.assertEqual(p5.formal(a,b,mf,ChangeLog('test','fsm_certificate'),budget_s=5)['method'],'structural_induction')
            b.write_text(red.replace('RUN:y=1','RUN:y=0'))
            self.assertEqual(p5.formal(a,b,mf,ChangeLog('test','bad_fsm'),budget_s=5)['method'],'refuted')

    def test_module_name_does_not_rename_signal(self):
        source='module top(input child, output y); child u(child,y); endmodule\nmodule child(input a, output b); assign b=a; endmodule'
        alias, name = p5.alias_redacted(source,'top')
        self.assertIn('input child', alias)
        self.assertIn('u(child,y)', alias)
        self.assertIn('_verify_red_1_child u',alias)
        self.assertEqual(name,'_verify_red_0_top')


class TransformSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
        import phase4_transform
        cls.p4 = phase4_transform

    def test_comment_stripping_preserves_synthesis_controls(self):
        src="module top(input clk,output reg y);\n// proprietary explanation\ninitial begin\n// synthesis translate_off\ny=1'b1;\n// synthesis translate_on\nend\nalways @(posedge clk)y<=~y;endmodule"
        st={'rtl':src};self.p4.step_4f_strip(st,ChangeLog('test','pragmas'))
        self.assertIn('// synthesis translate_off',st['rtl'])
        self.assertIn('// synthesis translate_on',st['rtl'])
        self.assertNotIn('proprietary explanation',st['rtl'])
        for text in (src,st['rtl']):
            with tempfile.TemporaryDirectory() as folder:
                folder=Path(folder);(folder/'in.v').write_text(text)
                rc,_,err=p5.run([p5.C.YOSYS,'-Q','-T','-p','read_verilog in.v; prep -top top; write_json out.json'],cwd=folder)
                self.assertEqual(rc,0,err)
                import json
                net=json.loads((folder/'out.json').read_text())['modules']['top']['netnames']['y']
                self.assertNotIn('init',net.get('attributes',{}))

    def test_comparison_chain_preserves_borrow_and_upper_bits(self):
        import random
        for signed in ('', 'signed '):
            for op in ('==','!='):
                source=f"module top(input {signed}[7:0] a, output y); assign y=(a {op} 5'b00000); endmodule"
                st={'rtl':source,'rng':random.Random(3),'high_lines':lambda s: set(range(1,100))}
                cl=ChangeLog('test','compare_width')
                self.p4.step_4d(st,cl)
                tb,_=p5.build_testbench(source,st['rtl'],{},[])
                with tempfile.TemporaryDirectory() as folder:
                    a,b=Path(folder)/'a.v',Path(folder)/'b.v'
                    a.write_text(source);b.write_text(st['rtl'])
                    self.assertTrue(p5.simulate(a,b,tb,cl,'compare_width')['passed'])

    def test_mask_constant_in_wider_expression(self):
        import random
        source = "module top(input a, output [31:0] y); assign y = 8'h12; endmodule"
        for seed in range(4):
            st={'rtl':source,'rng':random.Random(seed),'high_lines':lambda s: set(range(1,100))}
            cl=ChangeLog('test','mask_width')
            self.p4.step_4c(st,cl)
            tb,_=p5.build_testbench(source,st['rtl'],{},[])
            with tempfile.TemporaryDirectory() as folder:
                a,b=Path(folder)/'a.v',Path(folder)/'b.v'
                a.write_text(source);b.write_text(st['rtl'])
                self.assertTrue(p5.simulate(a,b,tb,cl,'mask_width')['passed'])

    def test_state_labels_are_scoped_per_module(self):
        import random
        source="""module top(input clk, input rst, input go, output y);
localparam IDLE=2'd0, RUN=2'd1; reg [1:0] state;
always @(posedge clk) if(rst) state<=IDLE; else if(go) state<=RUN;
reg own; always @* case(state) IDLE:own=0; RUN:own=1; default:own=0; endcase
wire other; child u(clk,rst,go,other); assign y=own^other; endmodule
module child(input clk, input rst, input go, output reg y);
localparam IDLE=3'd3, RUN=3'd4; reg [2:0] state;
always @(posedge clk) if(rst) state<=IDLE; else if(go) state<=RUN;
always @* case(state) IDLE:y=0; RUN:y=1; default:y=0; endcase endmodule"""
        st={'rtl':source,'rng':random.Random(3)}
        cl=ChangeLog('test','scoped_states')
        self.p4.step_4e(st,cl)
        self.assertIn('top.IDLE',st['fsm_encoding'])
        self.assertIn('child.IDLE',st['fsm_encoding'])
        self.assertTrue(st['fsm_encoding']['top.IDLE'].startswith("2'"))
        self.assertTrue(st['fsm_encoding']['child.IDLE'].startswith("3'"))
        tb,_=p5.build_testbench(source,st['rtl'],{},[])
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.v',Path(folder)/'b.v'
            a.write_text(source);b.write_text(st['rtl'])
            self.assertTrue(p5.simulate(a,b,tb,cl,'scoped_states')['passed'])

    def test_combinational_operation_codes_are_not_fsm_states(self):
        import random
        source="""module top(input sel,output y,output reg z);
localparam ADD=4'b1000, SUB=4'b0100; reg [3:0] op;
always @* if(sel) op=ADD; else op=SUB;
always @* case(op) ADD:z=0; SUB:z=1; default:z=0; endcase
assign y=op[3]; endmodule"""
        st={'rtl':source,'rng':random.Random(3)}
        self.p4.step_4e(st,ChangeLog('test','alu_codes'))
        self.assertEqual(source,st['rtl'])

    def test_internal_instruction_decode_is_not_an_fsm(self):
        import random
        source="""module top(input clk, input [3:0] instruction, output reg y);
localparam READ=4'h2, WRITE=4'h3;
reg [3:0] opcode;
always @(posedge clk) opcode <= instruction;
always @* case(opcode) READ:y=0; WRITE:y=1; default:y=0; endcase
endmodule"""
        st={'rtl':source,'rng':random.Random(3)}
        self.p4.step_4e(st,ChangeLog('test','decode'))
        self.assertEqual(source,st['rtl'])

if __name__ == '__main__': unittest.main()
