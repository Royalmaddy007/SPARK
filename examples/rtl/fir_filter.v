// Independent implementation: four-tap signed FIR with parameterized coefficients.
// Output is registered; truncation/overflow wrap to OUT_WIDTH.
module fir_filter #(parameter IN_WIDTH=16, parameter COEFF_WIDTH=16,
 parameter OUT_WIDTH=36, parameter signed C0=1, C1=1, C2=1, C3=1)(
 input wire clk, input wire rst, input wire valid_in,
 input wire signed [IN_WIDTH-1:0] sample_in,
 output reg valid_out, output reg signed [OUT_WIDTH-1:0] sample_out);
 reg signed [IN_WIDTH-1:0] d1,d2,d3;
 wire signed [OUT_WIDTH-1:0] acc =
 $signed(sample_in)*$signed(C0) + $signed(d1)*$signed(C1) +
 $signed(d2)*$signed(C2) + $signed(d3)*$signed(C3);
 always @(posedge clk) begin
   if(rst) begin d1<=0; d2<=0; d3<=0; sample_out<=0; valid_out<=0; end
   else begin
     valid_out<=valid_in;
     if(valid_in) begin d3<=d2; d2<=d1; d1<=sample_in; sample_out<=acc; end
   end
 end
endmodule
