// Independent implementation: phase accumulator and square-wave DDS.
module dds_synthesizer #(parameter PHASE_WIDTH=32)(
 input wire clk, input wire rst, input wire enable,
 input wire [PHASE_WIDTH-1:0] tuning_word,
 output reg [PHASE_WIDTH-1:0] phase,
 output wire square_out);
 always @(posedge clk) begin
   if(rst) phase<=0;
   else if(enable) phase<=phase+tuning_word;
 end
 assign square_out=phase[PHASE_WIDTH-1];
endmodule
