/////////////////////////////////////////////////////////////////////
////                                                             ////
////  Universal FIFO Single Clock                                ////
////                                                             ////
////                                                             ////
////  Author: Rudolf Usselmann                                   ////
////          rudi@asics.ws                                      ////
////                                                             ////
////                                                             ////
////  D/L from: http://www.opencores.org/cores/generic_fifos/    ////
////                                                             ////
/////////////////////////////////////////////////////////////////////
////                                                             ////
//// Copyright (C) 2000-2002 Rudolf Usselmann                    ////
////                         www.asics.ws                        ////
////                         rudi@asics.ws                       ////
////                                                             ////
//// This source file may be used and distributed without        ////
//// restriction provided that this copyright statement is not   ////
//// removed from the file and that any derivative work contains ////
//// the original copyright notice and the associated disclaimer.////
////                                                             ////
////     THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY     ////
//// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED   ////
//// TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS   ////
//// FOR A PARTICULAR PURPOSE. IN NO EVENT SHALL THE AUTHOR      ////
//// OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,         ////
//// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES    ////
//// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE   ////
//// GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR        ////
//// BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF  ////
//// LIABILITY, WHETHER IN  CONTRACT, STRICT LIABILITY, OR TORT  ////
//// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT  ////
//// OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         ////
//// POSSIBILITY OF SUCH DAMAGE.                                 ////
////                                                             ////
/////////////////////////////////////////////////////////////////////

//  CVS Log
//
//  $Id: generic_fifo_dc.v,v 1.1.1.1 2002-09-25 05:42:02 rudi Exp $
//
//  $Date: 2002-09-25 05:42:02 $
//  $Revision: 1.1.1.1 $
//  $Author: rudi $
//  $Locker:  $
//  $State: Exp $
//
// Change History:
//               $Log: not supported by cvs2svn $
//
//
//
//
//
//
//
//
//
//

`timescale 1ns / 100ps

/*

Description
===========

I/Os
----
rd_clk	Read Port Clock
wr_clk	Write Port Clock
rst	low active, either sync. or async. master reset (see below how to select)
clr	synchronous clear (just like reset but always synchronous), high active
re	read enable, synchronous, high active
we	read enable, synchronous, high active
din	Data Input
dout	Data Output

full	Indicates the FIFO is full (driven at the rising edge of wr_clk)
empty	Indicates the FIFO is empty (driven at the rising edge of rd_clk)

full_n	Indicates if the FIFO has space for N entries (driven of wr_clk)
empty_n	Indicates the FIFO has at least N entries (driven of rd_clk)

level		indicates the FIFO level:
		2'b00	0-25%	 full
		2'b01	25-50%	 full
		2'b10	50-75%	 full
		2'b11	%75-100% full

Status Timing
-------------
All status outputs are registered. They are asserted immediately
as the full/empty condition occurs, however, there is a 2 cycle
delay before they are de-asserted once the condition is not true
anymore.

Parameters
----------
The FIFO takes 3 parameters:
dw	Data bus width
aw	Address bus width (Determines the FIFO size by evaluating 2^aw)
n	N is a second status threshold constant for full_n and empty_n
	If you have no need for the second status threshold, do not
	connect the outputs and the logic should be removed by your
	synthesis tool.

Synthesis Results
-----------------
In a Spartan 2e a 8 bit wide, 8 entries deep FIFO, takes 85 LUTs and runs
at about 116 MHz (IO insertion disabled). The registered status outputs
are valid after 2.1NS, the combinatorial once take out to 6.5 NS to be
available.

Misc
----
This design assumes you will do appropriate status checking externally.

IMPORTANT ! writing while the FIFO is full or reading while the FIFO is
empty will place the FIFO in an undefined state.

*/


// Selecting Sync. or Async Reset
// ------------------------------
// Uncomment one of the two lines below. The first line for
// synchronous reset, the second for asynchronous reset


//`define DC_FIFO_ASYNC_RESET	or negedge rst		// Uncomment for Async. reset


module lfsr (clk, ena, nReset, rst, q);

	//
	// parameters
	//
	parameter [3:0] TAPS   = 8;                // number of flip-flops in LFSR

	//
	// inputs & outputs
	//
	input clk;                                 // master clock
	input ena;                                 // clock enable
	input nReset;                              // asynchronous active low reset
	input rst;                                 // synchronous active high reset

	output [TAPS:1] q;                         // LFSR output
	reg [TAPS:1] q;

	//
	// Module body
	//
	function lsb;
	   input [TAPS-1:0] q;

	   case (TAPS)
	       2: lsb = ~q[0];
	       3: lsb = q[3] ^ q[2];
	       4: lsb = q[4] ^ q[3];
	       5: lsb = q[5] ^ q[3];
	       6: lsb = q[6] ^ q[5];
	       7: lsb = q[7] ^ q[6];
	       8: lsb = q[8] ^ q[6] ^ q[5] ^ q[4];
	       9: lsb = q[9] ^ q[5];
	      10: lsb = q[10] ^ q[7];
	      11: lsb = q[11] ^ q[9];
	      12: lsb = q[12] ^ q[6] ^ q[4] ^ q[1];
	      13: lsb = q[13] ^ q[4] ^ q[3] ^ q[1];
	      14: lsb = q[14] ^ q[5] ^ q[3] ^ q[1];
	      15: lsb = q[15] ^ q[14];
	      16: lsb = q[16] ^ q[15] ^ q[13] ^ q[4];
	   endcase
	endfunction

	always @(posedge clk or negedge nReset)
	  if (~nReset)	q <= #1 0;
	  else if (rst)	q <= #1 0;
	  else if (ena)	q <= #1 {q[TAPS-1:1], lsb(q)};
endmodule
module generic_fifo_dc(rd_clk, wr_clk, rst, clr, din, we, dout, re,
			full, empty, full_n, empty_n, level );

parameter dw=8;
parameter aw=8;
parameter n=32;
parameter max_size = 1<<aw;

