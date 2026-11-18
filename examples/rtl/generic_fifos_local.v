// Independent implementation: synchronous FIFO, single clock, FWFT output.
module generic_fifos #(parameter WIDTH=8, parameter ADDR_BITS=4)(
 input wire clk, input wire rst, input wire wr_en, input wire rd_en,
 input wire [WIDTH-1:0] din, output wire [WIDTH-1:0] dout,
 output wire full, output wire empty, output reg [ADDR_BITS:0] count);
 localparam DEPTH=(1<<ADDR_BITS);
 reg [WIDTH-1:0] mem [0:DEPTH-1];
 reg [ADDR_BITS-1:0] wp, rp;
 wire pop=rd_en && !empty;
 wire push=wr_en && (!full || pop);
 assign full=(count==DEPTH);
 assign empty=(count==0);
 assign dout=mem[rp];
 always @(posedge clk) begin
   if (rst) begin wp<=0; rp<=0; count<=0; end
   else begin
     if(push) begin mem[wp]<=din; wp<=wp+1'b1; end
     if(pop) rp<=rp+1'b1;
     case ({push,pop})
       2'b10:count<=count+1'b1;
       2'b01:count<=count-1'b1;
       default:count<=count;
     endcase
   end
 end
endmodule
