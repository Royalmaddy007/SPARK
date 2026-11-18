/**************************************
Author: J.W Tang
Email: jaytang1987@hotmail.com
Module: LinkRunCCA
Date: 2016-04-24
Description: Top level of LinkRunCCA Hardware Module.

Copyright (C) 2016 J.W. Tang
----------------------------
This file is part of LinkRunCCA.

LinkRunCCA is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

LinkRunCCA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with LinkRunCCA. If not, see <http://www.gnu.org/licenses/>.

By using LinkRunCCA in any or associated publication,
you agree to cite it as: 
Tang, J. W., et al. "A linked list run-length-based single-pass
connected component analysis for real-time embedded hardware."
Journal of Real-Time Image Processing: 1-19. 2016.
doi:10.1007/s11554-016-0590-2.  

***************************************/

module LinkRunCCA(clk,rst,datavalid,pix_in,datavalid_out,box_out);

parameter imwidth=512;
parameter imheight=512;
//parameters file

parameter x_bit=$clog2(imwidth); 
parameter y_bit=$clog2(imheight);
parameter address_bit=x_bit-1;
parameter data_bit=2*(x_bit+y_bit);
parameter latency=3; //latency is 3 with holes_filler

input clk,rst,datavalid,pix_in;
output reg datavalid_out;
output reg [data_bit-1:0]box_out;

//rams' wires
wire [address_bit-1:0]n_waddr,n_wdata,n_raddr,n_rdata;
wire [address_bit-1:0]h_waddr,h_wdata,h_raddr,h_rdata;
wire [address_bit-1:0]t_waddr,t_wdata,t_raddr,t_rdata;
wire [address_bit-1:0]d_raddr,d_waddr;
wire [data_bit-1:0] d_rdata,d_wdata;
wire n_we,h_we,t_we,d_we;

//connection wires
wire A,B,C,D,r1,r2,fp,fn,O,HCN,DAC,DMG,CLR,EOC;
wire [address_bit-1:0]p,hp,tp,np;
wire [data_bit-1:0]d,dp;
wire left,hr1,hf_out;


//tables
table_ram#(address_bit,address_bit)
	Next_Table(clk,n_we&datavalid,n_waddr,n_wdata,n_raddr,n_rdata);
table_ram#(address_bit,address_bit)
	Head_Table(clk,h_we&datavalid,h_waddr,h_wdata,h_raddr,h_rdata);
table_ram#(address_bit,address_bit)
	Tail_Table(clk,t_we&datavalid,t_waddr,t_wdata,t_raddr,t_rdata);
table_ram#(data_bit,address_bit)
	Data_Table(clk,d_we&datavalid,d_waddr,d_wdata,d_raddr,d_rdata);

//holes filler
holes_filler HF(clk,datavalid,pix_in,hr1,left,hf_out);
row_buf#(imwidth-2) RBHF(clk,datavalid,left,hr1);



//window & row buffer
window WIN(clk,datavalid,hf_out,r1,A,B,C,D);
row_buf#(imwidth-2) RB(clk,datavalid,C,r1,r2);

//table reader
table_reader#(address_bit,data_bit) TR(
	clk,rst,datavalid, //global input
	A,B,r1,r2,d,O,HCN, //input from other modules
	d_we,d_waddr,h_rdata,t_rdata,n_rdata,d_rdata,h_wdata,t_wdata, //input from table
	h_raddr,t_raddr,n_raddr,d_raddr, //output to table
	p,hp,np,tp,dp,fp,fn //output to others module
);

//equivalence resolver
equivalence_resolver#(address_bit,data_bit) ES(
	clk,rst,datavalid, //global input
	A,B,C,D,p,hp,np,tp,dp,fp,fn,d, //input from other modules
	h_we,t_we,n_we,d_we, //output to table (write enable)
	h_waddr,t_waddr,n_waddr,d_waddr, //output to table (write address)
	h_wdata,t_wdata,n_wdata,d_wdata, //output to table (write data)
	HCN,DAC,DMG,CLR,EOC,O //output to other modules
);