input			rd_clk, wr_clk, rst, clr;
input	[dw-1:0]	din;
input			we;
output	[dw-1:0]	dout;
input			re;
output			full; 
output			empty;
output			full_n;
output			empty_n;
output	[1:0]		level;

////////////////////////////////////////////////////////////////////
//
// Local Wires
//

reg	[aw:0]		wp;
wire	[aw:0]		wp_pl1;
reg	[aw:0]		rp;
wire	[aw:0]		rp_pl1;
reg	[aw:0]		wp_s, rp_s;
wire	[aw:0]		diff;
reg	[aw:0]		diff_r1, diff_r2;
reg			re_r, we_r;
reg			full, empty, full_n, empty_n;
reg	[1:0]		level;

////////////////////////////////////////////////////////////////////
//
// Memory Block
//

generic_dpram  #(aw,dw) u0(
	.rclk(		rd_clk		),
	.rrst(		!rst		),
	.rce(		1'b1		),
	.oe(		1'b1		),
	.raddr(		rp[aw-1:0]	),
	.do(		dout		),
	.wclk(		wr_clk		),
	.wrst(		!rst		),
	.wce(		1'b1		),
	.we(		we		),
	.waddr(		wp[aw-1:0]	),
	.di(		din		)
	);

////////////////////////////////////////////////////////////////////
//
// Read/Write Pointers Logic
//

always @(posedge wr_clk )
	if(!rst)	wp <= #1 {aw+1{1'b0}};
	else
	if(clr)		wp <= #1 {aw+1{1'b0}};
	else
	if(we)		wp <= #1 wp_pl1;

assign wp_pl1 = wp + { {aw{1'b0}}, 1'b1};

always @(posedge rd_clk )
	if(!rst)	rp <= #1 {aw+1{1'b0}};
	else
	if(clr)		rp <= #1 {aw+1{1'b0}};
	else
	if(re)		rp <= #1 rp_pl1;

assign rp_pl1 = rp + { {aw{1'b0}}, 1'b1};

////////////////////////////////////////////////////////////////////
//
// Synchronization Logic
//

// write pointer
always @(posedge rd_clk)	wp_s <= #1 wp;

// read pointer
always @(posedge wr_clk)	rp_s <= #1 rp;

////////////////////////////////////////////////////////////////////
//
// Registered Full & Empty Flags
//

always @(posedge rd_clk)
	empty <= #1 (wp_s == rp) | (re & (wp_s == rp_pl1));

always @(posedge wr_clk)
	full <= #1 ((wp[aw-1:0] == rp_s[aw-1:0]) & (wp[aw] != rp_s[aw])) |
	(we & (wp_pl1[aw-1:0] == rp_s[aw-1:0]) & (wp_pl1[aw] != rp_s[aw]));

////////////////////////////////////////////////////////////////////
//
// Registered Full_n & Empty_n Flags
//

assign diff = wp-rp;

always @(posedge rd_clk)
	re_r <= #1 re;

always @(posedge rd_clk)
	diff_r1 <= #1 diff;

always @(posedge rd_clk)
	empty_n <= #1 (diff_r1 < n) | ((diff_r1==n) & (re | re_r));

always @(posedge wr_clk)
	we_r <= #1 we;

always @(posedge wr_clk)
	diff_r2 <= #1 diff;

always @(posedge wr_clk)
	full_n <= #1 (diff_r2 > max_size-n) | ((diff_r2==max_size-n) & (we | we_r));

always @(posedge wr_clk)
	level <= #1 {2{diff[aw]}} | diff[aw-1:aw-2];


////////////////////////////////////////////////////////////////////
//
// Sanity Check
//

// synopsys translate_off
always @(posedge wr_clk)
	if(we & full)
		$display("%m WARNING: Writing while fifo is FULL (%t)",$time);

always @(posedge rd_clk)
	if(re & empty)
		$display("%m WARNING: Reading while fifo is EMPTY (%t)",$time);
// synopsys translate_on

endmodule

/////////////////////////////////////////////////////////////////////
////                                                             ////
////  Universal FIFO Dual Clock, gray encoded                    ////
////                                                             ////
////                                                             ////
////  Author: Rudolf Usselmann                                   ////
////          rudi@asics.ws                                      ////
////                                                             ////
////                                                             ////
////  D/L from: http://www.opencores.org/cores/generic_fifos/    ////
////                                                             ////
/////////////////////////////////////////////////////////////////////
////                                                             ////
//// Copyright (C) 2000-2002 Rudolf Usselmann                    ////
////                         www.asics.ws                        ////
////                         rudi@asics.ws                       ////
////                                                             ////
//// This source file may be used and distributed without        ////
//// restriction provided that this copyright statement is not   ////
//// removed from the file and that any derivative work contains ////
//// the original copyright notice and the associated disclaimer.////
////                                                             ////
////     THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY     ////
//// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED   ////
//// TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS   ////
//// FOR A PARTICULAR PURPOSE. IN NO EVENT SHALL THE AUTHOR      ////
//// OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,         ////
//// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES    ////
//// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE   ////
//// GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR        ////
//// BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF  ////
//// LIABILITY, WHETHER IN  CONTRACT, STRICT LIABILITY, OR TORT  ////
//// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT  ////
//// OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         ////
//// POSSIBILITY OF SUCH DAMAGE.                                 ////
////                                                             ////
/////////////////////////////////////////////////////////////////////



//  CVS Log
//
//  $Id: generic_fifo_dc_gray.v,v 1.2 2004-01-13 09:11:55 rudi Exp $
//
//  $Date: 2004-01-13 09:11:55 $
//  $Revision: 1.2 $
//  $Author: rudi $
//  $Locker:  $
//  $State: Exp $
//
// Change History:
//               $Log: not supported by cvs2svn $
//               Revision 1.1  2003/10/14 09:34:41  rudi
//               Dual clock FIFO Gray Code encoded version.
//
//
//
//
//


`timescale 1ns / 100ps

/*

Description
===========

I/Os
----
rd_clk	Read Port Clock
wr_clk	Write Port Clock
rst	low active, either sync. or async. master reset (see below how to select)
clr	synchronous clear (just like reset but always synchronous), high active
re	read enable, synchronous, high active
we	read enable, synchronous, high active
din	Data Input
dout	Data Output

full	Indicates the FIFO is full (driven at the rising edge of wr_clk)
empty	Indicates the FIFO is empty (driven at the rising edge of rd_clk)

wr_level	indicates the FIFO level:
		2'b00	0-25%	 full
		2'b01	25-50%	 full
		2'b10	50-75%	 full
		2'b11	%75-100% full

rd_level	indicates the FIFO level:
		2'b00	0-25%	 empty
		2'b01	25-50%	 empty
		2'b10	50-75%	 empty
		2'b11	%75-100% empty

Status Timing
-------------
All status outputs are registered. They are asserted immediately
as the full/empty condition occurs, however, there is a 2 cycle
delay before they are de-asserted once the condition is not true
anymore.

Parameters
----------
The FIFO takes 2 parameters:
dw	Data bus width
aw	Address bus width (Determines the FIFO size by evaluating 2^aw)

Synthesis Results
-----------------
In a Spartan 2e a 8 bit wide, 8 entries deep FIFO, takes 97 LUTs and runs
at about 113 MHz (IO insertion disabled). 

Misc
----
This design assumes you will do appropriate status checking externally.

IMPORTANT ! writing while the FIFO is full or reading while the FIFO is
empty will place the FIFO in an undefined state.

*/


module generic_fifo_dc_gray(	rd_clk, wr_clk, rst, clr, din, we,
		dout, re, full, empty, wr_level, rd_level );

parameter dw=16;
parameter aw=8;

input			rd_clk, wr_clk, rst, clr;
input	[dw-1:0]	din;
input			we;
output	[dw-1:0]	dout;
input			re;
output			full; 
output			empty;
output	[1:0]		wr_level;
output	[1:0]		rd_level;

////////////////////////////////////////////////////////////////////
//
// Local Wires
//

reg	[aw:0]		wp_bin, wp_gray;
reg	[aw:0]		rp_bin, rp_gray;
reg	[aw:0]		wp_s, rp_s;
reg			full, empty;

wire	[aw:0]		wp_bin_next, wp_gray_next;
wire	[aw:0]		rp_bin_next, rp_gray_next;

wire	[aw:0]		wp_bin_x, rp_bin_x;
reg	[aw-1:0]	d1, d2;

reg			rd_rst, wr_rst;
reg			rd_rst_r, wr_rst_r;
reg			rd_clr, wr_clr;
reg			rd_clr_r, wr_clr_r;

////////////////////////////////////////////////////////////////////
//
// Reset Logic
//

always @(posedge rd_clk or negedge rst)
	if(!rst)	rd_rst <= 1'b0;
	else
	if(rd_rst_r)	rd_rst <= 1'b1;		// Release Reset

always @(posedge rd_clk or negedge rst)
	if(!rst)	rd_rst_r <= 1'b0;
	else		rd_rst_r <= 1'b1;

always @(posedge wr_clk or negedge rst)
	if(!rst)	wr_rst <= 1'b0;
	else
	if(wr_rst_r)	wr_rst <= 1'b1;		// Release Reset

always @(posedge wr_clk or negedge rst)
	if(!rst)	wr_rst_r <= 1'b0;
	else		wr_rst_r <= 1'b1;

always @(posedge rd_clk or posedge clr)
	if(clr)		rd_clr <= 1'b1;
	else
	if(!rd_clr_r)	rd_clr <= 1'b0;		// Release Clear

always @(posedge rd_clk or posedge clr)
	if(clr)		rd_clr_r <= 1'b1;
	else		rd_clr_r <= 1'b0;

always @(posedge wr_clk or posedge clr)
	if(clr)		wr_clr <= 1'b1;
	else
	if(!wr_clr_r)	wr_clr <= 1'b0;		// Release Clear

always @(posedge wr_clk or posedge clr)
	if(clr)		wr_clr_r <= 1'b1;
	else		wr_clr_r <= 1'b0;

////////////////////////////////////////////////////////////////////
//
// Memory Block
//

generic_dpram  #(aw,dw) u0(
	.rclk(		rd_clk		),
	.rrst(		!rd_rst		),
	.rce(		1'b1		),
	.oe(		1'b1		),
	.raddr(		rp_bin[aw-1:0]	),
	.do(		dout		),
	.wclk(		wr_clk		),
	.wrst(		!wr_rst		),
	.wce(		1'b1		),
	.we(		we		),
	.waddr(		wp_bin[aw-1:0]	),
	.di(		din		)
	);

////////////////////////////////////////////////////////////////////
//
// Read/Write Pointers Logic
//

always @(posedge wr_clk)
	if(!wr_rst)	wp_bin <= {aw+1{1'b0}};
	else
	if(wr_clr)	wp_bin <= {aw+1{1'b0}};
	else
	if(we)		wp_bin <= wp_bin_next;

always @(posedge wr_clk)
	if(!wr_rst)	wp_gray <= {aw+1{1'b0}};
	else
	if(wr_clr)	wp_gray <= {aw+1{1'b0}};
	else
	if(we)		wp_gray <= wp_gray_next;

assign wp_bin_next  = wp_bin + {{aw{1'b0}},1'b1};
assign wp_gray_next = wp_bin_next ^ {1'b0, wp_bin_next[aw:1]};

always @(posedge rd_clk)
	if(!rd_rst)	rp_bin <= {aw+1{1'b0}};
	else
	if(rd_clr)	rp_bin <= {aw+1{1'b0}};
	else
	if(re)		rp_bin <= rp_bin_next;

always @(posedge rd_clk)
	if(!rd_rst)	rp_gray <= {aw+1{1'b0}};
	else
	if(rd_clr)	rp_gray <= {aw+1{1'b0}};
	else
	if(re)		rp_gray <= rp_gray_next;

assign rp_bin_next  = rp_bin + {{aw{1'b0}},1'b1};
assign rp_gray_next = rp_bin_next ^ {1'b0, rp_bin_next[aw:1]};

////////////////////////////////////////////////////////////////////
//
// Synchronization Logic
//

// write pointer
always @(posedge rd_clk)	wp_s <= wp_gray;

// read pointer
always @(posedge wr_clk)	rp_s <= rp_gray;

////////////////////////////////////////////////////////////////////
//
// Registered Full & Empty Flags
//

assign wp_bin_x = wp_s ^ {1'b0, wp_bin_x[aw:1]};	// convert gray to binary
assign rp_bin_x = rp_s ^ {1'b0, rp_bin_x[aw:1]};	// convert gray to binary

always @(posedge rd_clk)
        empty <= (wp_s == rp_gray) | (re & (wp_s == rp_gray_next));

always @(posedge wr_clk)
        full <= ((wp_bin[aw-1:0] == rp_bin_x[aw-1:0]) & (wp_bin[aw] != rp_bin_x[aw])) |
        (we & (wp_bin_next[aw-1:0] == rp_bin_x[aw-1:0]) & (wp_bin_next[aw] != rp_bin_x[aw]));

////////////////////////////////////////////////////////////////////
//
// Registered Level Indicators
//
reg	[1:0]		wr_level;
reg	[1:0]		rd_level;
reg	[aw-1:0]	wp_bin_xr, rp_bin_xr;
reg			full_rc;
reg			full_wc;

always @(posedge wr_clk)	full_wc <= full;
always @(posedge wr_clk)	rp_bin_xr <=  ~rp_bin_x[aw-1:0] + {{aw-1{1'b0}}, 1'b1};
always @(posedge wr_clk)	d1 <= wp_bin[aw-1:0] + rp_bin_xr[aw-1:0];

always @(posedge wr_clk)	wr_level <= {d1[aw-1] | full | full_wc, d1[aw-2] | full | full_wc};

always @(posedge rd_clk)	wp_bin_xr <=  ~wp_bin_x[aw-1:0];
always @(posedge rd_clk)	d2 <= rp_bin[aw-1:0] + wp_bin_xr[aw-1:0];

always @(posedge rd_clk)	full_rc <= full;
always @(posedge rd_clk)	rd_level <= full_rc ? 2'h0 : {d2[aw-1] | empty, d2[aw-2] | empty};

////////////////////////////////////////////////////////////////////
//
// Sanity Check
//

// synopsys translate_off
always @(posedge wr_clk)
	if(we && full)
		$display("%m WARNING: Writing while fifo is FULL (%t)",$time);

always @(posedge rd_clk)
	if(re && empty)
		$display("%m WARNING: Reading while fifo is EMPTY (%t)",$time);
// synopsys translate_on

endmodule

/////////////////////////////////////////////////////////////////////
////                                                             ////
////  generic FIFO, uses LFSRs for read/write pointers           ////
////                                                             ////
////  Author: Richard Herveille                                  ////
////          richard@asics.ws                                   ////
////          www.asics.ws                                       ////
////                                                             ////
/////////////////////////////////////////////////////////////////////
////                                                             ////
//// Copyright (C) 2001, 2002 Richard Herveille                  ////
////                          richard@asics.ws                   ////
////                                                             ////
//// This source file may be used and distributed without        ////
//// restriction provided that this copyright statement is not   ////
//// removed from the file and that any derivative work contains ////
//// the original copyright notice and the associated disclaimer.////
////                                                             ////
////     THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY     ////
//// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED   ////
//// TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS   ////
//// FOR A PARTICULAR PURPOSE. IN NO EVENT SHALL THE AUTHOR      ////
//// OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,         ////
//// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES    ////
//// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE   ////
//// GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR        ////
//// BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF  ////
//// LIABILITY, WHETHER IN  CONTRACT, STRICT LIABILITY, OR TORT  ////
//// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT  ////
//// OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         ////
//// POSSIBILITY OF SUCH DAMAGE.                                 ////
////                                                             ////
/////////////////////////////////////////////////////////////////////

//
//  CVS Log
//
//  $Id: generic_fifo_lfsr.v,v 1.1 2002-10-29 19:45:07 rherveille Exp $
//
//  $Date: 2002-10-29 19:45:07 $
//  $Revision: 1.1 $
//  $Author: rherveille $
//  $Locker:  $
//  $State: Exp $
//
// Change History:
//               $Log: not supported by cvs2svn $

`timescale 1ns / 100ps

// set FIFO_RW_CHECK to prevent writing to a full and reading from an empty FIFO
//`define FIFO_RW_CHECK

// Long Pseudo Random Generators can generate (N^2 -1) combinations. This means
// 1 FIFO entry is unavailable. This might be a problem, especially for small
// FIFOs. Setting FIFO_ALL_ENTRIES creates additional logic that ensures that
// all FIFO entries are used at the expense of some additional logic.


module generic_fifo_lfsr (
	clk,
	nReset,
	rst,
	wreq,
	rreq,
	d,
	q,
	empty,
	full,
	aempty,
	afull
	);

	//
	// parameters
	//
	parameter aw =  3;                         // no.of entries (in bits; 2^7=128 entries)
	parameter dw =  8;                         // datawidth (in bits)

	//
	// inputs & outputs
	//
	input             clk;                     // master clock
	input nReset;                              // asynchronous active low reset
	input rst;                                 // synchronous active high reset

	input             wreq;                    // write request
	input             rreq;                    // read request
	input  [dw:1] d;                           // data-input
	output [dw:1] q;                           // data-output

	output            empty;                   // fifo empty
	output            full;                    // fifo full

	output            aempty;                  // fifo asynchronous/almost empty (1 entry left)
	output            afull;                   // fifo asynchronous/almost full (1 entry left)

	reg empty, full;

	//
	// Module body
	//
	reg  [aw:1] rp, wp;
	wire [dw:1] ramq;
	wire fwreq, frreq;


	function lsb;
	   input [aw:1] q;
	   case (aw)
	       2: lsb = ~q[2];
	       3: lsb = &q[aw-1:1] ^ ~(q[3] ^ q[2]);
	       4: lsb = &q[aw-1:1] ^ ~(q[4] ^ q[3]);
	       5: lsb = &q[aw-1:1] ^ ~(q[5] ^ q[3]);
	       6: lsb = &q[aw-1:1] ^ ~(q[6] ^ q[5]);
	       7: lsb = &q[aw-1:1] ^ ~(q[7] ^ q[6]);
	       8: lsb = &q[aw-1:1] ^ ~(q[8] ^ q[6] ^ q[5] ^ q[4]);
	       9: lsb = &q[aw-1:1] ^ ~(q[9] ^ q[5]);
	      10: lsb = &q[aw-1:1] ^ ~(q[10] ^ q[7]);
	      11: lsb = &q[aw-1:1] ^ ~(q[11] ^ q[9]);
	      12: lsb = &q[aw-1:1] ^ ~(q[12] ^ q[6] ^ q[4] ^ q[1]);
	      13: lsb = &q[aw-1:1] ^ ~(q[13] ^ q[4] ^ q[3] ^ q[1]);
	      14: lsb = &q[aw-1:1] ^ ~(q[14] ^ q[5] ^ q[3] ^ q[1]);
	      15: lsb = &q[aw-1:1] ^ ~(q[15] ^ q[14]);
	      16: lsb = &q[aw-1:1] ^ ~(q[16] ^ q[15] ^ q[13] ^ q[4]);
	   endcase
	endfunction



























  assign fwreq = wreq;
  assign frreq = rreq;


	// hookup read-pointer
	always @(posedge clk or negedge nReset)
	  if (~nReset)    rp <= #1 0;
	  else if (rst)   rp <= #1 0;
	  else if (frreq) rp <= #1 {rp[aw-1:1], lsb(rp)};

	// hookup write-pointer
	always @(posedge clk or negedge nReset)
	  if (~nReset)    wp <= #1 0;
	  else if (rst)   wp <= #1 0;
	  else if (fwreq) wp <= #1 {wp[aw-1:1], lsb(wp)};

	// hookup RAM-block
	generic_dpram #(aw, dw)
	fiforam (
		// write section
		.wclk(clk),
		.wrst(1'b0),
		.wce(1'b1),
		.we(fwreq),
		.waddr(wp),
		.di(d),

		// read section
		.rclk(clk),
		.rrst(1'b0),
		.rce(1'b1),
		.oe(1'b1),
		.raddr(rp),
		.do(q)
	);

	// generate full/empty signals
	assign aempty = (rp[aw-1:1] == wp[aw:2]) & (lsb(rp) == wp[1]) & frreq & ~fwreq;
	always @(posedge clk or negedge nReset)
	  if (~nReset)
	    empty <= #1 1'b1;
	  else if (rst)
	    empty <= #1 1'b1;
	  else
	    empty <= #1 aempty | (empty & (~fwreq + frreq));

	assign afull = (wp[aw-1:1] == rp[aw:2]) & (lsb(wp) == rp[1]) & fwreq & ~frreq;
	always @(posedge clk or negedge nReset)
	  if (~nReset)
	    full <= #1 1'b0;
	  else if (rst)
	    full <= #1 1'b0;
	  else
	    full <= #1 afull | ( full & (~frreq + fwreq) );

	//
	// Simulation checks
	//
	// synopsys translate_off
	always @(posedge clk)
	  if (full & fwreq)
	    $display("Writing while FIFO full\n");

	always @(posedge clk)
	  if (empty & frreq)
	    $display("Reading while FIFO empty\n");
	// synopsys translate_on
endmodule

/////////////////////////////////////////////////////////////////////
////                                                             ////
////  Universal FIFO Single Clock                                ////
////                                                             ////
////                                                             ////
////  Author: Rudolf Usselmann                                   ////
////          rudi@asics.ws                                      ////
////                                                             ////
////                                                             ////
////  D/L from: http://www.opencores.org/cores/generic_fifos/    ////
////                                                             ////
/////////////////////////////////////////////////////////////////////
////                                                             ////
//// Copyright (C) 2000-2002 Rudolf Usselmann                    ////
////                         www.asics.ws                        ////
////                         rudi@asics.ws                       ////
////                                                             ////
//// This source file may be used and distributed without        ////
//// restriction provided that this copyright statement is not   ////
//// removed from the file and that any derivative work contains ////
//// the original copyright notice and the associated disclaimer.////
////                                                             ////
////     THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY     ////
//// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED   ////
//// TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS   ////
//// FOR A PARTICULAR PURPOSE. IN NO EVENT SHALL THE AUTHOR      ////
//// OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,         ////
//// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES    ////
//// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE   ////
//// GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR        ////
//// BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF  ////
//// LIABILITY, WHETHER IN  CONTRACT, STRICT LIABILITY, OR TORT  ////
//// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT  ////
//// OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         ////
//// POSSIBILITY OF SUCH DAMAGE.                                 ////
////                                                             ////
/////////////////////////////////////////////////////////////////////

//  CVS Log
//
//  $Id: generic_fifo_sc_a.v,v 1.1.1.1 2002-09-25 05:42:06 rudi Exp $
//
//  $Date: 2002-09-25 05:42:06 $
//  $Revision: 1.1.1.1 $
//  $Author: rudi $
//  $Locker:  $
//  $State: Exp $
//
// Change History:
//               $Log: not supported by cvs2svn $
//
//
//
//
//
//
//
//
//
//

`timescale 1ns / 100ps

/*

Description
===========

I/Os
----
rst	low active, either sync. or async. master reset (see below how to select)
clr	synchronous clear (just like reset but always synchronous), high active
re	read enable, synchronous, high active
we	read enable, synchronous, high active
din	Data Input
dout	Data Output

full	Indicates the FIFO is full (combinatorial output)
full_r	same as above, but registered output (see note below)
empty	Indicates the FIFO is empty
empty_r	same as above, but registered output (see note below)

full_n		Indicates if the FIFO has space for N entries (combinatorial output)
full_n_r	same as above, but registered output (see note below)
empty_n		Indicates the FIFO has at least N entries (combinatorial output)
empty_n_r	same as above, but registered output (see note below)

level		indicates the FIFO level:
		2'b00	0-25%	 full
		2'b01	25-50%	 full
		2'b10	50-75%	 full
		2'b11	%75-100% full

combinatorial vs. registered status outputs
-------------------------------------------
Both the combinatorial and registered status outputs have exactly the same
synchronous timing. Meaning they are being asserted immediately at the clock
edge after the last read or write. The combinatorial outputs however, pass
through several levels of logic before they are output. The registered status
outputs are direct outputs of a flip-flop. The reason both are provided, is
that the registered outputs require quite a bit of additional logic inside
the FIFO. If you can meet timing of your device with the combinatorial
outputs, use them ! The FIFO will be smaller. If the status signals are
in the critical pass, use the registered outputs, they have a much smaller
output delay (actually only Tcq).

Parameters
----------
The FIFO takes 3 parameters:
dw	Data bus width
aw	Address bus width (Determines the FIFO size by evaluating 2^aw)
n	N is a second status threshold constant for full_n and empty_n
	If you have no need for the second status threshold, do not
	connect the outputs and the logic should be removed by your
	synthesis tool.

Synthesis Results
-----------------
In a Spartan 2e a 8 bit wide, 8 entries deep FIFO, takes 85 LUTs and runs
at about 116 MHz (IO insertion disabled). The registered status outputs
are valid after 2.1NS, the combinatorial once take out to 6.5 NS to be
available.


Misc
----
This design assumes you will do appropriate status checking externally.

IMPORTANT ! writing while the FIFO is full or reading while the FIFO is
empty will place the FIFO in an undefined state.

*/


// Selecting Sync. or Async Reset
// ------------------------------
// Uncomment one of the two lines below. The first line for
// synchronous reset, the second for asynchronous reset


//`define SC_FIFO_ASYNC_RESET	or negedge rst		// Uncomment for Async. reset


module generic_fifo_sc_a(clk, rst, clr, din, we, dout, re,
			full, empty, full_r, empty_r,
			full_n, empty_n, full_n_r, empty_n_r,
			level);

parameter dw=8;
parameter aw=8;
parameter n=32;
parameter max_size = 1<<aw;

input			clk, rst, clr;
input	[dw-1:0]	din;
input			we;
output	[dw-1:0]	dout;
input			re;
output			full, full_r;
output			empty, empty_r;
output			full_n, full_n_r;
output			empty_n, empty_n_r;
output	[1:0]		level;

////////////////////////////////////////////////////////////////////
//
// Local Wires
//

reg	[aw-1:0]	wp;
wire	[aw-1:0]	wp_pl1;
wire	[aw-1:0]	wp_pl2;
reg	[aw-1:0]	rp;
wire	[aw-1:0]	rp_pl1;
reg			full_r;
reg			empty_r;
reg			gb;
reg			gb2;
reg	[aw:0]		cnt;
wire			full_n, empty_n;
reg			full_n_r, empty_n_r;

////////////////////////////////////////////////////////////////////
//
// Memory Block
//

generic_dpram  #(aw,dw) u0(
	.rclk(		clk		),
	.rrst(		!rst		),
	.rce(		1'b1		),
	.oe(		1'b1		),
	.raddr(		rp		),
	.do(		dout		),
	.wclk(		clk		),
	.wrst(		!rst		),
	.wce(		1'b1		),
	.we(		we		),
	.waddr(		wp		),
	.di(		din		)
	);

////////////////////////////////////////////////////////////////////
//
// Misc Logic
//

always @(posedge clk )
	if(!rst)	wp <= #1 {aw{1'b0}};
	else
	if(clr)		wp <= #1 {aw{1'b0}};
	else
	if(we)		wp <= #1 wp_pl1;

assign wp_pl1 = wp + { {aw-1{1'b0}}, 1'b1};
assign wp_pl2 = wp + { {aw-2{1'b0}}, 2'b10};

always @(posedge clk )
	if(!rst)	rp <= #1 {aw{1'b0}};
	else
	if(clr)		rp <= #1 {aw{1'b0}};
	else
	if(re)		rp <= #1 rp_pl1;

assign rp_pl1 = rp + { {aw-1{1'b0}}, 1'b1};

////////////////////////////////////////////////////////////////////
//
// Combinatorial Full & Empty Flags
//

assign empty = ((wp == rp) & !gb);
assign full  = ((wp == rp) &  gb);

// Guard Bit ...
always @(posedge clk )
	if(!rst)			gb <= #1 1'b0;
	else
	if(clr)				gb <= #1 1'b0;
	else
	if((wp_pl1 == rp) & we)		gb <= #1 1'b1;
	else
	if(re)				gb <= #1 1'b0;

////////////////////////////////////////////////////////////////////
//
// Registered Full & Empty Flags
//

// Guard Bit ...
always @(posedge clk )
	if(!rst)			gb2 <= #1 1'b0;
	else
	if(clr)				gb2 <= #1 1'b0;
	else
	if((wp_pl2 == rp) & we)		gb2 <= #1 1'b1;
	else
	if((wp != rp) & re)		gb2 <= #1 1'b0;

always @(posedge clk )
	if(!rst)				full_r <= #1 1'b0;
	else
	if(clr)					full_r <= #1 1'b0;
	else
	if(we & ((wp_pl1 == rp) & gb2) & !re)	full_r <= #1 1'b1;
	else
	if(re & ((wp_pl1 != rp) | !gb2) & !we)	full_r <= #1 1'b0;

always @(posedge clk )
	if(!rst)				empty_r <= #1 1'b1;
	else
	if(clr)					empty_r <= #1 1'b1;
	else
	if(we & ((wp != rp_pl1) | gb2) & !re)	empty_r <= #1 1'b0;
	else
	if(re & ((wp == rp_pl1) & !gb2) & !we)	empty_r <= #1 1'b1;

////////////////////////////////////////////////////////////////////
//
// Combinatorial Full_n & Empty_n Flags
//

assign empty_n = cnt < n;
assign full_n  = !(cnt < (max_size-n+1));
assign level = {2{cnt[aw]}} | cnt[aw-1:aw-2];

// N entries status
always @(posedge clk )
	if(!rst)	cnt <= #1 {aw+1{1'b0}};
	else
	if(clr)		cnt <= #1 {aw+1{1'b0}};
	else
	if( re & !we)	cnt <= #1 cnt + { {aw{1'b1}}, 1'b1};
	else
	if(!re &  we)	cnt <= #1 cnt + { {aw{1'b0}}, 1'b1};

////////////////////////////////////////////////////////////////////
//
// Registered Full_n & Empty_n Flags
//

always @(posedge clk )
	if(!rst)				empty_n_r <= #1 1'b1;
	else
	if(clr)					empty_n_r <= #1 1'b1;
	else
	if(we & (cnt >= (n-1) ) & !re)		empty_n_r <= #1 1'b0;
	else
	if(re & (cnt <= n ) & !we)		empty_n_r <= #1 1'b1;

always @(posedge clk )
	if(!rst)				full_n_r <= #1 1'b0;
	else
	if(clr)					full_n_r <= #1 1'b0;
	else
	if(we & (cnt >= (max_size-n) ) & !re)	full_n_r <= #1 1'b1;
	else
	if(re & (cnt <= (max_size-n+1)) & !we)	full_n_r <= #1 1'b0;

////////////////////////////////////////////////////////////////////
//
// Sanity Check
//

// synopsys translate_off
always @(posedge clk)
	if(we & full)
		$display("%m WARNING: Writing while fifo is FULL (%t)",$time);

always @(posedge clk)
	if(re & empty)
		$display("%m WARNING: Reading while fifo is EMPTY (%t)",$time);
// synopsys translate_on

endmodule

/////////////////////////////////////////////////////////////////////
////                                                             ////
////  Universal FIFO Single Clock                                ////
////                                                             ////
////                                                             ////
////  Author: Rudolf Usselmann                                   ////
////          rudi@asics.ws                                      ////
////                                                             ////
////                                                             ////
////  D/L from: http://www.opencores.org/cores/generic_fifos/    ////
////                                                             ////
/////////////////////////////////////////////////////////////////////
////                                                             ////
//// Copyright (C) 2000-2002 Rudolf Usselmann                    ////
////                         www.asics.ws                        ////
////                         rudi@asics.ws                       ////
////                                                             ////
//// This source file may be used and distributed without        ////
//// restriction provided that this copyright statement is not   ////
//// removed from the file and that any derivative work contains ////
//// the original copyright notice and the associated disclaimer.////
////                                                             ////
////     THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY     ////
//// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED   ////
//// TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS   ////
//// FOR A PARTICULAR PURPOSE. IN NO EVENT SHALL THE AUTHOR      ////
//// OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,         ////
//// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES    ////
//// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE   ////
//// GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR        ////
//// BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF  ////
//// LIABILITY, WHETHER IN  CONTRACT, STRICT LIABILITY, OR TORT  ////
//// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT  ////
//// OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         ////
//// POSSIBILITY OF SUCH DAMAGE.                                 ////
////                                                             ////
/////////////////////////////////////////////////////////////////////

//  CVS Log
//
//  $Id: generic_fifo_sc_b.v,v 1.1.1.1 2002-09-25 05:42:04 rudi Exp $
//
//  $Date: 2002-09-25 05:42:04 $
//  $Revision: 1.1.1.1 $
//  $Author: rudi $
//  $Locker:  $
//  $State: Exp $
//
// Change History:
//               $Log: not supported by cvs2svn $
//
//
//
//
//
//
//
//
//
//

`timescale 1ns / 100ps

/*

Description
===========

I/Os
----
rst	low active, either sync. or async. master reset (see below how to select)
clr	synchronous clear (just like reset but always synchronous), high active
re	read enable, synchronous, high active
we	read enable, synchronous, high active
din	Data Input
dout	Data Output

full	Indicates the FIFO is full (combinatorial output)
full_r	same as above, but registered output (see note below)
empty	Indicates the FIFO is empty
empty_r	same as above, but registered output (see note below)

full_n		Indicates if the FIFO has space for N entries (combinatorial output)
full_n_r	same as above, but registered output (see note below)
empty_n		Indicates the FIFO has at least N entries (combinatorial output)
empty_n_r	same as above, but registered output (see note below)

level		indicates the FIFO level:
		2'b00	0-25%	 full
		2'b01	25-50%	 full
		2'b10	50-75%	 full
		2'b11	%75-100% full

combinatorial vs. registered status outputs
-------------------------------------------
Both the combinatorial and registered status outputs have the same
basic functionality. The registered outputs are de-asserted with a
1 cycle delay for full_r and empty_r, and a 2 cycle delay for full_n_r
and empty_n_r.
The combinatorial outputs however, pass through several levels of
logic before they are output. The registered status outputs are
direct outputs of a flip-flop. The reason both are provided, is
that the registered outputs require additional logic inside the
FIFO. If you can meet timing of your device with the combinatorial
outputs, use them ! The FIFO will be smaller. If the status signals
are in the critical pass, use the registered outputs, they have a
much smaller output delay (actually only Tcq).

Parameters
----------
The FIFO takes 3 parameters:
dw	Data bus width
aw	Address bus width (Determines the FIFO size by evaluating 2^aw)
n	N is a second status threshold constant for full_n and empty_n
	If you have no need for the second status threshold, do not
	connect the outputs and the logic should be removed by your
	synthesis tool.

Synthesis Results
-----------------
In a Spartan 2e a 8 bit wide, 8 entries deep FIFO, takes 85 LUTs and runs
at about 116 MHz (IO insertion disabled). The registered status outputs
are valid after 2.1NS, the combinatorial once take out to 6.5 NS to be
available.


Misc
----
This design assumes you will do appropriate status checking externally.

IMPORTANT ! writing while the FIFO is full or reading while the FIFO is
empty will place the FIFO in an undefined state.

*/


// Selecting Sync. or Async Reset
// ------------------------------
// Uncomment one of the two lines below. The first line for
// synchronous reset, the second for asynchronous reset


//`define SC_FIFO_ASYNC_RESET	or negedge rst		// Uncomment for Async. reset


module generic_fifo_sc_b(clk, rst, clr, din, we, dout, re,
			full, empty, full_r, empty_r,
			full_n, empty_n, full_n_r, empty_n_r,
			level);

parameter dw=8;
parameter aw=8;
parameter n=32;
parameter max_size = 1<<aw;

input			clk, rst, clr;
input	[dw-1:0]	din;
input			we;
output	[dw-1:0]	dout;
input			re;
output			full, full_r;
output			empty, empty_r;
output			full_n, full_n_r;
output			empty_n, empty_n_r;
output	[1:0]		level;

////////////////////////////////////////////////////////////////////
//
// Local Wires
//

reg	[aw:0]	wp;
wire	[aw:0]	wp_pl1;
reg	[aw:0]	rp;
wire	[aw:0]	rp_pl1;
reg		full_r;
reg		empty_r;
wire	[aw:0]	diff;
reg	[aw:0]	diff_r;
reg		re_r, we_r;
wire		full_n, empty_n;
reg		full_n_r, empty_n_r;
reg	[1:0]	level;

////////////////////////////////////////////////////////////////////
//
// Memory Block
//

generic_dpram  #(aw,dw) u0(
	.rclk(		clk		),
	.rrst(		!rst		),
	.rce(		1'b1		),
	.oe(		1'b1		),
	.raddr(		rp[aw-1:0]	),
	.do(		dout		),
	.wclk(		clk		),
	.wrst(		!rst		),
	.wce(		1'b1		),
	.we(		we		),
	.waddr(		wp[aw-1:0]	),
	.di(		din		)
	);

////////////////////////////////////////////////////////////////////
//
// Misc Logic
//

always @(posedge clk )
	if(!rst)	wp <= #1 {aw+1{1'b0}};
	else
	if(clr)		wp <= #1 {aw+1{1'b0}};
	else
	if(we)		wp <= #1 wp_pl1;

assign wp_pl1 = wp + { {aw{1'b0}}, 1'b1};

always @(posedge clk )
	if(!rst)	rp <= #1 {aw+1{1'b0}};
	else
	if(clr)		rp <= #1 {aw+1{1'b0}};
	else
	if(re)		rp <= #1 rp_pl1;

assign rp_pl1 = rp + { {aw{1'b0}}, 1'b1};

////////////////////////////////////////////////////////////////////
//
// Combinatorial Full & Empty Flags
//

assign empty = (wp == rp);
assign full  = (wp[aw-1:0] == rp[aw-1:0]) & (wp[aw] != rp[aw]);

////////////////////////////////////////////////////////////////////
//
// Registered Full & Empty Flags
//

always @(posedge clk)
	empty_r <= #1 (wp == rp) | (re & (wp == rp_pl1));

always @(posedge clk)
	full_r <= #1 ((wp[aw-1:0] == rp[aw-1:0]) & (wp[aw] != rp[aw])) |
	(we & (wp_pl1[aw-1:0] == rp[aw-1:0]) & (wp_pl1[aw] != rp[aw]));

////////////////////////////////////////////////////////////////////
//
// Combinatorial Full_n & Empty_n Flags
//

assign diff = wp-rp;
assign empty_n = diff < n;
assign full_n  = !(diff < (max_size-n+1));

always @(posedge clk)
	level <= #1 {2{diff[aw]}} | diff[aw-1:aw-2];

////////////////////////////////////////////////////////////////////
//
// Registered Full_n & Empty_n Flags
//

always @(posedge clk)
	re_r <= #1 re;

always @(posedge clk)
	diff_r <= #1 diff;

always @(posedge clk)
	empty_n_r <= #1 (diff_r < n) | ((diff_r==n) & (re | re_r));

always @(posedge clk)
	we_r <= #1 we;

always @(posedge clk)
	full_n_r <= #1 (diff_r > max_size-n) | ((diff_r==max_size-n) & (we | we_r));

////////////////////////////////////////////////////////////////////
//
// Sanity Check
//

// synopsys translate_off
always @(posedge clk)
	if(we & full)
		$display("%m WARNING: Writing while fifo is FULL (%t)",$time);

always @(posedge clk)
	if(re & empty)
		$display("%m WARNING: Reading while fifo is EMPTY (%t)",$time);
// synopsys translate_on

endmodule

/////////////////////////////////////////////////////////////////////
////                                                             ////
////  Linear Feedback Shift Register                             ////
////                                                             ////
////  Author: Richard Herveille                                  ////
////          richard@asics.ws                                   ////
////          www.asics.ws                                       ////
////                                                             ////
/////////////////////////////////////////////////////////////////////
////                                                             ////
//// Copyright (C) 2001, 2002 Richard Herveille                  ////
////                          richard@asics.ws                   ////
////                                                             ////
//// This source file may be used and distributed without        ////
//// restriction provided that this copyright statement is not   ////
//// removed from the file and that any derivative work contains ////
//// the original copyright notice and the associated disclaimer.////
////                                                             ////
////     THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY     ////
//// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED   ////
//// TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS   ////
//// FOR A PARTICULAR PURPOSE. IN NO EVENT SHALL THE AUTHOR      ////
//// OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,         ////
//// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES    ////
//// (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE   ////
//// GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR        ////
//// BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF  ////
//// LIABILITY, WHETHER IN  CONTRACT, STRICT LIABILITY, OR TORT  ////
//// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT  ////
//// OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         ////
//// POSSIBILITY OF SUCH DAMAGE.                                 ////
////                                                             ////
/////////////////////////////////////////////////////////////////////

//
//  CVS Log
//
//  $Id: lfsr.v,v 1.1 2002-10-29 19:45:07 rherveille Exp $
//
//  $Date: 2002-10-29 19:45:07 $
//  $Revision: 1.1 $
//  $Author: rherveille $
//  $Locker:  $
//  $State: Exp $
//
// Change History:
//               $Log: not supported by cvs2svn $

`timescale 1ns / 100ps



