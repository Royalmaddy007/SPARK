// Copyright 2004-2005 Openchip
// http://www.openchip.org

// ---------------------------------------------------------------------------
// Clock Prescaler
//
// For Xilinx Passive serial we use
// Divide by 16 or 1:1 clock deliver from FGPA (6MHz)
// ---------------------------------------------------------------------------

module xmsmmc_minimal( cclk, done, init, mmc_cmd, mmc_clk );

// Connect to FPGA CCLK, INIT, DONE
// Init and Done need an external PULLUP Resistor!
input  cclk;
input  init; 
input  done; 

// MMC Card DAT goes to FPGA DIN
// MMC Card CS (pin 1) tie high or leave floating
// Connect to MMC Card CMD and CLK
inout  mmc_cmd;
output mmc_clk;

// Instantiate XMSMMC IP
xmsmmc_core boot_i (
    .cclk    (   cclk    ), 
    .done    (   done    ), 
    .init    (   init    ), 
    .mmc_cmd (   mmc_cmd ), 
    .mmc_clk (   mmc_clk ), 
    .dis     (   1'b0    ),  // Tristate control not used
    .error   (           )   // Error output not used
    );

endmodule
module mmc_boot_prescaler_16_1(
  rst,
  sys_clk,
  mmc_clk,
  mode_transfer
  );

input rst;
input sys_clk;
output mmc_clk;
input mode_transfer;

reg [3:0] prescaler;

always @(posedge sys_clk)
  if (rst)
    prescaler <= 4'b0000;
  else
    prescaler <= prescaler + 4'b0001;

// ---------------------------------------------------------------------------
// Select divide by 16 or direct sys_clk (CCLK)
// ---------------------------------------------------------------------------

assign mmc_clk = mode_transfer ?  sys_clk : prescaler[3]; 


endmodule
//
// Hard-wired CMD bit module, includes hard-wired CRC
// optimized for PLD implementation
//


//
// MMC CMD Bit Select
// Start, Command, Arg, CRC, Stop
//

// Copyright 2004-2005 Openchip
// http://www.openchip.org






// send 80 clocks ?


// Initialize


// identify, loop until ready !


// just read the rest of response


// read CID


// assign RCA


// go transfer


// stream read command


// stream read transfer in progress


// config done, just idle wait for reset


// config error, just idle wait for reset




module mmc_cmd_select(
  cmd,
  bit,
  cmd_active,
  data);

input [3:0] cmd;
input [7:0] bit;
output cmd_active;
output data;

wire start_bit;
wire cmd_bits;
wire CMD1_dat;
wire arg16_bit;
wire crc_bit;
wire stop_bit;


//
// Command bits active 
// START, CMD, ARG, CRC7, STOP == 48Bits
//
assign cmd_bits  = (bit[7:6] == 2'b00) & 
                   (bit[5:4] != 2'b11) &
			    (cmd[3:2] != 2'b11);
// Start bit
assign start_bit = bit[7:0] == 8'b00000001;
// RCA=0x01 (D16 in Argument)
assign arg16_bit = bit[7:0] == 8'b00010111; 
// select Start Address for streaming
//assign arg_x_bit = counter_command_bits[7:0] == 8'b00010101; 
// Stop bit
assign stop_bit  = bit[7:0] == 8'b00101111;

// ---------------------------------------------------------------------------
// hard-wired CRC7 generator!
// this implementation requires less resources in PLD 
// than serial CRC calculator
// the values are calculated by an C program
// ---------------------------------------------------------------------------

// CMD0,0          xx
// CMD1,0x80FF8000 xx
// CMD2,0          4d   0100 1101
// CMD3,0x10000    7f   0111 1111
// CMD7,0x10000    dd   1101 1101
// CMD11,0         77   0111 0111

assign crc_bit =
    ( (bit[5:0] == 6'b101000) & ( 
      (cmd==4'b0000) 
    | (cmd==4'b0001) 
    | (cmd==4'b0111) ) ) // CRC6
  
  | ( (bit[5:0] == 6'b101001) & ( 
      (cmd==4'b0010) 
    | (cmd==4'b0011) 
    | (cmd==4'b0111) 
    | (cmd==4'b1011) ) ) // CRC5

  | ( (bit[5:0] == 6'b101010) & ( 
      (cmd==4'b0001) 
    | (cmd==4'b0011) 
    | (cmd==4'b1011) ) ) // CRC4

  | ( (bit[5:0] == 6'b101011) & ( 
      (cmd==4'b0000) 
    | (cmd==4'b0011) 
    | (cmd==4'b0111) 
    | (cmd==4'b1011) ) ) // CRC3

  | ( (bit[5:0] == 6'b101100) & ( 
      (cmd==4'b0001) 
    | (cmd==4'b0010) 
    | (cmd==4'b0011) 
    | (cmd==4'b0111) ) ) // CRC2

  | ( (bit[5:0] == 6'b101101) & ( 
      (cmd==4'b0000) 
    | (cmd==4'b0001) 
    | (cmd==4'b0010) 
    | (cmd==4'b0011) 
    | (cmd==4'b0111) 
    | (cmd==4'b1011) ) ) // CRC1

  | ( (bit[5:0] == 6'b101110) & ( 
      (cmd==4'b0001) 
    | (cmd==4'b0011) 
    | (cmd==4'b1011) ) ) // CRC0
  ;

// ---------------------------------------------------------------------------
// Hard wired ARG for CMD1 == 0x80FF8000
// ---------------------------------------------------------------------------

assign CMD1_dat = (cmd==4'b0001) &
  ( (bit[5:0] == 6'b001000) //
  | (bit[5:0] == 6'b010000) //
  | (bit[5:0] == 6'b010001) //
  | (bit[5:0] == 6'b010010) //
  | (bit[5:0] == 6'b010011) //
  | (bit[5:0] == 6'b010100) //
  | (bit[5:0] == 6'b010101) //
  | (bit[5:0] == 6'b010110) //
  | (bit[5:0] == 6'b010111) //
  | (bit[5:0] == 6'b011000) //
  );
  

// ---------------------------------------------------------------------------
// Select CMD Data output
// ---------------------------------------------------------------------------

assign data =
    start_bit                // START
  | ( cmd[0] & (bit[5:0] == 6'b000111)  )
  | ( cmd[1] & (bit[5:0] == 6'b000110)  )
  | ( cmd[2] & (bit[5:0] == 6'b000101)  )
  | ( cmd[3] & (bit[5:0] == 6'b000100)  )
  | CMD1_dat // CMD1 Argument
  | ( arg16_bit & ((cmd == 4'b0011) | (cmd == 4'b0111)) ) // RCA = 0x1 ARG16
//  | ( arg_x_bit & (cmd_state == CMD11) ) // Start Address = 0x0400 ARG10
  | crc_bit                  // Hard coded CRC7
  | stop_bit;                // STOP

assign cmd_active = cmd_bits;

endmodule

// Copyright 2004-2005 Openchip
// http://www.openchip.org

// Copyright 2004-2005 Openchip
// http://www.openchip.org


// XAPP-151








// Virtex-II/Pro, S-3



// XAPP 151













// Virtex-II



// XAPP 151








  
module xilinx_fpga_config_int(
  // Power on reset (simulat power on reset)
  por,
  sys_clk100,
  // Xilinx Config Interface

  cclk_I, cclk_T, cclk_O,
  init_I, init_T, init_O,

  din,
  prog_b,
  done,
  rdwr_b,
  cs_b,

  // internal registers
  CMD, COR, FAR,
  
  // config input
  M0, M1, M2,
  // JTAG port
  tclk, tdi, tdo, tms,



  //
  trace1,
  trace2
  );


input por;
input sys_clk100;

input  cclk_I;
output cclk_O;
output cclk_T;

input init_I;
output init_T;
output init_O;

input din;
input prog_b;
input rdwr_b;
input cs_b;

output done;




output [3:0] CMD;
output [31:0] COR;
output [31:0] FAR;
input  M0;
input  M1;
input  M2;
input  tclk;
input  tdi;
output tdo;
input  tms;


//
output trace1;
output trace2;


wire init;
assign init = init_I & init_O;

//
// internal reset is high when init and prog are both low
// or on Power On Reset
//
wire internal_reset;
assign internal_reset = !prog_b | !por; 



//
// Clear Int memory, as long as prog_b is low, and some time after it (delay)
//
reg config_memory_cleared;
reg [7:0] config_clear_cnt;

always @(posedge sys_clk100) 
  if (internal_reset)
    config_clear_cnt <= 8'b00000000;
  else
    config_clear_cnt <= config_clear_cnt + 8'b00000001;

always @(posedge sys_clk100) 
  if (internal_reset)
    config_memory_cleared <= 1'b0;
  else
    if (config_clear_cnt[7])
      config_memory_cleared <= 1'b1;

//
// Latch M0, M1, M2
//
reg M_latched;
reg [2:0] M_r;

// have we latched M0, M1, M2 ?
always @(posedge sys_clk100) 
  if (internal_reset)
    M_latched <= 1'b0;
  else
    if (config_memory_cleared)
       M_latched <= 1'b1;

// Latch M0, M1, M2
always @(posedge sys_clk100) 
  if (internal_reset)
    M_r <= 3'b0;
  else
    if (!M_latched & config_memory_cleared)
      M_r <= {M2, M1, M0};


// 
assign init_0 = M_latched;
assign init_T = !M_latched;


//
// Start Master mode CCLK !
//

reg enable_internal_cclk;

always @(posedge sys_clk100) 
  if (internal_reset)
    enable_internal_cclk <= 1'b0;
  else
    if (M_latched)
      enable_internal_cclk <= 1'b1;
//
//
//
wire mode_master_serial;
wire mode_slave_serial;
wire mode_master_parallel;
wire mode_slave_parallel;
wire mode_jtag;

assign mode_master_serial   = (M_r == 3'b000) & M_latched;
assign mode_slave_serial    = (M_r == 3'b000) & M_latched;
assign mode_master_parallel = (M_r == 3'b000) & M_latched;
assign mode_slave_parallel  = (M_r == 3'b000) & M_latched;
assign mode_jtag            = (M_r == 3'b000) & M_latched;







//
// Master CCLK prescaler
//
reg [7:0] prescaler;
wire cclk_master;

always @(posedge sys_clk100) 
  prescaler <= prescaler + 8'b00000001;

assign cclk_master = prescaler[2];


//
// Master or Slave Clock select
//
wire master_clock;
assign master_clock = 1'b1;

assign cclk = master_clock ? cclk_master : cclk_I;


//
// only when running!! before memory clear no CCLK out !
//
assign cclk_O = enable_internal_cclk ? cclk_master : 1'b0;
assign cclk_T = enable_internal_cclk;




    





//
// 32 bit shift register to
// 
reg [31:0] sr;

always @(posedge cclk or posedge internal_reset)
  if (internal_reset)
    sr <= 32'h00000000;
  else 
    begin
      sr[0] <= din; 	
	 sr[1] <= sr[0];
	 sr[2] <= sr[1];	
	 sr[3] <= sr[2];
	 sr[4] <= sr[3];	
	 sr[5] <= sr[4];
	 sr[6] <= sr[5];	
	 sr[7] <= sr[6];
	 sr[8] <= sr[7];	
	 sr[9] <= sr[8];
	 sr[10] <= sr[9];	
	 sr[11] <= sr[10];
	 sr[12] <= sr[11];	
	 sr[13] <= sr[12];
	 sr[14] <= sr[13];	
	 sr[15] <= sr[14];
	 sr[16] <= sr[15];
	 sr[17] <= sr[16];	
	 sr[18] <= sr[17];
	 sr[19] <= sr[18];	
	 sr[20] <= sr[19];
	 sr[21] <= sr[20];	
	 sr[22] <= sr[21];
	 sr[23] <= sr[22];	
	 sr[24] <= sr[23];
	 sr[25] <= sr[24];	
	 sr[26] <= sr[25];
	 sr[27] <= sr[26];	
	 sr[28] <= sr[27];
	 sr[29] <= sr[28];	
	 sr[30] <= sr[29];
      sr[31] <= sr[30];	
    end

//
// Detect Align SYNC
//
wire sync_det;

assign syn_det = sr[31:0] == 32'hAA995566;

reg syn_det_ok;

always @(posedge cclk or posedge internal_reset)
  if (internal_reset)
    syn_det_ok <= 1'b0;
  else 
    if (syn_det)
      syn_det_ok <= 1'b1;


//
// count 32 bits for each word
//
reg [4:0] shift_cnt32;

always @(posedge cclk)
  if (!syn_det_ok)
    shift_cnt32 <= 5'b00000;
  else 
    shift_cnt32 <= shift_cnt32 + 5'b00001;

//
// strobe 32 bit words
//
wire word_stb;

assign word_stb = shift_cnt32 == 5'b11111;

//
//
//
reg [31:0] header;
//
// Statemachine to track latches to the header
//
always @(posedge cclk)
  if (!syn_det_ok)
    header <= 32'h00000000;
  else if (word_stb)
    header <= sr;


//
// Operation Read or Write
//
wire header_op_write;
wire header_op_read;

assign header_op_write = header[28:27] == 2'b10;
assign header_op_read =  header[28:27] == 2'b01;


// Command header field
wire header_type_command;
wire header_type_large_block;

assign header_type_command = header[31:29] == 3'b001;
assign header_type_large_block = header[31:29] == 3'b010;

wire command_header_stb;
assign command_header_stb = header_type_command & word_stb;

//
// Word Counter
//
reg [19:0] WC;



//
// write to config register
//
wire cfg_write_stb;
assign cfg_write_stb = header_type_command & header_op_write & word_stb;


//
// Write strobes to registers
//


// CMD Register is target
wire write_CMD;
assign write_CMD = cfg_write_stb & (header[16:13]==4'b0100);


// COR Option Register is target
wire write_COR;
assign write_COR = cfg_write_stb & (header[16:13]==4'b1001);

// FAR Register is target
wire write_FAR;
assign write_FAR = cfg_write_stb & (header[16:13]==4'b0001);

wire write_FLR;
assign write_FLR = cfg_write_stb & (header[16:13]==4'b1011);

wire write_CRC;
assign write_CRC = cfg_write_stb & (header[16:13]==4'b0000);

wire write_CTL;
assign write_CTL = cfg_write_stb & (header[16:13]==4'b0101);

wire write_MASK;
assign write_MASK = cfg_write_stb & (header[16:13]==4'b0110);

wire write_STAT;
assign write_STAT = cfg_write_stb & (header[16:13]==4'b0111);

wire write_FDRI;
assign write_FDRI = cfg_write_stb & (header[16:13]==4'b0010);


wire write_RES_E;
assign write_RES_E = cfg_write_stb & (header[16:13]==4'b1110);

//
// 4 Bit CMD register
//
reg [3:0] CMD;
//
// Write to CMD latch value written
//
always @(posedge cclk or posedge internal_reset)
  if (internal_reset)
    CMD <= 4'b0000;
  else
    if (write_CMD) 
      CMD <= sr[3:0];
//
// Config states (value in CMD)
//
wire cfg_state_START;
assign cfg_state_START = CMD == 4'b0101;

wire cfg_state_RCRC;
assign cfg_state_RCRC = CMD == 4'b0111;


//
// 31 Bit COR register
//
reg [31:0] COR;
//
// Write to CMD latch value written
//
always @(posedge cclk or posedge internal_reset)
  if (internal_reset)
    COR <= 31'h00000000;
  else
    if (write_COR) 
      COR <= sr[3:0];

//
// 31 Bit FAR register
//
reg [31:0] FAR;
//
// Write to CMD latch value written
//
always @(posedge cclk or posedge internal_reset)
  if (internal_reset)
    FAR <= 31'h00000000;
  else
    if (write_FAR) 
      FAR <= sr[3:0];





//
// Large Block Count
//


wire write_LBC;
assign write_LBC = header_type_large_block & word_stb;





//
// CRC
//

//
//
// holds CRC as written with WCFG CRC 
reg [15:0] CRC_from_cfg;


always @(posedge cclk or posedge internal_reset)
  if (internal_reset)
    CRC_from_cfg <= 16'h0000;
  else if (write_CRC) 
    CRC_from_cfg[15:0] <= sr[15:0];  


//assign trace_sync_found = sr[15:0] == 16'h55AA;

// Virtex/Spartan SYNC word    
assign trace1 = cfg_state_START;

assign done = cfg_state_START;

assign trace2 = 
  write_LBC |
  write_CMD | 
  write_COR | 
  write_CRC | 
  write_FLR | 
  write_FAR |
  write_CTL | 
  write_STAT | 
  write_FDRI | 

  write_RES_E |
  write_MASK;


endmodule
// Copyright 2004-2005 Openchip
// http://www.openchip.org


// Copyright 2004-2005 Openchip
// http://www.openchip.org









































module xmsmmc_core(

  // CCLK From FPGA
  cclk,
  // Done From FPGA, indicates success
  done,
  // Init From FPGA (start of config and ERROR)
  init,
  
  //
  // MMC Card I/O  
  // CS is not used tie up, pull up or leave open (not used)
  // DAT is directly connected to FPGA DIN(D0)
  
  // CMD Pin
  mmc_cmd,
  // CLK Pin
  mmc_clk,

  // Output enable control
  dis,

  // Error goes high if config error, or no MMC card inserted         
  error
  );


// global clock input, is divided to provide 400KHz and 20MHz Clocks    
input  cclk;

input  init;      // Pulse to start config
input  done;      //

// error/status out, goes high on error
output error;

// MMC Card I/O tristate when reset active and after config done/error
inout  mmc_cmd;
output mmc_clk;

//
input dis;


// command data to MMC card
wire cmd_data_out;

// "Transfer Mode" switch MMC clock to direct CCLK!
wire mode_transfer;

//

// CMD1 Response Start Bit
// if not Low, then no Card detected, error !
wire cmd1_resp_start_bit;
// CMD1 Response Busy Bit
// if Low then busy, loop until goes high
wire cmd1_resp_busy_bit;




//
// ASYNC reset we do not yet have clock!
//

//wire int_reset;
//assign int_reset = !init & !done;

wire config_request;
assign config_request = !init & !done;



/*
reg int_reset;

always @(posedge cclk or posedge config_request)
  if (config_request)
    int_reset <= 1'b1;
  else
    int_reset <= 1'b0;
*/

wire int_reset;
assign int_reset = config_request;


// ---------------------------------------------------------------------------
// Clock Prescaler
// ---------------------------------------------------------------------------

wire clk_mmc;
 
mmc_boot_prescaler_16_1 precaler_i (
        .rst    (               int_reset       ),
	.sys_clk(		cclk		), 
	.mmc_clk(		clk_mmc		), 
	.mode_transfer(		mode_transfer	)
	);



// command bit counter
reg [7:0] counter_command_bits;

always @(negedge clk_mmc or posedge int_reset)
  if (int_reset)
    counter_command_bits <= 8'b00000000;
  else
    counter_command_bits <= counter_command_bits + 8'b00000001;

// ------------------------------------------------------------------
//
// ------------------------------------------------------------------

// command sequencer state machine
reg [3:0] cmd_state;
reg [3:0] cmd_state_next;

wire cmd_done;
assign cmd_done = counter_command_bits == 8'b11111111;

// CMD1 response Start (must be low if card is responding
assign cmd1_resp_start_bit = counter_command_bits[7:0] == 8'b00110101;
// CMD1 response Busy bit (must be high if card is ready)
assign cmd1_resp_busy_bit = counter_command_bits[7:0] == 8'b00111101;

//
// COMMAND State machine
//
always @(posedge clk_mmc or posedge int_reset)
  if (int_reset)
    cmd_state <= 4'b1111;
  else 
    cmd_state <= cmd_state_next;

// R1 48 bits
// 00xx xxxx Sxxx xxxx ... xxx1
// R2 136 bits !!
// 00xx ... xxx1
// R3 48 bit
// 00xx ... xxx1

always @(cmd_state, done, cmd_done, init, mmc_cmd, cmd1_resp_start_bit, cmd1_resp_busy_bit)
  begin
    cmd_state_next = cmd_state;

    case (cmd_state) // synopsys full_case parallel_case
	 
	 4'b1111: // send 80+ clocks, then send CMD0
	   begin
	     if (cmd_done & init) cmd_state_next = 4'b0000;
	   end

	 4'b0000: // No response command, go send CMD1
	   begin
	     if (cmd_done) cmd_state_next = 4'b0001;
	   end

	 4'b0001: // send CMD1, loop until response bit31 is high
	   begin
	     // Response start detected ?
		// if not no card and go error
	     if ( (cmd1_resp_start_bit==1'b1) & (mmc_cmd==1'b1) ) 
		  cmd_state_next = 4'b1110;
          	// if not busy advance to next
		// we can jump to next command as we are in the middle
		// of response time, so the next command will not
		// start before the last response has been read
	     if ( (cmd1_resp_busy_bit==1'b1) & (mmc_cmd==1'b1) ) 
		  cmd_state_next = 4'b1001;
	   end

	 4'b1001: // just some clocks spacing
	   begin
	     if (cmd_done) cmd_state_next = 4'b0010;
	   end

	 4'b0010: // send CMD2	R2
	   begin
	     if (cmd_done) cmd_state_next = 4'b0011;
	   end

	 4'b0011: // send CMD3	R1
	   begin
	     if (cmd_done) cmd_state_next = 4'b0111;
	   end

	 4'b0111: // send CMD7	R1
	   begin
	     if (cmd_done) cmd_state_next = 4'b1011;
	   end

	 4'b1011: // send CMD11 R1
	   begin
	     if (cmd_done) cmd_state_next = 4'b1100;
	   end
	 
	 //
	 // Commands are sent, CMD is held high
	 // MMC Card content is streamed out on DAT pin
	 //
	 4'b1100: 
	   begin
	     if (done)
            cmd_state_next = 4'b1101;

	     if (!init)
            cmd_state_next = 4'b1110;
	   end
	 
	 // Config done succesfully!
	 4'b1101:
	   begin
	     
	   end

	 // Some error has occoured
	 4'b1110:
	   begin

	   end

    endcase
  end

//
// transfer mode, select high speed clock
//
assign mode_transfer = cmd_state == 4'b1100;


// ------------------------------------------------------------------
//
// Just emulating a memory to select CMD Data output
//
// ------------------------------------------------------------------

wire cmd_bits;
// 
mmc_cmd_select mmc_cmd_select_i (
	.cmd(		cmd_state		), 
	.bit(		counter_command_bits	), 
	.cmd_active(	cmd_bits		),
	.data(		cmd_data_out		)
    );


// ------------------------------------------------------------------
//
// ------------------------------------------------------------------

assign mmc_cmd = (!dis & cmd_bits) ? cmd_data_out : 1'bz;
assign mmc_clk = !dis ? (int_reset ? 1'b0 : clk_mmc) : 1'bz;

// signal ERROR (active high)
assign error = cmd_state == 4'b1110;


endmodule


//
// BootX-XMSMMC IP Core demonstration
// Minimal configuration - to show the absolute minimal resource useage
// This configuration uses 20 Macrocells in Xilinx XCR3032
// 
// Copyright 2004-2005 Openchip
// http://www.openchip.org
//
// Copyright 2004-2005 Openchip
// http://www.openchip.org










