//feature accumulator
feature_accumulator#(
	.imwidth(imwidth),
	.imheight(imheight),
	.x_bit(x_bit),
	.y_bit(y_bit),
	.address_bit(address_bit),
	.data_bit(data_bit),
	.latency(latency)
	)
	FA(
	clk,rst,datavalid,DAC,DMG,CLR,dp,d
);


//registered data output
always@(posedge clk or posedge rst)
	if(rst)begin
		datavalid_out<=0;
	end
	else if(datavalid)begin
		datavalid_out<=0;
		box_out<=dp;
		if(EOC)
			datavalid_out<=1;
	end

endmodule
/**************************************
Author: J.W Tang
Email: jaytang1987@hotmail.com
Module: equivalence_resolver
Date: 2016-04-24

Copyright (C) 2016 J.W. Tang
----------------------------
This file is part of LinkRunCCA.

LinkRunCCA is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

LinkRunCCA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with LinkRunCCA. If not, see <http://www.gnu.org/licenses/>.

By using LinkRunCCA in any or associated publication,
you agree to cite it as: 
Tang, J. W., et al. "A linked list run-length-based single-pass
connected component analysis for real-time embedded hardware."
Journal of Real-Time Image Processing: 1-19. 2016.
doi:10.1007/s11554-016-0590-2. 

***************************************/

module equivalence_resolver(
	clk,rst,datavalid, //global input
	A,B,C,D,p,hp,np,tp,dp,fp,fn,dd, //input from other modules
	h_we,t_we,n_we,d_we, //output to table (write enable)
	h_waddr,t_waddr,n_waddr,d_waddr, //output to table (write address)
	h_wdata,t_wdata,n_wdata,d_wdata, //output to table (write data)
	HCN,DAC,DMG,CLR,EOC,O //output to other modules
);
parameter address_bit=9;
parameter data_bit=38;

input clk,rst,datavalid,A,B,C,D,fp,fn;
input [address_bit-1:0]p,hp,np,tp;
input [data_bit-1:0]dp,dd;

output reg h_we,t_we,n_we,d_we;
output reg[address_bit-1:0]h_waddr,t_waddr,n_waddr,d_waddr;
output reg[address_bit-1:0]h_wdata,t_wdata,n_wdata;
output reg[data_bit-1:0]d_wdata;
output HCN,DAC,DMG,CLR,O;
output reg EOC;

reg [address_bit-1:0]cc,h;
reg f,HBF;
wire Ec,Ep;

assign DMG=O&~(f&hp==h);
assign DAC=D;

/////events
assign Ec=(C&~D);
assign Ep=(A&~B);
assign O=(B&D&(~A|~C));
assign CLR=Ec;
assign HCN=HBF&(np==p);


////cache cc,h,f
always@(posedge clk or posedge rst)
	if(rst)begin
		cc<=0;h<=0;f<=0;
	end
	else if(datavalid)
		if(Ec)begin
			cc<=cc+1; //INC
			f<=0;	//CLR
		end
		else if(O)begin
			h<=h_wdata;f<=1; //ET1,ET2,ET3
		end

