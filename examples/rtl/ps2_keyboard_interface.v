// Independent implementation: PS/2 byte receiver, odd parity and stop checking.
// ps2_clk and ps2_data must be externally conditioned for metastability/noise.
module ps2_keyboard_interface(input wire clk, input wire rst,
 input wire ps2_clk, input wire ps2_data,
 output reg [7:0] data, output reg valid, output reg frame_error);
 reg [2:0] clk_sync;
 reg [10:0] frame;
 reg [3:0] bit_count;
 wire fall_edge=(clk_sync[2:1]==2'b10);
 always @(posedge clk) begin
   if(rst) begin clk_sync<=3'b111; frame<=0; bit_count<=0;
     data<=0; valid<=0; frame_error<=0; end
   else begin
     clk_sync<={clk_sync[1:0],ps2_clk}; valid<=0; frame_error<=0;
     if(fall_edge) begin
       frame[bit_count]<=ps2_data;
       if(bit_count==10) begin
         bit_count<=0;
         if(frame[0]==0 && ps2_data==1 && (^{frame[9:1]})==1'b1) begin
           data<=frame[8:1]; valid<=1;
         end else frame_error<=1;
       end else bit_count<=bit_count+1'b1;
     end
   end
 end
endmodule
