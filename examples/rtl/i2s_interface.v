// Independent implementation: I2S transmitter, 16-bit stereo, external BCLK.
// Expects BCLK slow enough for synchronous edge detection; WS left=0, right=1.
module i2s_interface(input wire clk, input wire rst, input wire bclk,
 input wire [15:0] left_sample, input wire [15:0] right_sample,
 output reg ws, output reg sd, output reg frame_start);
 reg [2:0] bsync;
 reg [5:0] slot;
 wire falling=(bsync[2:1]==2'b10);
 always @(posedge clk) begin
   if(rst) begin bsync<=3'b000; slot<=0; ws<=0; sd<=0; frame_start<=0; end
   else begin
     bsync<={bsync[1:0],bclk}; frame_start<=0;
     if(falling) begin
       slot<=slot+1'b1;
       ws<=(slot>=32);
       if(slot==0) begin sd<=0; frame_start<=1; end
       else if(slot<=16) sd<=left_sample[16-slot];
       else if(slot==32) sd<=0;
       else if(slot>=33 && slot<=48) sd<=right_sample[48-slot];
       else sd<=0;
     end
   end
 end
endmodule