/////table update
always@*begin
	h_we=0;h_waddr={address_bit{1'bx}};h_wdata={address_bit{1'bx}};
	t_we=0;t_waddr={address_bit{1'bx}};t_wdata={address_bit{1'bx}};
	n_we=0;n_waddr={address_bit{1'bx}};n_wdata={address_bit{1'bx}};
	d_we=0;d_waddr={address_bit{1'bx}};d_wdata={data_bit{1'bx}};
	EOC=0;HBF=0;
	if(Ec)begin
		n_we=1;n_waddr=cc;n_wdata=cc; //CLR
		h_we=1;h_waddr=cc;h_wdata=cc; //CLR
		case(f)
		0:begin d_we=1;d_waddr=cc;d_wdata=dd;end	//DUC
		1:begin d_we=1;d_waddr=h;d_wdata=dd;end	//DUH
		endcase
	end
	else if(Ep)begin
		case(fp)
		0:begin	d_we=1;d_waddr=np;d_wdata=dp; //DBF
			if(fn)EOC=1;	end	  //EOC
		1:begin	h_we=1;h_waddr=np;h_wdata=hp;HBF=1;end	//HBF
		endcase
	end
	else if(O)
		case({f,fp})
		2'b00:begin
			h_we=1;h_waddr=np;h_wdata=cc;	//ET1
			t_we=1;t_waddr=h_wdata;t_wdata=cc;
		end
		2'b01:begin
			h_we=1;h_waddr=np;h_wdata=hp;	//ET3
			t_we=1;t_waddr=h_wdata;t_wdata=cc;
			n_we=1;n_waddr=tp;n_wdata=cc;	//EM1
		end
		2'b10:begin
			h_we=1;h_waddr=np;h_wdata=h;	//ET2
			t_we=1;t_waddr=h_wdata;t_wdata=cc;
		end
		2'b11:begin
			h_we=1;h_waddr=np;h_wdata=hp;	//ET3
			t_we=1;t_waddr=h_wdata;t_wdata=cc;
			n_we=1;n_waddr=tp;n_wdata=h;	//EM2
		end
		endcase
end


endmodule

/**************************************
Author: J.W Tang
Email: jaytang1987@hotmail.com
Module: feature_accumulator
Date: 2016-04-24

Copyright (C) 2016 J.W. Tang
----------------------------
This file is part of LinkRunCCA.

LinkRunCCA is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

LinkRunCCA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with LinkRunCCA. If not, see <http://www.gnu.org/licenses/>.

By using LinkRunCCA in any or associated publication,
you agree to cite it as: 
Tang, J. W., et al. "A linked list run-length-based single-pass
connected component analysis for real-time embedded hardware."
Journal of Real-Time Image Processing: 1-19. 2016.
doi:10.1007/s11554-016-0590-2. 

***************************************/

module feature_accumulator(
	clk,rst,datavalid,DAC,DMG,CLR,dp,d
);

parameter imwidth=512;
parameter imheight=512;
parameter x_bit=9;
parameter y_bit=9;
parameter address_bit=8;
parameter data_bit=38;
parameter latency=3; //latency to offset counter x, 3 if holes filling, else 1
parameter rstx=imwidth-latency;
parameter rsty=imheight-1;
parameter compx=imwidth-1;
input clk,rst,datavalid,DAC,DMG,CLR;
input [data_bit-1:0]dp;
output reg[data_bit-1:0]d;

////coordinate counter
reg [x_bit-1:0]x;
reg [y_bit-1:0]y;
always@(posedge clk or posedge rst)
	if(rst)begin 
		x<=rstx[x_bit-1:0];y<=rsty[y_bit-1:0];
	end
	else if(datavalid)begin
		if(x==compx[x_bit-1:0])begin
			x<=0;
			if(y==rsty[y_bit-1:0])
				y<=0;
			else y<=y+1;
		end
		else x<=x+1;
	end

/////register d
wire [x_bit-1:0]minx,maxx,minx1,maxx1;
wire [y_bit-1:0]miny,maxy,miny1,maxy1;
//data accumulate
assign minx1=(DAC&(x<d[data_bit-1:data_bit-x_bit]))?x:d[data_bit-1:data_bit-x_bit];
assign maxx1=(DAC&(x>d[data_bit-x_bit-1:2*y_bit]))?x:d[data_bit-x_bit-1:2*y_bit];
assign miny1=(DAC&(y<d[2*y_bit-1:y_bit]))?y:d[2*y_bit-1:y_bit];
assign maxy1=(DAC&(y>d[y_bit-1:0]))?y:d[y_bit-1:0];
//data merge
assign minx=(DMG&(dp[data_bit-1:data_bit-x_bit]<minx1))?dp[data_bit-1:data_bit-x_bit]:minx1;
assign maxx=(DMG&(dp[data_bit-x_bit-1:2*y_bit]>maxx1))?dp[data_bit-x_bit-1:2*y_bit]:maxx1;
assign miny=(DMG&(dp[2*y_bit-1:y_bit]<miny1))?dp[2*y_bit-1:y_bit]:miny1;
assign maxy=(DMG&(dp[y_bit-1:0]>maxy1))?dp[y_bit-1:0]:maxy1;

