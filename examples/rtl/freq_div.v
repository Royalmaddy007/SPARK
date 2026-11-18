


module divider(in, out, N, reset);

	input in;				// input clock
	input [6-1:0] N;	// the number to be divided by
	input reset;			// asynchronous reset
	output out;				// divided output clock
	
	wire out_odd;			// output of odd divider
	wire out_even;			// output of even divider
	wire not_zero;			// signal to find divide by 0 case
	wire enable_even;		// enable of even divider
	wire enable_odd;		// enable of odd divider

	assign not_zero = | N[6-1:1];

	assign out = (out_odd & N[0] & not_zero) | (out_even & !N[0]);
	//assign out = out_odd | out_even;
	assign enable_odd = N[0] & not_zero;
	assign enable_even = !N[0];

	// Even divider
	even even_0(in, out_even, N, reset, not_zero, enable_even);
	// Odd divider
	odd odd_0(in, out_odd, N, reset, enable_odd);
	
endmodule //divider



module even(clk, out, N, reset, not_zero, enable);

	input clk;				// fast input clock
	output out;				// slower divided clock
	input [6-1:0] N;	// divide by factor 'N'
	input reset;			// asynchronous reset
	input not_zero;			// if !not_zero divide by 1
	input enable;			// enable the even divider

	reg [6-1:0] counter;
	reg out_counter;
	wire [6-1:0] div_2;


	// if N=0 just output the clock, otherwise, divide it.
	assign out = (clk & !not_zero) | (out_counter & not_zero);
	assign div_2 = {1'b0, N[6-1:1]};

	// simple flip-flop even divider
	always @(posedge reset or posedge clk)
	begin
		if(reset)						// asynch. reset
		begin
			counter <= 1;
			out_counter <= 1;
		end
		else if(enable)					// only use switching power if enabled
		begin
			if(counter == 1)			// divide after counter has reached bottom
			begin						// of interval 'N' which will be value '1'
				counter <= div_2;
				out_counter <= ~out_counter;
			end
			else
			begin						// decrement the counter and wait
				counter <= counter-1;	// to start next trasition.
			end
		end
	end

endmodule //even



module odd(clk, out, N, reset, enable);

	input clk;					// slow clock
	output out;					// fast output clock
	input [6-1:0] N;		// division factor
	input reset;				// synchronous reset
	input enable;				// odd enable

	reg [6-1:0] counter;	// these 2 counters are used
	reg [6-1:0] counter2;	// to non-overlapping signals
	reg out_counter;			// positive edge triggered counter
	reg out_counter2;			// negative edge triggered counter
	reg rst_pulse;				// pulse generated when vector N changes
	reg [6-1:0] old_N;		// gets set to old N when N is changed
	wire not_zero;				// if !not_zero, we devide by 1

	assign out = out_counter2 ^ out_counter;	// xor to generate 50% duty, half-period
												// waves of final output
	// positive edge counter/divider
	always @(posedge clk)
	begin
		if(reset | rst_pulse)
		begin
			counter <= N;
			out_counter <= 1;
		end
		else if (enable)
		begin
			if(counter == 1)
			begin
				counter <= N;
				out_counter <= ~out_counter;
			end
			else
			begin
				counter <= counter - 1'b1;
			end
		end
	end

	reg [6-1:0] initial_begin;		// this is used to offset the negative edge counter
	wire [6:0] interm_3;			// from the positive edge counter in order to
	assign interm_3 = {1'b0,N} + 2'b11;		// guarante 50% duty cycle.

	// counter driven by negative edge of clock.
	always @(negedge clk)
	begin
		if(reset | rst_pulse)						// reset the counter at system reset
		begin										// or change of N.
			counter2 <= N;
			initial_begin <= interm_3[6:1];
			out_counter2 <= 1;
		end
		else if(initial_begin <= 1 && enable)		// Do normal logic after odd calibration.
		begin										// This is the same as the even counter.
			if(counter2 == 1)
			begin
				counter2 <= N;
				out_counter2 <= ~out_counter2;
			end
			else
			begin
				counter2 <= counter2 - 1'b1;
			end
		end
		else if(enable)
		begin
			initial_begin <= initial_begin - 1'b1;
		end
	end

	//
	// reset pulse generator:
	//               __    __    __    __    _
	// clk:       __/  \__/  \__/  \__/  \__/
	//            _ __________________________
	// N:         _X__________________________
	//               _____
	// rst_pulse: __/     \___________________
	//
	// This block generates an internal reset for the odd divider in the
	// form of a single pulse signal when the odd divider is enabled.
	always @(posedge clk or posedge reset)
	begin
		if(reset)
		begin
			rst_pulse <= 0;
		end
		else if(enable)
		begin
			if(N != old_N)		// pulse when reset changes
			begin
				rst_pulse <= 1;
			end
			else
			begin
				rst_pulse <= 0;
			end
		end
	end

	always @(posedge clk)
	begin
		old_N <= N;	// always save the old N value to guarante reset from
	end				// an even-to-odd transition.

endmodule //odd
