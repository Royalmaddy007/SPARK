// Independent implementation: SPI mode-0 master, 8-bit, one transaction per start.
// Divider specifies half SCLK period in system clocks (minimum 2).
module spi_master_slave #(parameter DIVIDER=4)(
 input wire clk, input wire rst, input wire start,
 input wire [7:0] tx_data, input wire miso,
 output reg mosi, output reg sclk, output reg cs_n,
 output reg [7:0] rx_data, output reg busy, output reg done);
 reg [7:0] tx_shift,rx_shift;
 reg [2:0] bit_idx;
 reg [31:0] div_count;
 reg edge_phase;
 always @(posedge clk) begin
   if(rst) begin mosi<=0; sclk<=0; cs_n<=1; rx_data<=0;
     busy<=0; done<=0; tx_shift<=0; rx_shift<=0;
     bit_idx<=0; div_count<=0; edge_phase<=0; end
   else begin
     done<=0;
     if(!busy) begin
       if(start) begin busy<=1; cs_n<=0; sclk<=0;
         tx_shift<=tx_data; mosi<=tx_data[7]; rx_shift<=0;
         bit_idx<=0; div_count<=0; edge_phase<=0; end
     end else if(div_count==DIVIDER-1) begin
       div_count<=0;
       if(!edge_phase) begin
         sclk<=1; rx_shift<={rx_shift[6:0],miso}; edge_phase<=1;
       end else begin
         sclk<=0; edge_phase<=0;
         if(bit_idx==7) begin
           rx_data<=rx_shift; busy<=0; cs_n<=1; done<=1;
         end else begin
           bit_idx<=bit_idx+1'b1;
           tx_shift<={tx_shift[6:0],1'b0}; mosi<=tx_shift[6];
         end
       end
     end else div_count<=div_count+1'b1;
   end
 end
endmodule