always@(posedge clk or posedge rst)
	if(rst)
		d<={{x_bit{1'b1}},{x_bit{1'b0}},{y_bit{1'b1}},{y_bit{1'b0}}};
	else if(datavalid)
		if(CLR)
			d<={{x_bit{1'b1}},{x_bit{1'b0}},{y_bit{1'b1}},{y_bit{1'b0}}}; //CLR
		else d<={minx,maxx,miny,maxy};

endmodule
/**************************************
Author: J.W Tang
Email: jaytang1987@hotmail.com
Module: holes_filler
Date: 2016-04-24

Copyright (C) 2016 J.W. Tang
----------------------------
This file is part of LinkRunCCA.

LinkRunCCA is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

LinkRunCCA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with LinkRunCCA. If not, see <http://www.gnu.org/licenses/>.

By using LinkRunCCA in any or associated publication,
you agree to cite it as: 
Tang, J. W., et al. "A linked list run-length-based single-pass
connected component analysis for real-time embedded hardware."
Journal of Real-Time Image Processing: 1-19. 2016.
doi:10.1007/s11554-016-0590-2. 

***************************************/

module holes_filler(clk,datavalid,pix_in_current,pix_in_previous,left,pix_out);

input clk,datavalid,pix_in_current,pix_in_previous;
output reg left;
output pix_out;

reg top,x,right;


//window
always@(posedge clk)
	if(datavalid)begin
		top<=pix_in_previous;
		left<=x;x<=right;right<=pix_in_current;
	end

assign pix_out=(top&(left|right))?1'd1:x;


endmodule
/**************************************
Author: J.W Tang
Email: jaytang1987@hotmail.com
Module: row_buf
Date: 2016-04-24

Copyright (C) 2016 J.W. Tang
----------------------------
This file is part of LinkRunCCA.

LinkRunCCA is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

LinkRunCCA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with LinkRunCCA. If not, see <http://www.gnu.org/licenses/>.

By using LinkRunCCA in any or associated publication,
you agree to cite it as: 
Tang, J. W., et al. "A linked list run-length-based single-pass
connected component analysis for real-time embedded hardware."
Journal of Real-Time Image Processing: 1-19. 2016.
doi:10.1007/s11554-016-0590-2.  

***************************************/

module row_buf(clk,datavalid,pix_in,pix_out1,pix_out2);
parameter length=640;

input clk,datavalid,pix_in;
output pix_out1,pix_out2;

reg [length-1:0] R;
//reg R[0:length-1];

always@(posedge clk)begin
	if(datavalid)begin
		R[length-1:1]<=R[length-2:0];
		R[0]<=pix_in;
	end
end
assign pix_out1=R[length-1];
assign pix_out2=R[length-2];
	
endmodule
// Quartus II Verilog Template
// Simple Dual Port RAM with separate read/write addresses and
// single read/write clock
/* verilator lint_off BLKSEQ */

module table_ram
#(parameter DATA_WIDTH=8, parameter ADDR_WIDTH=10)
(	clk,we,write_addr,data,read_addr,q);

	input [(DATA_WIDTH-1):0] data;
	input [(ADDR_WIDTH-1):0] read_addr, write_addr;
	input we, clk;
	output [(DATA_WIDTH-1):0] q;

	// Declare the RAM variable
	reg [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH-1:0];
	reg [(ADDR_WIDTH-1):0] read_addr_reg;
	always @ (posedge clk)
	begin
	
		read_addr_reg=read_addr;
		// Write
		if (we)
			ram[write_addr] = data;

	end
	assign q= ram[read_addr_reg];
endmodule


