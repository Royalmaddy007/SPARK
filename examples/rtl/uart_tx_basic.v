// Independent implementation: 8N1 UART transmitter only, not a 16750 register-compatible UART.
// Named uart_tx_basic intentionally to avoid implying 16750 compliance.
module uart_tx_basic #(parameter CLKS_PER_BIT=434)(
 input wire clk, input wire rst, input wire start, input wire [7:0] data,
 output reg tx, output reg busy, output reg done);
 reg [15:0] timer;
 reg [3:0] index;
 reg [9:0] shifter;
 always @(posedge clk) begin
   if(rst) begin tx<=1; busy<=0; done<=0; timer<=0; index<=0; shifter<=10'h3ff; end
   else begin
     done<=0;
     if(!busy) begin
       if(start) begin shifter<={1'b1,data,1'b0}; busy<=1; index<=0;
         timer<=0; tx<=0; end
     end else if(timer==CLKS_PER_BIT-1) begin
       timer<=0;
       if(index==9) begin tx<=1; busy<=0; done<=1; end
       else begin index<=index+1'b1; shifter<={1'b1,shifter[9:1]}; tx<=shifter[1]; end
     end else timer<=timer+1'b1;
   end
 end
endmodule