/**************************************
Author: J.W Tang
Email: jaytang1987@hotmail.com
Module: table_reader
Date: 2016-04-24

Copyright (C) 2016 J.W. Tang
----------------------------
This file is part of LinkRunCCA.

LinkRunCCA is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

LinkRunCCA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with LinkRunCCA. If not, see <http://www.gnu.org/licenses/>.

By using this component in any associated publication,
you agree to cite it as: 
Tang, J. W., et al. "A linked list run-length-based single-pass
connected component analysis for real-time embedded hardware."
Journal of Real-Time Image Processing: 1-19. 2016.
doi:10.1007/s11554-016-0590-2. 

***************************************/

module table_reader(
	clk,rst,datavalid, //global input
	A,B,r1,r2,d,O,HCN, //input from other modules
	d_we,d_waddr,h_rdata,t_rdata,n_rdata,d_rdata,h_wdata,t_wdata, //input from table
	h_raddr,t_raddr,n_raddr,d_raddr, //output to table
	p,hp,np,tp,dp,fp,fn //output to others module
);

parameter address_bit=9;
parameter data_bit=38;

input clk,rst,datavalid,A,B,r1,r2,O,HCN,d_we;
input [address_bit-1:0]d_waddr,h_rdata,t_rdata,n_rdata,h_wdata,t_wdata;
input [data_bit-1:0]d,d_rdata;
output [address_bit-1:0]n_raddr,h_raddr,t_raddr,d_raddr;
output reg [address_bit-1:0]p,hp,np;
output [address_bit-1:0]tp;
output [data_bit-1:0]dp;
output reg fp,fn;

reg [address_bit-1:0]Rtp;
reg [data_bit-1:0]Rdp;

////label counter p
reg [address_bit-1:0]pc;
always@(posedge clk or posedge rst)
	if(rst)begin
		pc<=0;p<=0;
	end
	else if(datavalid)begin
		p<=pc;
		if(r1&~r2)begin
			pc<=pc+1;
		end	
	end

//////primary tables
assign n_raddr=pc;
assign h_raddr=pc;

//////secondary tables
assign t_raddr=(HCN)?h_wdata:h_rdata; 
assign d_raddr=(HCN)?h_wdata:h_rdata;

//////previous row run cache
wire DCN;
assign DCN=(d_we)&(d_waddr==hp);

assign tp=(~A&B)?t_rdata:Rtp;
assign dp=(~A&B)?d_rdata:Rdp;
always@(posedge clk or posedge rst)
	if(rst)begin
		np<=0;hp<=0;fp<=0;fn<=0;Rtp<=0;Rdp<=0;
	end
	else if(datavalid)begin
		Rtp<=tp;Rdp<=dp;
		if(DCN)
			Rdp<=d;
		if(~B&r1)begin
			hp<=t_raddr;
			fp<=~(t_raddr==p);
			np<=n_rdata;
			fn<=(n_rdata==p);
		end
		else if(O)begin
			Rtp<=t_wdata;
			fp<=1;
			hp<=h_wdata;
		end
	end
	
endmodule
/**************************************
Author: J.W Tang
Email: jaytang1987@hotmail.com
Module: window
Date: 2016-04-24

Copyright (C) 2016 J.W. Tang
----------------------------
This file is part of LinkRunCCA.

LinkRunCCA is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

LinkRunCCA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with LinkRunCCA. If not, see <http://www.gnu.org/licenses/>.

By using this component in any associated publication,
you agree to cite it as: 
Tang, J. W., et al. "A linked list run-length-based single-pass
connected component analysis for real-time embedded hardware."
Journal of Real-Time Image Processing: 1-19. 2016.
doi:10.1007/s11554-016-0590-2. 

***************************************/

module window(clk,datavalid,pix_in_current,pix_in_previous,A,B,C,D);

input clk,datavalid,pix_in_current,pix_in_previous;
output reg A,B,C,D;

always@(posedge clk)
	if(datavalid)begin
		A<=B;B<=pix_in_previous;
		C<=D;D<=pix_in_current;
	end
	
endmodule
