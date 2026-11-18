/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/




//`define USE_MULDIV




 
 

 
 
 

 
 
 
 
 
 


 
 
 
 
 
 
 
 
 
 
 

 
 
 

 
 
 

 
 
 
 
 

 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 

 
 
 
 
 
 
 
 
 
 
 
 

 
 
 
 
 
 
 
 
 


 
 
 
 

 
 
 
 

 
 
 
 
 
 
 

 
 
 
 
 
 
 
 
 
 
 
 

 
 
 
 
 
 
 

 
 
 
 
 
 

 
 
 

 
 
 
 
 
 
 

 
 
 







 
 
 

 

   






module mips_core (
        clk,rst,cop_dout,
          din,  ins_i,iack_o,cop_addr_o,
        cop_data_o,cop_mem_ctl_o,  addr_o,
          dout,  pc_o,  wr_en_o
    );

    input clk;
    wire clk;
   /// input irq_i;
    wire irq_i = 0;
    input rst;
    wire rst;
    input [31:0] cop_dout;
    wire [31:0] cop_dout;
  ///  input [31:0] irq_addr;
    wire [31:0] irq_addr=0;
    input [31:0]   din;
    wire [31:0]   din;
    input [31:0]   ins_i;
    wire [31:0]   ins_i;
    output [31:0]   addr_o;
    wire [31:0]   addr_o;
    output [31:0]   dout;
    wire [31:0]   dout;
    output [31:0]   pc_o;
    wire [31:0]   pc_o;
    output [3:0]   wr_en_o;
    wire [3:0]   wr_en_o;
    output iack_o;
    wire iack_o;
    output [31:0] cop_addr_o;
    wire [31:0] cop_addr_o;
    output [31:0] cop_data_o;
    wire [31:0] cop_data_o;
    output [3:0] cop_mem_ctl_o;
    wire [3:0] cop_mem_ctl_o;


    wire NET1375;
    wire NET1572;
    wire NET1606;
    wire NET1640;
    wire NET21531;
    wire NET457;
    wire NET767;
    wire [2:0] BUS109;
    wire [2:0] BUS1158;
    wire [2:0] BUS117;
    wire [2:0] BUS1196;
    wire [31:0] BUS15471;
    wire [4:0] BUS1724;
    wire [4:0] BUS1726;
    wire [4:0] BUS18211;
    wire [2:0] BUS197;
    wire [2:0] BUS2140;
    wire [2:0] BUS2156;
    wire [31:0] BUS22401;
    wire [31:0] BUS24839;
    wire [31:0] BUS27031;
    wire [2:0] BUS271;
    wire [31:0] BUS28013;
    wire [1:0] BUS371;
    wire [31:0] BUS422;
    wire [1:0] BUS5832;
    wire [1:0] BUS5840;
    wire [3:0] BUS5985;
    wire [2:0] BUS5993;
    wire [4:0] BUS6275;
    wire [31:0] BUS7101;
    wire [31:0] BUS7117;
    wire [31:0] BUS7160;
    wire [31:0] BUS7219;
    wire [31:0] BUS7231;
    wire [4:0] BUS748;
    wire [4:0] BUS756;
    wire [4:0] BUS775;
    wire [31:0] BUS7772;
    wire [31:0] BUS7780;
    wire [31:0] BUS9589;
    wire [31:0] BUS9884;
/*

        clk,din,dmem_addr_i,dmem_ctl,
        zZ_din,Zz_addr,Zz_dout,Zz_wr_en,dout
*/

    mem_module MEM_CTL
               (
                   .Zz_addr(addr_o),
                   .Zz_dout(  dout),
                   .Zz_wr_en(  wr_en_o),
                   .clk(clk),
                   .din(BUS9884),
                   .dmem_addr_i(BUS9589),
                   .dmem_ctl(BUS5985),
                   .dout(BUS22401),
                   .zZ_din(  din)
               );

    assign NET21531 = NET1572 | iack_o;

    rf_stage iRF_stage
             (
                 .clk(clk),
                 .cmp_ctl_i(BUS109),
                 .ext_ctl_i(BUS117),
                 .ext_o(BUS7219),
                 .fw_alu_i(cop_addr_o),
                 .fw_cmp_rs(BUS2140),
                 .fw_cmp_rt(BUS2156),
                 .fw_mem_i(BUS15471),
                 .iack_o(iack_o),
                 .id2ra_ctl_clr_o(NET1606),
                 .id2ra_ctl_cls_o(NET1572),
                 .id_cmd(BUS197),
                 .ins_i(  ins_i),
                 .irq_addr_i(irq_addr),
                 .irq_i(irq_i),
                 .pc_gen_ctl(BUS271),
                 .pc_i(BUS27031),
                 .pc_next(  pc_o),
                 .ra2ex_ctl_clr_o(NET1640),
                 .rd_index_o(BUS775),
                 .rd_sel_i(BUS371),
                 .rs_n_o(BUS748),
                 .rs_o(BUS24839),
                 .rst_i(rst),
                 .rt_n_o(BUS756),
                 .rt_o(BUS7160),
                 .wb_addr_i(BUS18211),
                 .wb_din_i(BUS15471),
                 .wb_we_i(NET1375),
                 .zz_spc_i(BUS28013)
             );



    exec_stage iexec_stage
               (
                   .alu_func(BUS6275),
                   .alu_ur_o(BUS9589),
                   .clk(clk),
                   .dmem_data_ur_o(BUS9884),
                   .dmem_fw_ctl(BUS5993),
                   .ext_i(BUS7231),
                   .fw_alu(cop_addr_o),
                   .fw_dmem(BUS15471),
                   .muxa_ctl_i(BUS5832),
                   .muxa_fw_ctl(BUS1158),
                   .muxb_ctl_i(BUS5840),
                   .muxb_fw_ctl(BUS1196),
                   .pc_i(BUS27031),
                   .rs_i(BUS7101),
                   .rst(rst),
                   .rt_i(BUS7117),
                   .spc_cls_i(NET21531),
                   .zz_spc_o(BUS28013)
               );



    r32_reg alu_pass0
            (
                .clk(clk),
                .r32_i(BUS9589),
                .r32_o(cop_addr_o)
            );



    r32_reg alu_pass1
            (
                .clk(clk),
                .r32_i(cop_addr_o),
                .r32_o(BUS422)
            );



    or32 cop_data_or
         (
             .a(cop_dout),
             .b(BUS7772),
             .c(BUS7780)
         );



    r32_reg cop_data_reg
            (
                .clk(clk),
                .r32_i(BUS9884),
                .r32_o(cop_data_o)
            );



    r32_reg cop_dout_reg
            (
                .clk(clk),
                .r32_i(BUS22401),
                .r32_o(BUS7772)
            );



    decode_pipe decoder_pipe
                (
                    .alu_func_o(BUS6275),
                    .alu_we_o(NET767),
                    .clk(clk),
                    .cmp_ctl_o(BUS109),
                    .dmem_ctl_o(cop_mem_ctl_o),
                    .dmem_ctl_ur_o(BUS5985),
                    .ext_ctl_o(BUS117),
                    .fsm_dly(BUS197),
                    .id2ra_ctl_clr(NET1606),
                    .id2ra_ctl_cls(NET1572),
                    .ins_i(  ins_i),
                    .muxa_ctl_o(BUS5832),
                    .muxb_ctl_o(BUS5840),
                    .pc_gen_ctl_o(BUS271),
                    .ra2ex_ctl_clr(NET1640),
                    .rd_sel_o(BUS371),
                    .wb_mux_ctl_o(NET457),
                    .wb_we_o(NET1375)
                );



    r32_reg ext_reg
            (
                .clk(clk),
                .r32_i(BUS7219),
                .r32_o(BUS7231)
            );



    forward iforward
            (
                .alu_rs_fw(BUS1158),
                .alu_rt_fw(BUS1196),
                .alu_we(NET767),
                .clk(clk),
                .cmp_rs_fw(BUS2140),
                .cmp_rt_fw(BUS2156),
                .dmem_fw(BUS5993),
                .fw_alu_rn(BUS1724),
                .fw_mem_rn(BUS18211),
                .mem_We(NET1375),
                .rns_i(BUS748),
                .rnt_i(BUS756)
            );



    r32_reg pc
            (
                .clk(clk),
                .r32_i(  pc_o),
                .r32_o(BUS27031)
            );



    r5_reg rnd_pass0
           (
               .clk(clk),
               .r5_i(BUS775),
               .r5_o(BUS1726)
           );



    r5_reg rnd_pass1
           (
               .clk(clk),
               .r5_i(BUS1726),
               .r5_o(BUS1724)
           );



    r5_reg rnd_pass2
           (
               .clk(clk),
               .r5_i(BUS1724),
               .r5_o(BUS18211)
           );



    r32_reg rs_reg
            (
                .clk(clk),
                .r32_i(BUS24839),
                .r32_o(BUS7101)
            );



    r32_reg rt_reg
            (
                .clk(clk),
                .r32_i(BUS7160),
                .r32_o(BUS7117)
            );



    wb_mux wb_mux
           (
               .alu_i(BUS422),
               .dmem_i(BUS7780),
               .sel(NET457),
               .wb_o(BUS15471)
           );

endmodule
module exec_stage
    (
    input clk,
    input rst,
    input spc_cls_i,
    input [4:0] alu_func,
    input [2:0] dmem_fw_ctl,
    input [31:0] ext_i,
    input [31:0] fw_alu,
    input [31:0] fw_dmem,
    input [1:0] muxa_ctl_i,
    input [2:0] muxa_fw_ctl,
    input [1:0] muxb_ctl_i,
    input [2:0] muxb_fw_ctl,
    input [31:0] pc_i,
    input [31:0] rs_i,
    input [31:0] rt_i,
    output [31:0] alu_ur_o,
    output [31:0] dmem_data_ur_o,
    output [31:0] zz_spc_o
    );


    wire [31:0] BUS2332;
    wire [31:0] BUS2446;
    wire [31:0] BUS468;
    wire [31:0] BUS476;


    mips_alu MIPS_alu
            (
                .a(BUS476),
                .b(BUS468),
                .c(alu_ur_o),
                .clk(clk),
                .ctl(alu_func),
                .rst(rst)
            );

    add32 add4
          (
              .d_i(pc_i),
              .d_o(BUS2446)
          );


    fwd_mux dmem_fw_mux
            (
                .dout(dmem_data_ur_o),
                .fw_alu(fw_alu),
                .fw_ctl(dmem_fw_ctl),
                .fw_dmem(fw_dmem),
                .din(rt_i)
            );



    alu_muxa i_alu_muxa
             (
                 .a_o(BUS476),
                 .ctl(muxa_ctl_i),
                 .ext(ext_i),
                 .fw_alu(fw_alu),
                 .fw_ctl(muxa_fw_ctl),
                 .fw_mem(fw_dmem),
                 .pc(BUS2332),
                 .rs(rs_i),
                 .spc(zz_spc_o)
             );



    alu_muxb i_alu_muxb
             (
                 .b_o(BUS468),
                 .ctl(muxb_ctl_i),
                 .ext(ext_i),
                 .fw_alu(fw_alu),
                 .fw_ctl(muxb_fw_ctl),
                 .fw_mem(fw_dmem),
                 .rt(rt_i)
             );



    r32_reg pc_nxt
            (
                .clk(clk),
                .r32_i(BUS2446),
                .r32_o(BUS2332)
            );



    r32_reg_cls spc
                (
                    .clk(clk),
                    .cls(spc_cls_i),
                    .r32_i(pc_i),
                    .r32_o(zz_spc_o)
                );

endmodule

module mips_alu(clk,rst,a,b,c,ctl);
    input  clk,rst ;
    input  [31:0] a,b ;
    output [31:0] c ;
    input  [4:0]ctl ;

    wire [31:0] mul_div_c;
    wire [31:0] alu_c;
    wire [31:0] shift_c;
    



 
    assign c =   alu_c | shift_c ;

 
    











 
    shifter_tak mips_shifter(
                    .a(b),
                    .shift_out(shift_c),
                    .shift_func(ctl),
                    .shift_amount(a)
                );

    alu mips_alu(
            .a(a),
            .b(b),
            .alu_out(alu_c),
            .alu_func(ctl)
        );

endmodule

module alu_muxa(
        input [31:0]spc,
        input [31:0]pc,
        input [31:0]fw_mem,
        input [31:0]rs,
        input [31:0]fw_alu,
        input [31:0]ext,
        input [1:0] ctl,
        input [2:0] fw_ctl,
        output reg [31:0]a_o
    );

    always @(*)
    begin
        case (ctl)
            2:   a_o = (fw_ctl ==3'b001 )?fw_alu:(fw_ctl==3'b010)?fw_mem:rs;
            1:   a_o = pc;
            3:  a_o = ext;
            0:  a_o = spc;
            default :   a_o = rs;
        endcase
    end
endmodule

module alu_muxb(
        input [31:0] rt,
        input [31:0]fw_alu,
        input [31:0]fw_mem,
        input [31:0]ext ,
        input [1:0]ctl ,
        input [2:0]fw_ctl ,
        output reg [31:0] b_o
    );
    always@(*)
    case (ctl)
        1 :b_o = (fw_ctl ==3'b001 )?fw_alu:(fw_ctl==3'b010)?fw_mem:rt;
        2 :	b_o=ext;
        default b_o=rt;
    endcase
endmodule



//This file is based on YACC ->alu.v and  UCORE ->alu.v

module alu (
    input [31:0] a,
	input [31:0]b,
    output reg [31:0] alu_out,
    input [4:0]	alu_func
	);

    reg [32:0] sum;

    always @(*)
    begin
        case (alu_func)

            22     : alu_out=a;
            23     : alu_out=b;
            12    : alu_out=a+b;
            14  ,
            15   : alu_out=a + (~b)+1;
            18     : alu_out=a | b;
            19    : alu_out=a & b;
            20    : alu_out=a ^ b;
            21    : alu_out=~(a | b);
            16   : alu_out=(a < b)?1:0;
            17 :
            begin
                sum={a[31],a}+~{b[31],b}+33'h0_0000_0001;
                alu_out={31'h0000_0000,sum[32]};
            end

            /*
            			`ALU_SLL:	alu_out = a<<b[4:0];
                    	`ALU_SRL:   alu_out = a>>b[4:0];
            			`ALU_SRA:	alu_out=~(~a>>b[4:0]);
            			//the three operations is done in shifter_tak or shift_ff
            */

            default : alu_out=32'h0;
        endcase
    end
endmodule


module shifter_ff(
        input [31:0] a,
        output reg [31:0] shift_out,
        input [4:0] shift_func,//connect to alu_func_ctl
        input [31:0] shift_amount//connect to b
    );

    always @ (*)
    begin
        case( shift_func )
            2:	shift_out = a<<shift_amount;
            1:   shift_out = a>>shift_amount;
            4:	shift_out=~(~a>> shift_amount);
            default		shift_out='d0;
        endcase
    end
endmodule


module  shifter_tak(
            input [31:0] a,
            output reg [31:0] shift_out,
            input [4:0] shift_func,//connect to alu_func_ctl
            input [31:0] shift_amount//connect to b
        );

    always @ (*)
    case( shift_func )
        2:
        begin
            case ( shift_amount[4:0] )
                5'b00000: shift_out=a;
                5'b00001: shift_out={a[30:0],1'b0};
                5'b00010: shift_out={a[29:0],2'b0};
                5'b00011: shift_out={a[28:0],3'b0};
                5'b00100: shift_out={a[27:0],4'b0};
                5'b00101: shift_out={a[26:0],5'b0};
                5'b00110: shift_out={a[25:0],6'b0};
                5'b00111: shift_out={a[24:0],7'b0};
                5'b01000: shift_out={a[23:0],8'b0};
                5'b01001: shift_out={a[22:0],9'b0};
                5'b01010: shift_out={a[21:0],10'b0};
                5'b01011: shift_out={a[20:0],11'b0};
                5'b01100: shift_out={a[19:0],12'b0};
                5'b01101: shift_out={a[18:0],13'b0};
                5'b01110: shift_out={a[17:0],14'b0};
                5'b01111: shift_out={a[16:0],15'b0};
                5'b10000: shift_out={a[15:0],16'b0};
                5'b10001: shift_out={a[14:0],17'b0};
                5'b10010: shift_out={a[13:0],18'b0};
                5'b10011: shift_out={a[12:0],19'b0};
                5'b10100: shift_out={a[11:0],20'b0};
                5'b10101: shift_out={a[10:0],21'b0};
                5'b10110: shift_out={a[9:0],22'b0};
                5'b10111: shift_out={a[8:0],23'b0};
                5'b11000: shift_out={a[7:0],24'b0};
                5'b11001: shift_out={a[6:0],25'b0};
                5'b11010: shift_out={a[5:0],26'b0};
                5'b11011: shift_out={a[4:0],27'b0};
                5'b11100: shift_out={a[3:0],28'b0};
                5'b11101: shift_out={a[2:0],29'b0};
                5'b11110: shift_out={a[1:0],30'b0};
                5'b11111: shift_out={a[0],31'b0};
                default shift_out =32'bx;//never in this case
            endcase
        end
        1 :
        begin
            case (shift_amount[4:0])
                5'b00000: shift_out=a;
                5'b00001: shift_out={1'b0,a[31:1]};
                5'b00010: shift_out={2'b0,a[31:2]};
                5'b00011: shift_out={3'b0,a[31:3]};
                5'b00100: shift_out={4'b0,a[31:4]};
                5'b00101: shift_out={5'b0,a[31:5]};
                5'b00110: shift_out={6'b0,a[31:6]};
                5'b00111: shift_out={7'b0,a[31:7]};
                5'b01000: shift_out={8'b0,a[31:8]};
                5'b01001: shift_out={9'b0,a[31:9]};
                5'b01010: shift_out={10'b0,a[31:10]};
                5'b01011: shift_out={11'b0,a[31:11]};
                5'b01100: shift_out={12'b0,a[31:12]};
                5'b01101: shift_out={13'b0,a[31:13]};
                5'b01110: shift_out={14'b0,a[31:14]};
                5'b01111: shift_out={15'b0,a[31:15]};
                5'b10000: shift_out={16'b0,a[31:16]};
                5'b10001: shift_out={17'b0,a[31:17]};
                5'b10010: shift_out={18'b0,a[31:18]};
                5'b10011: shift_out={19'b0,a[31:19]};
                5'b10100: shift_out={20'b0,a[31:20]};
                5'b10101: shift_out={21'b0,a[31:21]};
                5'b10110: shift_out={22'b0,a[31:22]};
                5'b10111: shift_out={23'b0,a[31:23]};
                5'b11000: shift_out={24'b0,a[31:24]};
                5'b11001: shift_out={25'b0,a[31:25]};
                5'b11010: shift_out={26'b0,a[31:26]};
                5'b11011: shift_out={27'b0,a[31:27]};
                5'b11100: shift_out={28'b0,a[31:28]};
                5'b11101: shift_out={29'b0,a[31:29]};
                5'b11110: shift_out={30'b0,a[31:30]};
                5'b11111: shift_out={31'b0,a[31:31]};
                default : shift_out = 32'bx;//never in this case
            endcase
        end
        4:
        begin// SHIFT_RIGHT_SIGNED
            case ( shift_amount[4:0])
                5'b00000: shift_out=a;
                5'b00001: shift_out={a[31],a[31:1]};
                5'b00010: shift_out={{2{a[31]}},a[31:2]};
                5'b00011: shift_out={{3{a[31]}},a[31:3]};
                5'b00100: shift_out={{4{a[31]}},a[31:4]};
                5'b00101: shift_out={{5{a[31]}},a[31:5]};
                5'b00110: shift_out={{6{a[31]}},a[31:6]};
                5'b00111: shift_out={{7{a[31]}},a[31:7]};
                5'b01000: shift_out={{8{a[31]}},a[31:8]};
                5'b01001: shift_out={{9{a[31]}},a[31:9]};
                5'b01010: shift_out={{10{a[31]}},a[31:10]};
                5'b01011: shift_out={{11{a[31]}},a[31:11]};
                5'b01100: shift_out={{12{a[31]}},a[31:12]};
                5'b01101: shift_out={{13{a[31]}},a[31:13]};
                5'b01110: shift_out={{14{a[31]}},a[31:14]};
                5'b01111: shift_out={{15{a[31]}},a[31:15]};
                5'b10000: shift_out={{16{a[31]}},a[31:16]};
                5'b10001: shift_out={{17{a[31]}},a[31:17]};
                5'b10010: shift_out={{18{a[31]}},a[31:18]};
                5'b10011: shift_out={{19{a[31]}},a[31:19]};
                5'b10100: shift_out={{20{a[31]}},a[31:20]};
                5'b10101: shift_out={{21{a[31]}},a[31:21]};
                5'b10110: shift_out={{22{a[31]}},a[31:22]};
                5'b10111: shift_out={{23{a[31]}},a[31:23]};
                5'b11000: shift_out={{24{a[31]}},a[31:24]};
                5'b11001: shift_out={{25{a[31]}},a[31:25]};
                5'b11010: shift_out={{26{a[31]}},a[31:26]};
                5'b11011: shift_out={{27{a[31]}},a[31:27]};
                5'b11100: shift_out={{28{a[31]}},a[31:28]};
                5'b11101: shift_out={{29{a[31]}},a[31:29]};
                5'b11110: shift_out={{30{a[31]}},a[31:30]};
                5'b11111: shift_out={{31{a[31]}},a[31:31]};
                default shift_out=32'bx;//never in this case
            endcase
        end
        default			shift_out='d0;
    endcase
endmodule

module muldiv(ready,rst,op1,op2,clk,dout,func);
    input         clk,rst;
    wire       sign;
    input [4:0] func ;
    input [31:0] op2, op1;
    output [31:0] dout;
    output        ready;
    reg [31:0]    quotient, quotient_temp;
    reg [63:0]    dividend_copy, divider_copy, diff;
    reg           negative_output;

    reg [63:0]    product, product_temp;

    reg [31:0]    multiplier_copy;
    reg [63:0]    multiplicand_copy;

    reg [6:0]     mul_bit,div_bit;
    wire          ready = ((mul_bit==0)&&(div_bit==0));

    wire  [31:0]  dividend, divider;

    wire [31:0]  remainder;
    wire [31:0] multiplier,multiplicand;

    reg [31:0] hi,lo;

    assign dout = (func==6)?hi:(func==7)?lo:0;

    assign  remainder = (!negative_output) ?
            dividend_copy[31:0] :
            ~dividend_copy[31:0] + 1'b1;

    assign multiplier=op2;
    assign multiplicand=op1;
    assign dividend=op1;
    assign  divider = op2;
    assign sign = ((func==9)||(func==11));

    initial
    begin
        hi=0;
        lo=0;
    end
    always @( posedge clk /*or negedge rst */)
        if (~rst)
        begin
            mul_bit=0;
            div_bit=0;
            /*
            hi=0;
            lo=0;
            */
            negative_output = 0;
        end
        else
        begin
            if((ready)&&((func==9)||(func==8)))
            begin
                mul_bit               = 33;
                product           = 0;
                product_temp      = 0;
                multiplicand_copy = (!sign || !multiplicand[31]) ?
                                  { 32'd0, multiplicand } :
                                  { 32'd0, ~multiplicand + 1'b1};
                multiplier_copy   = (!sign || !multiplier[31]) ?multiplier :~multiplier + 1'b1;

                negative_output = sign &&
                                ((multiplier[31] && !multiplicand[31])
                                 ||(!multiplier[31] && multiplicand[31]));
            end
            if ( mul_bit > 1 )
            begin

                if( multiplier_copy[0] == 1'b1 )
                    product_temp = product_temp +multiplicand_copy;


                product = (!negative_output) ?
                        product_temp :
                        ~product_temp + 1'b1;

                multiplier_copy = multiplier_copy >> 1;
                multiplicand_copy = multiplicand_copy << 1;
                mul_bit = mul_bit - 1'b1;
            end
            else if (mul_bit == 1)
            begin
                hi =  product[63:32];
                lo =  product[31:0];
                mul_bit=0;
            end

            if((ready)&&((func==11)||(func==10)))
            begin
                div_bit = 33;
                quotient = 0;
                quotient_temp = 0;
                dividend_copy = (!sign || !dividend[31]) ?
                              {32'd0,dividend} :
                              {32'd0,~dividend + 1'b1};

                divider_copy = (!sign || !divider[31]) ?
                             {1'b0,divider,31'd0} :
                             {1'b0,~divider + 1'b1,31'd0};

                negative_output = sign &&
                                ((divider[31] && !dividend[31])
                                 ||(!divider[31] && dividend[31]));
            end
            else if (div_bit > 1)
            begin
                diff = dividend_copy - divider_copy;
                quotient_temp = quotient_temp << 1;
                if( !diff[63] )
                begin
                    dividend_copy = diff;
                    quotient_temp[0] = 1'd1;
                end
                quotient = (!negative_output) ?quotient_temp :~quotient_temp + 1'b1;
                divider_copy = divider_copy >> 1;
                div_bit = div_bit - 1'b1;
            end
            else if (div_bit == 1)
            begin
                lo =  quotient;
                hi =  remainder;
                div_bit=0;
            end
        end

endmodule

//creatied by Zhangfeifei
//modified by Liwei
module muldiv_ff
    (        clk_i,rst_i,
             op_type,op1,op2,
             rdy,res

    );

    parameter  OP_MULT  = 9;
    parameter  OP_MULTU = 8;
    parameter  OP_DIV   = 11;
    parameter  OP_DIVU  = 10;
    parameter  OP_MFHI  = 6;
    parameter  OP_MFLO  = 7;
    parameter  OP_MTHI  = 31;
    parameter  OP_MTLO  = 30;
    parameter  OP_NONE  = 0;

    input         clk_i;
    input         rst_i;
    input  [4:0]  op_type;
    input  [31:0] op1;
    input  [31:0] op2;
    output [31:0] res;
    output        rdy;

    reg           rdy;
    reg    [64:0] hilo;
    reg    [32:0] op2_reged;
    reg    [5:0]  count;
    reg           op1_sign_reged;
    reg           op2_sign_reged;
    reg           sub_or_yn;

    wire   [32:0] nop2_reged;
    assign nop2_reged = ~op2_reged +1;

    reg           sign;
    reg           mul;
    reg           start;

    assign res = (op_type == OP_MFLO )?hilo[31:0]:((op_type == OP_MFHI))?hilo[63:32]:0;//op_type == OP_MFHI or other

    reg           overflow;
    reg           finish;
    reg           add1;  //if the quotient will add 1 at the end of the divide operation
    reg           addop2; //if the remainder will add op2 at the end of the divide operation
    reg           addnop2;//if the remainder will add ~op2+1 at the end of the divide operation


    always @( posedge clk_i  /*or negedge rst_i*/)
    begin
        if(~rst_i)
        begin
            count          = 6'bx;
            hilo           = 65'b0;
            op2_reged      = 33'bx;
            op1_sign_reged = 1'bx;
            op2_sign_reged = 1'bx;
            sub_or_yn      = 1'bx;
            rdy            = 1'b1;
            start          = 1'bx;
            sign           = 1'bx;
            mul            = 1'bx;
            finish         = 1'bx;
            add1           = 1'bx;
            addop2         = 1'bx;
            addnop2        = 1'bx;
        end
        else begin

            if(op_type == OP_MTHI || op_type == OP_MTLO)
            begin
                if(op_type == OP_MTHI) hilo[64:32] = {1'b0,op1};
                if(op_type == OP_MTLO) hilo[31:0]  = op1;
                rdy = 1;
            end
            else if(rdy)
            begin
                start = (op_type == OP_MULT) || (op_type == OP_MULTU) || (op_type == OP_DIV)  || (op_type == OP_DIVU);
                mul   = (op_type == OP_MULT) || (op_type == OP_MULTU);
                sign  = (op_type == OP_MULT) || (op_type == OP_DIV);

                if(start)
                begin:START_SECTION
                    reg [32:0] over;

                    op2_reged       = {sign        ?op2[31]      :1'b0 ,op2};
                    hilo            = {~mul && sign?{33{op1[31]}}:33'b0,op1};
                    count           = 6'b000000;
                    rdy             = 0;
                    op1_sign_reged  = sign?op1[31]:0;
                    op2_sign_reged  = sign?op2[31]:0;
                    sub_or_yn       = 0;

                    over            = ~op2_reged + {op1[31],op1};
                    overflow        = sign && ~mul ? op1_sign_reged && op2_sign_reged && ~over[32] : 0;

                    finish          = 0;
                end
            end
            else if(start)
            begin
                if(overflow)
                begin
                    hilo[63:0] = {hilo[31:0],32'b0};
                    rdy        = 1;
                end
                else if(!count[5])
                begin
                    if(mul)
                    begin
                        if(sign)
                        begin
                            case({hilo[0],sub_or_yn})
                                2'b10:hilo[64:32] = hilo[64:32] + nop2_reged;
                                2'b01:hilo[64:32] = hilo[64:32] + op2_reged;
                                default:;
                            endcase
                            {hilo[63:0],sub_or_yn} = hilo[64:0];
                        end
                        else begin
                            if(hilo[0]) hilo[64:32] = hilo[64:32] + op2_reged;
                            hilo      = {1'b0,hilo[64:1]};
                        end
                    end
                    else begin
                        sub_or_yn  = hilo[64]== op2_sign_reged;
                        hilo[64:1] = hilo[63:0];

                        hilo[64:32] = sub_or_yn ? hilo[64:32] + nop2_reged : hilo[64:32] + op2_reged;

                        hilo[0]    = hilo[64]== op2_sign_reged;
                    end

                    count        = count + 1'b1;
                end
                else begin
                    if(finish)
                    begin
                        if(add1)   hilo[31:0]  = hilo[31:0] + 1;
                        case({addop2,addnop2})
                            2'b10:   hilo[64:32] = hilo[64:32] + op2_reged;
                            2'b01:   hilo[64:32] = hilo[64:32] + nop2_reged;
                            default: ;
                        endcase
                        rdy = 1;
                    end
                    else begin
                        {add1,addop2,addnop2} = 3'b000;
                        finish                = 1;

                        if(~mul)
                        begin:LAST_CYCLE_DEAL_SECTION
                            reg eqz,eqop2,eqnop2;
                            eqz    = hilo[64:32] == 0;
                            eqop2  = hilo[64:32] == op2_reged;
                            eqnop2 = hilo[64:32] == nop2_reged;
                            casex({op1_sign_reged,op2_sign_reged,eqz,eqop2,eqnop2})
                                5'b101xx : {add1,addop2,addnop2} = 3'b000;
                                5'b100x1 : {add1,addop2,addnop2} = 3'b010;
                                5'b111xx : {add1,addop2,addnop2} = 3'b100;
                                5'b1101x : {add1,addop2,addnop2} = 3'b101;
                                default :
                                begin:LAST_CYCLE_DEAL_SECTION_DEFAULT

                                    reg op1s_eq_op2s,op1s_eq_h64;
                                    op1s_eq_op2s = op1_sign_reged == op2_sign_reged;
                                    op1s_eq_h64  = op1_sign_reged == hilo[64];

                                    add1 = ~op1s_eq_op2s;
                                    case({op1s_eq_op2s,op1s_eq_h64})//synthesis parallel_case
                                        2'b00:   {addop2,addnop2} = 2'b01;
                                        2'b10:   {addop2,addnop2} = 2'b10;
                                        default: {addop2,addnop2} = 2'b00;
                                    endcase
                                end
                            endcase
                        end
                    end
                end
            end
        end
    end
endmodule


/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 



module ext(
        input [31:0] ins_i ,
        output reg [31:0] res ,
        input [2:0]ctl
    );

    wire [25:0] instr25_0;
    assign instr25_0 = ins_i[25:0] ;

    wire[15:0] sign = {16{instr25_0[15]}};

    always @ (*)
    case (ctl)
        1    :res ={sign,instr25_0[15:0]};//sign
        2  :res ={16'b0,instr25_0[15:0]};//zeroext
        3       :res ={4'b0,instr25_0[25:0],2'b0};//jmp
        4       :res ={sign[13:0],instr25_0[15:0],2'B0};//branch
        5      :res ={27'b0,instr25_0[10:6]} ;//sll,srl
        6     :res ={instr25_0[15:0],16'B0};//shift to high
        default: res=32'bx;
    endcase
endmodule


module compare (
        input [31:0] s,
        input [31:0] t,
        input [2:0]ctl,
        output reg res
    );
    always @ (*)
    case  (ctl)
        1:   res = (s==t);
        2:   res = (s!=t);
        6:  res = s[31];
        5:  res = ~s[31] && (|s[30:0]);
        3:  res = s[31] |(~|s);
        4:  res = ~s[31];
        default res=1'Bx;
    endcase
endmodule


module pc_gen(
        input [2:0]ctl,
        output reg   [31:0]pc_next,
        input [3:0] pc_prectl,
        input check,
        input [31:0]s,
        input [31:0]pc,
        input [31:0]zz_spc,
        input [31:0]imm,
        input [31:0]irq
    );

    wire [32:0] br_addr = pc + imm ;
    always @ (*)
        if(pc_prectl == 1 )
        begin
            case (ctl)
                6 	:	pc_next = zz_spc ;
                1		:	pc_next ={pc[31:28],imm[27:0]};
                2		: 	pc_next = s;
                4		: 	pc_next = (check)?({br_addr[31:0]}):(pc+4);
             default   
			 /* `PC_NEXT	:*/	pc_next = pc + 4 ;              	
            endcase
        end
        else
        begin
            case (pc_prectl)
                2 	: pc_next=pc;
                4 	: pc_next=irq;
             default	    
			 /* `PC_RST 	: pc_next='d0;*/
               	  pc_next =0;
            endcase
        end

endmodule



module reg_array(
        data,
        wraddress,
        rdaddress_a,
        rdaddress_b,
        wren,
        clock,
        qa,
        qb,
        rd_clk_cls,
    //    bank_sel
    );

    input	[31:0]  data;
    input	[4:0]  wraddress;
    input	[4:0]  rdaddress_a;
    input	[4:0]  rdaddress_b;
   // input bank_sel;
    input rd_clk_cls;
    input	wren;

    reg	[31:0]  r_data;
    reg	[4:0]  r_wraddress;
    reg	[4:0]  r_rdaddress_a;
    reg	[4:0]  r_rdaddress_b;

    reg r_wren;
    input	clock;
    output	[31:0]  qa;
    output	[31:0]  qb;
    reg [31:0]reg_bank[0:31];

    integer i;
    initial
    begin
        for(i=0;i<32;i=i+1)
            reg_bank[i]=0;
    end

    always@(posedge clock)
    begin
        r_data <=data;
        r_wraddress<=wraddress;
        r_wren<=wren;
    end

	    always@(posedge clock)
        if (~rd_clk_cls)
        begin
            r_rdaddress_a <=rdaddress_a;
            r_rdaddress_b <=rdaddress_b;
        end

    always@(posedge clock)
        if (r_wren)
            reg_bank[r_wraddress] <= r_data ;

    assign qa=(r_rdaddress_a[4:0]==0)?0:
           ((r_wraddress==r_rdaddress_a)&&(1==r_wren))?r_data:
           reg_bank[r_rdaddress_a];

    assign qb=(r_rdaddress_b[4:0]==0)?0:
           ((r_wraddress==r_rdaddress_b)&&(1==r_wren))?r_data:
           reg_bank[r_rdaddress_b];

endmodule
/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 




module rf_stage (
        clk,irq_i,rst_i,wb_we_i,cmp_ctl_i,
        ext_ctl_i,fw_alu_i,fw_cmp_rs,fw_cmp_rt,
        fw_mem_i,id_cmd,ins_i,irq_addr_i,pc_gen_ctl,
        pc_i,rd_sel_i,wb_addr_i,wb_din_i,zz_spc_i,iack_o,
        id2ra_ctl_clr_o,id2ra_ctl_cls_o,ra2ex_ctl_clr_o,ext_o,
        pc_next,rd_index_o,rs_n_o,rs_o,rt_n_o,rt_o
    ) ;

    input clk;
    wire clk;
    input irq_i;
    wire irq_i;
    input rst_i;
    wire rst_i;
    input wb_we_i;
    wire wb_we_i;
    input [2:0] cmp_ctl_i;
    wire [2:0] cmp_ctl_i;
    input [2:0] ext_ctl_i;
    wire [2:0] ext_ctl_i;
    input [31:0] fw_alu_i;
    wire [31:0] fw_alu_i;
    input [2:0] fw_cmp_rs;
    wire [2:0] fw_cmp_rs;
    input [2:0] fw_cmp_rt;
    wire [2:0] fw_cmp_rt;
    input [31:0] fw_mem_i;
    wire [31:0] fw_mem_i;
    input [2:0] id_cmd;
    wire [2:0] id_cmd;
    input [31:0] ins_i;
    wire [31:0] ins_i;
    input [31:0] irq_addr_i;
    wire [31:0] irq_addr_i;
    input [2:0] pc_gen_ctl;
    wire [2:0] pc_gen_ctl;
    input [31:0] pc_i;
    wire [31:0] pc_i;
    input [1:0] rd_sel_i;
    wire [1:0] rd_sel_i;
    input [4:0] wb_addr_i;
    wire [4:0] wb_addr_i;
    input [31:0] wb_din_i;
    wire [31:0] wb_din_i;
    input [31:0] zz_spc_i;
    wire [31:0] zz_spc_i;
    output iack_o;
    wire iack_o;
    output id2ra_ctl_clr_o;
    wire id2ra_ctl_clr_o;
    output id2ra_ctl_cls_o;
    wire id2ra_ctl_cls_o;
    output ra2ex_ctl_clr_o;
    wire ra2ex_ctl_clr_o;
    output [31:0] ext_o;
    wire [31:0] ext_o;
    output [31:0] pc_next;
    wire [31:0] pc_next;
    output [4:0] rd_index_o;
    wire [4:0] rd_index_o;
    output [4:0] rs_n_o;
    wire [4:0] rs_n_o;
    output [31:0] rs_o;
    wire [31:0] rs_o;
    output [4:0] rt_n_o;
    wire [4:0] rt_n_o;
    output [31:0] rt_o;
    wire [31:0] rt_o;


    wire NET6609;
    wire NET6658;
    wire NET7774;
    wire NET904;

    wire [3:0] BUS1013;
    wire [31:0] BUS2085;
    wire [4:0] BUS3236;
    wire [4:0] BUS3237;
    wire [4:0] BUS5421;
    wire [31:0] BUS6061;
    wire [31:0] BUS6095;

    wire [100:0] CLK_NO;
    wire [100:0] INS_NO;

    cal_cpi CAL_CPI
            (
                .clk(clk),
                .clk_no(CLK_NO),
                .ins_no(INS_NO),
                .is_nop(NET7774),
                .rst(rst_i)
            );



    ctl_FSM MAIN_FSM
            (
                .clk(clk),
                .iack(iack_o),
                .id2ra_ctl_clr(id2ra_ctl_clr_o),
                .id2ra_ctl_cls(id2ra_ctl_cls_o),
                .id2ra_ins_clr(NET6609),
                .id2ra_ins_cls(NET6658),
                .id_cmd(id_cmd),
                .irq(irq_i),
                .pc_prectl(BUS1013),
                .ra2exec_ctl_clr(ra2ex_ctl_clr_o),
                .rst(rst_i),
                .zz_is_nop(NET7774)
            );



    pc_gen i_pc_gen
           (
               .check(NET904),
               .ctl(pc_gen_ctl),
               .imm(ext_o),
               .irq(irq_addr_i),
               .pc(pc_i),
               .pc_next(pc_next),
               .pc_prectl(BUS1013),
               .s(rs_o),
               .zz_spc(zz_spc_i)
           );



    compare i_cmp
            (
                .ctl(cmp_ctl_i),
                .res(NET904),
                .s(rs_o),
                .t(rt_o)
            );



    ext i_ext
        (
            .ctl(ext_ctl_i),
            .ins_i(BUS2085),
            .res(ext_o)
        );



    r32_reg_clr_cls ins_reg
                    (
                        .clk(clk),
                        .clr(NET6609),
                        .cls(NET6658),
                        .r32_i(ins_i),
                        .r32_o(BUS2085)
                    );



    jack jack1
         (
             .ins_i(BUS2085),
             .rd_o(BUS5421),
             .rs_o(rs_n_o),
             .rt_o(rt_n_o)
         );



    jack jack2
         (
             .ins_i(ins_i),
             .rs_o(BUS3237),
             .rt_o(BUS3236)
         );

    rd_sel rd_sel
           (
               .ctl(rd_sel_i),
               .rd_i(BUS5421),
               .rd_o(rd_index_o),
               .rt_i(rt_n_o)
           );

    reg_array reg_bank
              (
                  .clock(clk),
                  .data(wb_din_i),
                  .qa(BUS6061),
                  .qb(BUS6095),
                  .rd_clk_cls(NET6658),
                  .rdaddress_a(BUS3237),
                  .rdaddress_b(BUS3236),
                  .wraddress(wb_addr_i),
                  .wren(wb_we_i)/*,
                  .bank_sel(1'b0)*/
              );

    fwd_mux rf_fwd_rt
            (
                .din(BUS6095),
                .dout(rt_o),
                .fw_alu(fw_alu_i),
                .fw_ctl(fw_cmp_rt),
                .fw_dmem(fw_mem_i)
            );

    fwd_mux rs_fwd_rs
            (
                .din(BUS6061),
                .dout(rs_o),
                .fw_alu(fw_alu_i),
                .fw_ctl(fw_cmp_rs),
                .fw_dmem(fw_mem_i)
            );

endmodule
/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 



module ctl_FSM (
    input   clk,
    input   [2:0] id_cmd,
    input   irq,
    input   rst,
    output  reg iack,
    output  reg zz_is_nop,
    output  reg id2ra_ctl_clr,
    output  reg id2ra_ctl_cls,
    output  reg id2ra_ins_clr,
    output  reg id2ra_ins_cls,
    output  reg [3:0] pc_prectl,
    output  reg ra2exec_ctl_clr
    );
    parameter
        ID_CUR   = 1,   ID_LD    = 5 ,
        ID_MUL   = 2,   ID_NOI   = 6,
        ID_RET   = 4,
      
        PC_IGN   = 1 ,   PC_IRQ   = 4,
        PC_KEP   = 2 ,   PC_RST   = 8;

    reg [5:0] delay_counter;
    reg [4:0] CurrState ;
    reg [4:0] NextState ;
    reg     riack;
    always @(posedge clk) if (~rst) riack<=0; else riack<=iack;

    always @(*)
    begin //deal with iack
        case (CurrState )
            4'b0101:iack=1'b1;
            4'b0100:iack=1'b0;
            //onlt this 2 states those will change the iack state
            default iack=riack;
        endcase
    end

    always @ (posedge clk )
        if (~rst)delay_counter  <=0;
        else
        case (CurrState)
            //any delay state can be added here
            4'b0010:       delay_counter  <=delay_counter + 1;
            default :     delay_counter  <=0;
        endcase

/////////////////////////////////////////////////////////
//    Finite State Machine 
//
  /*Finite State Machine part1*/
    always @ (posedge clk) if (~rst) CurrState  <= 4'b0110; else CurrState  <= NextState ;

    always @ (*)/*Finite State Machine part2*/
    begin
        case (CurrState)
            4'b0001:
            begin
                if (~rst)                    NextState  = 4'b0110;
              //  else if ((irq)&&(~riack))    NextState  = `IRQ;
                else if (id_cmd ==ID_NOI)    NextState  = 4'b1000;
                else if (id_cmd==ID_CUR)     NextState  = 4'b0011;
                else if (id_cmd==ID_MUL)     NextState  = 4'b0010;
                else if (id_cmd==ID_LD)      NextState  = 4'b0111;
                else if (id_cmd==ID_RET)     NextState  = 4'b0100;
                else                         NextState  = 4'b0001;
            end      
            4'b1000:
            begin
                if (id_cmd ==ID_NOI)         NextState  = 4'b1000;
                else if (id_cmd==ID_CUR)     NextState  = 4'b0011;
                else if (id_cmd==ID_MUL)     NextState  = 4'b0010;
                else if (id_cmd==ID_LD)      NextState  = 4'b0111;
                else if (id_cmd==ID_RET)     NextState  = 4'b0100;
                else                         NextState  = 4'b0001;
            end
            4'b0011:   NextState  = 4'b1000;         
            4'b0100:   NextState  = 4'b0001;        
            4'b0101:   NextState  = 4'b0001;         
            4'b0110:   NextState  = 4'b0001;           
            4'b0111:    NextState  = 4'b0001;   
            4'b0010:   NextState  = (delay_counter==32)?4'b0001:4'b0010;
            default NextState  =4'b0001;
        endcase
    end

    always @ (*)/*Finite State Machine part3*/
    begin
        case (CurrState )
            4'b0001: begin id2ra_ins_clr  =  1'b0;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b0;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr   =  1'b0;
                pc_prectl=PC_IGN;
                zz_is_nop = 0;end             
      4'b0010:  begin
                id2ra_ins_clr  =  1'b1;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b1;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr  =  1'b0;
                pc_prectl =PC_KEP;
                zz_is_nop =0; end            
      4'b0011:  begin
                id2ra_ins_clr  =  1'b0;
                id2ra_ins_cls  =  1'b1;
                id2ra_ctl_clr  =  1'b0;
                id2ra_ctl_cls  =  1'b1;
                ra2exec_ctl_clr  =  1'b1;
                pc_prectl =PC_KEP;
                zz_is_nop = 1; end            
      4'b0100: begin id2ra_ins_clr  =  1'b0;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b0;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr   =  1'b0;
                pc_prectl =PC_IGN;
                zz_is_nop = 1'b0;  end        
      4'b0101: begin
                id2ra_ins_clr  =  1'b1;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b1;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr  =  1'b1;
                pc_prectl =PC_IRQ;
                zz_is_nop = 1'b0;end       
      4'b0110: begin
                id2ra_ins_clr  =  1'b1;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b1;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr  =  1'b1;
                pc_prectl=PC_RST;
                zz_is_nop = 1'b1; end       
      4'b0111:begin
                id2ra_ins_clr  =  1'b1;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b1;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr  =  1'b0;
                pc_prectl =PC_KEP;
                zz_is_nop = 1'b0;end          
      4'b1000:begin
                id2ra_ins_clr  =  1'b0;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b0;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr   =  1'b0;
                pc_prectl=PC_IGN;
                zz_is_nop = 1'b0;end         
      default   begin
                id2ra_ins_clr  =  1'b1;
                id2ra_ins_cls  =  1'b0;
                id2ra_ctl_clr  =  1'b1;
                id2ra_ctl_cls  =  1'b0;
                ra2exec_ctl_clr  =  1'b1;
                pc_prectl=PC_RST;
                zz_is_nop = 1'b1;end          
      endcase
    end
endmodule

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 



module decoder(
        input [31:0]ins_i,
        output reg [3-1:0] ext_ctl,
        output reg [2-1:0] rd_sel,
        output reg [3-1:0]cmp_ctl,
        output reg [3-1:0]pc_gen_ctl,
        output reg [3-1:0]fsm_dly,
        output reg [2-1:0]muxa_ctl,
        output reg [2-1:0]muxb_ctl,
        output reg [5-1:0]alu_func,
        output reg [4-1:0]dmem_ctl,
        output reg [1-1:0] alu_we,
        output reg [1-1:0]wb_mux,
        output reg [1-1:0]wb_we
    );

    wire [5:0]  inst_op,inst_func;
    wire [4:0]  inst_regimm;//,inst_rs,inst_rt,inst_rd,inst_sa;
    wire [4:0]  inst_cop0_func;//cop0's function code filed
    wire [25:0] inst_cop0_code;//cop0's code field

    assign inst_op        = ins_i[31:26];
    assign inst_func      = ins_i[5:0];
    assign inst_regimm    = ins_i[20:16];
    assign inst_cop0_func = ins_i[25:21];
    assign inst_cop0_code = ins_i[25:0];

    always @(*)
    begin
        case (inst_op)//synthesis parallel_case
            'd0://special operation
            begin
                case (inst_func) //synthesis parallel_case
                    'd0://SLL rd,rt,sa
                    begin
                        //replaceID  = `SLL ;
                        ext_ctl = 5;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 3;
                        muxb_ctl = 1;
                        alu_func = 2;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SLL ;
                    end
                    'd2://SRL rd,rt,sa
                    begin
                        //replaceID  = `SRL ;
                        ext_ctl = 5;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 3;
                        muxb_ctl = 1;
                        alu_func = 1;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SRL ;
                    end
                    'd3://SRA rd,rt,sa
                    begin
                        //replaceID  = `SRA ;
                        ext_ctl = 5;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 3;
                        muxb_ctl = 1;
                        alu_func = 4;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SRA ;
                    end
                    'd4://SLLV rd,rt,rs
                    begin
                        //replaceID  = `SLLV ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 1'bx;//`IGN;
                        //end of `SLLV ;
                    end
                    'd6://SRLV rd,rt,rs
                    begin
                        //replaceID  = `SRLV ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SRLV ;
                    end
                    'd7://SRAV rd,rt,rs
                    begin
                        //replaceID  = `SRAV ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SRAV ;
                    end
                    'd8://JR rs
                    begin
                        //replaceID  = `JR ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 2;
                        fsm_dly = 1;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `JR ;
                    end
                    'd9://JALR jalr rs(rd=31) or jalr rd,rs
                    begin
                        //replaceID  = `JALR ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `JALR ;
                    end
                    'd12://SYSCALL
                    begin
                        //replaceID  = `SYSCALL ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SYSCALL ;
                    end
                    'd13://BREAK
                    begin
                        //replaceID  = `BREAK ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `BREAK ;
                    end
                    'd16://MFHI rd
                    begin
                        //replaceID  = `MFHI ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 6;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `MFHI ;
                    end
                    'd17://MTHI rs
                    begin
                        //replaceID  = `MTHI ;
                        ext_ctl = 0	;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 0;
                        alu_func = 31;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `MTHI ;
                    end
                    'd18://MFLO rd
                    begin
                        //replaceID  = `MFLO ;
                        ext_ctl = 0	;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 7;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `MFLO ;
                    end
                    'd19://MTLO rs
                    begin
                        //replaceID  = `MTLO ;
                        ext_ctl = 0	;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 7;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;

                        //end of `MTLO ;
                    end
                    'd24://MULT rs,rt
                    begin
                        //replaceID  = `MULT ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 2;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 9;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `MULT ;
                    end
                    'd25://MULTU rs,rt
                    begin
                        //replaceID  = `MULTU ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 2;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 8;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `MULTU ;
                    end
                    'd26://DIV rs,rt
                    begin
                        //replaceID  = `DIV ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 2;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 11;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `DIV ;
                    end
                    'd27://DIVU rs,rt
                    begin
                        //replaceID  = `DIVU ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 2;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 10;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `DIVU ;
                    end
                    'd32://ADD rd,rs,rt
                    begin
                        //replaceID  = `ADD ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 12;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `ADD ;
                    end
                    'd33://ADDU rd,rs,rt
                    begin
                        //replaceID  = `ADDU ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 12;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `ADDU ;
                    end
                    'd34://SUB rd,rs,rt
                    begin
                        //replaceID  = `SUB ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 14;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SUB ;
                    end
                    'd35://SUBU rd,rs,rt
                    begin
                        //replaceID  = `SUBU ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 15;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SUBU ;
                    end
                    'd36://AND rd,rs,rt
                    begin
                        //replaceID  = `AND ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 19;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `AND ;
                    end
                    'd37://OR rd,rs,rt
                    begin
                        //replaceID  = `OR ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 18;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `OR ;
                    end
                    'd38://XOR rd,rs,rt
                    begin
                        //replaceID  = `XOR ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 20;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `XOR ;
                    end
                    'd39://NOR rd,rs,rt
                    begin
                        //replaceID  = `NOR ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 21;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `NOR ;
                    end
                    'd42://SLT rd,rs,rt
                    begin
                        //replaceID  = `SLT ;
                        ext_ctl = 1;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 17;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SLT ;
                    end
                    'd43://SLTU rd,rs,rt
                    begin
                        //replaceID  = `SLTU ;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 2;
                        muxb_ctl = 1;
                        alu_func = 16;
                        alu_we = 1;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `SLTU ;
                    end
                    default:
                    begin
                        //replaceID  = `INVALID ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `INVALID ;
                    end
                endcase
            end
            'd1://regimm opreation
            begin
                case (inst_regimm) //synthesis parallel_case
                    'd0://BLTZ rs,offset(signed)
                    begin
                        //replaceID  = `BLTZ ;
                        ext_ctl = 4;
                        rd_sel = 0;
                        cmp_ctl = 6;
                        pc_gen_ctl = 4;
                        fsm_dly = 1;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `BLTZ ;
                    end
                    'd1://BGEZ rs,offset(signed)
                    begin
                        //replaceID  = `BGEZ ;
                        ext_ctl = 4;
                        rd_sel = 0;
                        cmp_ctl = 4;
                        pc_gen_ctl = 4;
                        fsm_dly = 1;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `BGEZ ;
                    end
                    'd16://BLTZAL rs,offset(signed)
                    begin
                        //replaceID  = `BLTZAL ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `BLTZAL ;
                    end
                    'd17://BGEZAL rs,offset(signed)
                    begin
                        //replaceID  = `BGEZAL ;
                        //replaceID  = `INVALID ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `INVALID ;
                    end
                    default:
                    begin
                        //replaceID   = `INVALID ;
                        //replaceID  = `INVALID ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `INVALID ;
                    end
                endcase
            end
            'd2://J imm26({pc[31:28],imm26,00})
            begin
                //replaceID  = `J ;
                ext_ctl = 3;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 1;
                fsm_dly = 6;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `J ;
            end
            'd3://JAL imm26({pc[31:28],imm26,00})
            begin
                //replaceID  = `JAL ;

                ext_ctl = 3;
                rd_sel = 3;
                cmp_ctl = 0;
                pc_gen_ctl = 1;
                fsm_dly = 6;
                muxa_ctl = 1;
                muxb_ctl = 1;
                alu_func = 22;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `JAL ;
            end
            'd4://BEQ rs,rt,offset(signed)
            begin
                //replaceID  = `BEQ ;
                ext_ctl = 4;
                rd_sel = 0;
                cmp_ctl = 1;
                pc_gen_ctl = 4;
                fsm_dly = 1;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `BEQ ;
            end
            'd5://BNE rs,rt,offset(signed)
            begin
                //replaceID  = `BNE ;
                ext_ctl = 4;
                rd_sel = 0;
                cmp_ctl = 2;
                pc_gen_ctl = 4;
                fsm_dly = 1;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `BNE ;
            end
            'd6://BLEZ rs,offset(signed)
            begin
                //replaceID  = `BLEZ ;
                ext_ctl = 4;
                rd_sel = 0;
                cmp_ctl = 3;
                pc_gen_ctl = 4;
                fsm_dly = 1;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `BLEZ ;
            end
            'd7://BGTZ rs,offset(signed)
            begin
                //replaceID  = `BGTZ ;
                ext_ctl = 4;
                rd_sel = 0;
                cmp_ctl = 5;
                pc_gen_ctl = 4;
                fsm_dly = 1;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `BGTZ ;
            end
            'd8://ADDI rt,rs,imm16(singed)
            begin
                //replaceID  = `ADDI ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `ADDI ;
            end
            'd9://ADDIU rt,rs,imm16(singed)
            begin
                //replaceID  = `ADDIU ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `ADDIU ;
            end
            'd10://SLTI rt,rs,imm16(singed)
            begin
                //replaceID  = `SLTI ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 17;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `SLTI ;
            end
            'd11://SLTIU rt,rs,imm16(singed)
            begin
                //replaceID  = `SLTIU ;
                ext_ctl = 2;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 16;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `SLTIU ;
            end
            'd12://ANDI rt,rs,imm16(singed)
            begin
                //replaceID  = `ANDI ;
                ext_ctl = 2;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 19;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `ANDI ;
            end
            'd13://ORI rt,rs,imm16(singed)
            begin
                //replaceID  = `ORI ;
                ext_ctl = 2;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 18;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `ORI ;
            end
            'd14://XORI rt,rs,imm16(singed)
            begin
                //replaceID  = `XORI ;
                ext_ctl = 2;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 20;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  1;
                wb_mux = 0;
                //end of `XORI ;
            end
            'd15://LUI rt,imm16
            begin
                //replaceID  = `LUI ;
                ext_ctl = 6;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 23;
                alu_we = 1;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `LUI ;
            end
            'd16://COP0 func
            begin
                case(inst_cop0_func) //synthesis parallel_case
                    'd0://mfc0 rt,rd // GPR[rd] = CPR[rt] //differ to mips32 definition
                        //read saved PC
                    begin
                        //replaceID  = `MFC0;
                        ext_ctl = 0;
                        rd_sel = 1;
                        cmp_ctl = 0;
                        pc_gen_ctl = 5;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 2;
                        alu_func = 22;
                        alu_we = 1;
                        dmem_ctl = 3;
                        wb_we =  0;
                        wb_mux = 0;
                    end

                    'd4://mtc0 rt,rd // CPR[rd] = GPR[rt] //follow the mips32 definition
                    begin	 //return from interrupt
                        $display("mtco");
                        //replaceID  = `MTC0;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 6;
                        fsm_dly = 4;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                    end
                    default:
                    begin
                        //replaceID  = `INVALID ;
                        ext_ctl = 0;
                        rd_sel = 0;
                        cmp_ctl = 0;
                        pc_gen_ctl = 0;
                        fsm_dly = 0;
                        muxa_ctl = 0;
                        muxb_ctl = 0;
                        alu_func = 0;
                        alu_we = 0;
                        dmem_ctl = 0;
                        wb_we =  0;
                        wb_mux = 0;
                        //end of `INVALID ;
                    end
                endcase
            end
            'd32://LB rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `LB ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 2;
                wb_we =  1;
                wb_mux = 1;
                //end of `LB ;
            end
            'd33://LH rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `LH ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 8;
                wb_we =  1;
                wb_mux = 1;
                //end of `LH ;
            end
            'd34://LWL rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `LWL ;
                ext_ctl = 0;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 0;
                fsm_dly = 0;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `LWL ;
            end
            'd35://LW rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `LW ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 6;
                wb_we =  1;
                wb_mux = 1;
                //end of `LW ;
            end
            'd36://LBU rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `LBU ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 4;
                wb_we =  1;
                wb_mux = 1;
                //end of `LBU ;
            end
            'd37://LHU rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `LHU ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 10;
                wb_we =  1;
                wb_mux = 1;
                //end of `LHU ;
            end
            'd38://LWR rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `LWR ;
                ext_ctl = 0;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 0;
                fsm_dly = 0;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `LWR ;
            end
            'd40://SB rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `SB ;
                ext_ctl = 1;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 1;
                wb_we =  0;
                wb_mux = 0;
                //end of `SB ;
            end
            'd41://SH rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `SH ;
                ext_ctl = 1;
                rd_sel = 2;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 7;
                wb_we =  0;
                wb_mux = 0;
                //end of `SH ;
            end
            'd42://SWL rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `SWL ;
                ext_ctl = 0;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 0;
                fsm_dly = 0;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `SWL ;
            end
            'd43://SW rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `SW ;
                ext_ctl = 1;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 5;
                fsm_dly = 0;
                muxa_ctl = 2;
                muxb_ctl = 2;
                alu_func = 12;
                alu_we = 0;
                dmem_ctl = 5;
                wb_we =  0;
                wb_mux = 0;
                //end of `SW ;
            end
            'd46://SWR rt,offset(base) (offset:signed;base:rs)
            begin
                //replaceID  = `SWR ;
                ext_ctl = 0;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 0;
                fsm_dly = 0;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `SWR ;
            end
            default:
            begin
                //replaceID  = `INVALID ;
                ext_ctl = 0;
                rd_sel = 0;
                cmp_ctl = 0;
                pc_gen_ctl = 0;
                fsm_dly = 0;
                muxa_ctl = 0;
                muxb_ctl = 0;
                alu_func = 0;
                alu_we = 0;
                dmem_ctl = 0;
                wb_we =  0;
                wb_mux = 0;
                //end of `INVALID ;  //replaceID   = `INVALID ;
            end
        endcase
    end
endmodule



module pipelinedregs (
        clk,id2ra_ctl_clr,id2ra_ctl_cls,ra2ex_ctl_clr,
        alu_func_i,alu_we_i,cmp_ctl_i,dmem_ctl_i,ext_ctl_i,
        muxa_ctl_i,muxb_ctl_i,pc_gen_ctl_i,rd_sel_i,wb_mux_ctl_i,
        wb_we_i,alu_func_o,alu_we_o,cmp_ctl_o,dmem_ctl_o,dmem_ctl_ur_o,
        ext_ctl,muxa_ctl_o,muxb_ctl_o,pc_gen_ctl_o,rd_sel_o,wb_mux_ctl_o,wb_we_o
    ) ;

    input clk;
    wire clk;
    input id2ra_ctl_clr;
    wire id2ra_ctl_clr;
    input id2ra_ctl_cls;
    wire id2ra_ctl_cls;
    input ra2ex_ctl_clr;
    wire ra2ex_ctl_clr;
    input [4:0] alu_func_i;
    wire [4:0] alu_func_i;
    input [0:0] alu_we_i;
    wire [0:0] alu_we_i;
    input [2:0] cmp_ctl_i;
    wire [2:0] cmp_ctl_i;
    input [3:0] dmem_ctl_i;
    wire [3:0] dmem_ctl_i;
    input [2:0] ext_ctl_i;
    wire [2:0] ext_ctl_i;
    input [1:0] muxa_ctl_i;
    wire [1:0] muxa_ctl_i;
    input [1:0] muxb_ctl_i;
    wire [1:0] muxb_ctl_i;
    input [2:0] pc_gen_ctl_i;
    wire [2:0] pc_gen_ctl_i;
    input [1:0] rd_sel_i;
    wire [1:0] rd_sel_i;
    input [0:0] wb_mux_ctl_i;
    wire [0:0] wb_mux_ctl_i;
    input [0:0] wb_we_i;
    wire [0:0] wb_we_i;
    output [4:0] alu_func_o;
    wire [4:0] alu_func_o;
    output [0:0] alu_we_o;
    wire [0:0] alu_we_o;
    output [2:0] cmp_ctl_o;
    wire [2:0] cmp_ctl_o;
    output [3:0] dmem_ctl_o;
    wire [3:0] dmem_ctl_o;
    output [3:0] dmem_ctl_ur_o;
    wire [3:0] dmem_ctl_ur_o;
    output [2:0] ext_ctl;
    wire [2:0] ext_ctl;
    output [1:0] muxa_ctl_o;
    wire [1:0] muxa_ctl_o;
    output [1:0] muxb_ctl_o;
    wire [1:0] muxb_ctl_o;
    output [2:0] pc_gen_ctl_o;
    wire [2:0] pc_gen_ctl_o;
    output [1:0] rd_sel_o;
    wire [1:0] rd_sel_o;
    output [0:0] wb_mux_ctl_o;
    wire [0:0] wb_mux_ctl_o;
    output [0:0] wb_we_o;
    wire [0:0] wb_we_o;


    wire NET7643;
    wire [0:0] BUS4987;
    wire [1:0] BUS5008;
    wire [1:0] BUS5483;
    wire [0:0] BUS5639;
    wire [0:0] BUS5651;
    wire [3:0] BUS5666;
    wire [4:0] BUS5674;
    wire [0:0] BUS5682;
    wire [0:0] BUS5690;
    wire [0:0] BUS5790;
    wire [0:0] BUS7299;
    wire [0:0] BUS7822;


    muxb_ctl_reg_clr_cls U1
                         (
                             .clk(clk),
                             .clr(id2ra_ctl_clr),
                             .cls(id2ra_ctl_cls),
                             .muxb_ctl_i(muxb_ctl_i),
                             .muxb_ctl_o(BUS5483)
                         );



    wb_mux_ctl_reg_clr_cls U10
                           (
                               .clk(clk),
                               .clr(id2ra_ctl_clr),
                               .cls(id2ra_ctl_cls),
                               .wb_mux_ctl_i(wb_mux_ctl_i),
                               .wb_mux_ctl_o(BUS5651)
                           );



    wb_we_reg_clr_cls U11
                      (
                          .clk(clk),
                          .clr(id2ra_ctl_clr),
                          .cls(id2ra_ctl_cls),
                          .wb_we_i(wb_we_i),
                          .wb_we_o(BUS5639)
                      );



    wb_we_reg U12
              (
                  .clk(clk),
                  .wb_we_i(NET7643),
                  .wb_we_o(wb_we_o)
              );



    wb_mux_ctl_reg_clr U13
                       (
                           .clk(clk),
                           .clr(ra2ex_ctl_clr),
                           .wb_mux_ctl_i(BUS5651),
                           .wb_mux_ctl_o(BUS5690)
                       );



    muxb_ctl_reg_clr U14
                     (
                         .clk(clk),
                         .clr(ra2ex_ctl_clr),
                         .muxb_ctl_i(BUS5483),
                         .muxb_ctl_o(muxb_ctl_o)
                     );



    dmem_ctl_reg_clr U15
                     (
                         .clk(clk),
                         .clr(ra2ex_ctl_clr),
                         .dmem_ctl_i(BUS5666),
                         .dmem_ctl_o(dmem_ctl_ur_o)
                     );



    alu_func_reg_clr U16
                     (
                         .alu_func_i(BUS5674),
                         .alu_func_o(alu_func_o),
                         .clk(clk),
                         .clr(ra2ex_ctl_clr)
                     );



    muxa_ctl_reg_clr U17
                     (
                         .clk(clk),
                         .clr(ra2ex_ctl_clr),
                         .muxa_ctl_i(BUS5008),
                         .muxa_ctl_o(muxa_ctl_o)
                     );



    wb_mux_ctl_reg U18
                   (
                       .clk(clk),
                       .wb_mux_ctl_i(BUS5790),
                       .wb_mux_ctl_o(wb_mux_ctl_o)
                   );



    wb_we_reg_clr U19
                  (
                      .clk(clk),
                      .clr(ra2ex_ctl_clr),
                      .wb_we_i(BUS5639),
                      .wb_we_o(BUS5682)
                  );



    cmp_ctl_reg_clr_cls U2
                        (
                            .clk(clk),
                            .clr(id2ra_ctl_clr),
                            .cls(id2ra_ctl_cls),
                            .cmp_ctl_i(cmp_ctl_i),
                            .cmp_ctl_o(cmp_ctl_o)
                        );



    wb_we_reg U20
              (
                  .clk(clk),
                  .wb_we_i(BUS5682),
                  .wb_we_o(BUS7822)
              );



    wb_mux_ctl_reg U21
                   (
                       .clk(clk),
                       .wb_mux_ctl_i(BUS5690),
                       .wb_mux_ctl_o(BUS5790)
                   );



    wb_we_reg U22
              (
                  .clk(clk),
                  .wb_we_i(BUS7299),
                  .wb_we_o(alu_we_o)
              );



    assign NET7643 = alu_we_o[0] | BUS7822[0];


    alu_we_reg_clr U24
                   (
                       .alu_we_i(BUS4987),
                       .alu_we_o(BUS7299),
                       .clk(clk),
                       .clr(ra2ex_ctl_clr)
                   );



    alu_func_reg_clr_cls U26
                         (
                             .alu_func_i(alu_func_i),
                             .alu_func_o(BUS5674),
                             .clk(clk),
                             .clr(id2ra_ctl_clr),
                             .cls(id2ra_ctl_cls)
                         );



    dmem_ctl_reg_clr_cls U3
                         (
                             .clk(clk),
                             .clr(id2ra_ctl_clr),
                             .cls(id2ra_ctl_cls),
                             .dmem_ctl_i(dmem_ctl_i),
                             .dmem_ctl_o(BUS5666)
                         );



    ext_ctl_reg_clr_cls U4
                        (
                            .clk(clk),
                            .clr(id2ra_ctl_clr),
                            .cls(id2ra_ctl_cls),
                            .ext_ctl_i(ext_ctl_i),
                            .ext_ctl_o(ext_ctl)
                        );



    rd_sel_reg_clr_cls U5
                       (
                           .clk(clk),
                           .clr(id2ra_ctl_clr),
                           .cls(id2ra_ctl_cls),
                           .rd_sel_i(rd_sel_i),
                           .rd_sel_o(rd_sel_o)
                       );



    alu_we_reg_clr_cls U6
                       (
                           .alu_we_i(alu_we_i),
                           .alu_we_o(BUS4987),
                           .clk(clk),
                           .clr(id2ra_ctl_clr),
                           .cls(id2ra_ctl_cls)
                       );



    muxa_ctl_reg_clr_cls U7
                         (
                             .clk(clk),
                             .clr(id2ra_ctl_clr),
                             .cls(id2ra_ctl_cls),
                             .muxa_ctl_i(muxa_ctl_i),
                             .muxa_ctl_o(BUS5008)
                         );



    pc_gen_ctl_reg_clr_cls U8
                           (
                               .clk(clk),
                               .clr(id2ra_ctl_clr),
                               .cls(id2ra_ctl_cls),
                               .pc_gen_ctl_i(pc_gen_ctl_i),
                               .pc_gen_ctl_o(pc_gen_ctl_o)
                           );



    dmem_ctl_reg U9
                 (
                     .clk(clk),
                     .dmem_ctl_i(dmem_ctl_ur_o),
                     .dmem_ctl_o(dmem_ctl_o)
                 );



endmodule

module decode_pipe
    (
        clk,id2ra_ctl_clr,id2ra_ctl_cls,
        ra2ex_ctl_clr,ins_i,alu_func_o,alu_we_o,
        cmp_ctl_o,dmem_ctl_o,dmem_ctl_ur_o,ext_ctl_o,
        fsm_dly,muxa_ctl_o,muxb_ctl_o,pc_gen_ctl_o,rd_sel_o,
        wb_mux_ctl_o,wb_we_o
    ) ;

    input clk;
    wire clk;
    input id2ra_ctl_clr;
    wire id2ra_ctl_clr;
    input id2ra_ctl_cls;
    wire id2ra_ctl_cls;
    input ra2ex_ctl_clr;
    wire ra2ex_ctl_clr;
    input [31:0] ins_i;
    wire [31:0] ins_i;
    output [4:0] alu_func_o;
    wire [4:0] alu_func_o;
    output [0:0] alu_we_o;
    wire [0:0] alu_we_o;
    output [2:0] cmp_ctl_o;
    wire [2:0] cmp_ctl_o;
    output [3:0] dmem_ctl_o;
    wire [3:0] dmem_ctl_o;
    output [3:0] dmem_ctl_ur_o;
    wire [3:0] dmem_ctl_ur_o;
    output [2:0] ext_ctl_o;
    wire [2:0] ext_ctl_o;
    output [2:0] fsm_dly;
    wire [2:0] fsm_dly;
    output [1:0] muxa_ctl_o;
    wire [1:0] muxa_ctl_o;
    output [1:0] muxb_ctl_o;
    wire [1:0] muxb_ctl_o;
    output [2:0] pc_gen_ctl_o;
    wire [2:0] pc_gen_ctl_o;
    output [1:0] rd_sel_o;
    wire [1:0] rd_sel_o;
    output [0:0] wb_mux_ctl_o;
    wire [0:0] wb_mux_ctl_o;
    output [0:0] wb_we_o;
    wire [0:0] wb_we_o;


    wire [4:0] BUS2040;
    wire [0:0] BUS2048;
    wire [2:0] BUS2056;
    wire [3:0] BUS2064;
    wire [2:0] BUS2072;
    wire [1:0] BUS2086;
    wire [1:0] BUS2094;
    wire [2:0] BUS2102;
    wire [1:0] BUS2110;
    wire [0:0] BUS2118;
    wire [0:0] BUS2126;


    decoder idecoder
            (
                .alu_func(BUS2040),
                .alu_we(BUS2048),
                .cmp_ctl(BUS2056),
                .dmem_ctl(BUS2064),
                .ext_ctl(BUS2072),
                .fsm_dly(fsm_dly),
                .ins_i(ins_i),
                .muxa_ctl(BUS2086),
                .muxb_ctl(BUS2094),
                .pc_gen_ctl(BUS2102),
                .rd_sel(BUS2110),
                .wb_mux(BUS2118),
                .wb_we(BUS2126)
            );



    pipelinedregs pipereg
                  (
                      .alu_func_i(BUS2040),
                      .alu_func_o(alu_func_o),
                      .alu_we_i(BUS2048),
                      .alu_we_o(alu_we_o),
                      .clk(clk),
                      .cmp_ctl_i(BUS2056),
                      .cmp_ctl_o(cmp_ctl_o),
                      .dmem_ctl_i(BUS2064),
                      .dmem_ctl_o(dmem_ctl_o),
                      .dmem_ctl_ur_o(dmem_ctl_ur_o),
                      .ext_ctl(ext_ctl_o),
                      .ext_ctl_i(BUS2072),
                      .id2ra_ctl_clr(id2ra_ctl_clr),
                      .id2ra_ctl_cls(id2ra_ctl_cls),
                      .muxa_ctl_i(BUS2086),
                      .muxa_ctl_o(muxa_ctl_o),
                      .muxb_ctl_i(BUS2094),
                      .muxb_ctl_o(muxb_ctl_o),
                      .pc_gen_ctl_i(BUS2102),
                      .pc_gen_ctl_o(pc_gen_ctl_o),
                      .ra2ex_ctl_clr(ra2ex_ctl_clr),
                      .rd_sel_i(BUS2110),
                      .rd_sel_o(rd_sel_o),
                      .wb_mux_ctl_i(BUS2118),
                      .wb_mux_ctl_o(wb_mux_ctl_o),
                      .wb_we_i(BUS2126),
                      .wb_we_o(wb_we_o)
                  );



endmodule





/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 





module fw_latch5(input clk,input[4:0]d,output reg  [4:0]q);
    always @ (posedge clk) q<=d;
endmodule

module fw_latch1(input clk,input d,output reg q);
    always @ (posedge clk) q<=d;
endmodule

module forward_node (
        input [4:0]rn,
        input [4:0]alu_wr_rn,
        input alu_we,
        input [4:0]mem_wr_rn,
        input mem_we,
        output  wire[2:0]mux_fw
    );
    assign mux_fw = ((alu_we)&&(alu_wr_rn==rn)&&(alu_wr_rn!=0))?3'b001:
           ((mem_we)&&(mem_wr_rn==rn)&&(mem_wr_rn!=0))?3'b010:
           3'b100;
endmodule

module fwd_mux(
        input [31:0]din,
        output reg [31:0]dout,
        input [31:0]fw_alu	,
        input [2:0]fw_ctl,
        input [31:0]fw_dmem
    );
    always@(*)
    case (fw_ctl)
        3'b001 :dout=fw_alu;
        3'b010 :dout=fw_dmem;
         default
         dout=din;
    endcase
endmodule

module forward  (    input alu_we,
    input clk,
    input mem_We,
    input [4:0] fw_alu_rn,
    input [4:0] fw_mem_rn,
    input [4:0] rns_i,
    input [4:0] rnt_i,
    output [2:0] alu_rs_fw,
    output [2:0] alu_rt_fw,
    output [2:0] cmp_rs_fw,
    output [2:0] cmp_rt_fw,
    output [2:0] dmem_fw

) ;


    wire [2:0] BUS1345;
    wire [4:0] BUS82;
    wire [4:0] BUS937;

    forward_node fw_alu_rs
                 (
                     .alu_we(alu_we),
                     .alu_wr_rn(fw_alu_rn),
                     .mem_we(mem_We),
                     .mem_wr_rn(fw_mem_rn),
                     .mux_fw(alu_rs_fw),
                     .rn(BUS82)
                 );



    forward_node fw_alu_rt
                 (
                     .alu_we(alu_we),
                     .alu_wr_rn(fw_alu_rn),
                     .mem_we(mem_We),
                     .mem_wr_rn(fw_mem_rn),
                     .mux_fw(BUS1345),
                     .rn(BUS937)
                 );



    forward_node fw_cmp_rs
                 (
                     .alu_we(alu_we),
                     .alu_wr_rn(fw_alu_rn),
                     .mem_we(mem_We),
                     .mem_wr_rn(fw_mem_rn),
                     .mux_fw(cmp_rs_fw),
                     .rn(rns_i)
                 );



    forward_node fw_cmp_rt
                 (
                     .alu_we(alu_we),
                     .alu_wr_rn(fw_alu_rn),
                     .mem_we(mem_We),
                     .mem_wr_rn(fw_mem_rn),
                     .mux_fw(cmp_rt_fw),
                     .rn(rnt_i)
                 );



    fw_latch5 fw_reg_rns
              (
                  .clk(clk),
                  .d(rns_i),
                  .q(BUS82)
              );



    fw_latch5 fw_reg_rnt
              (
                  .clk(clk),
                  .d(rnt_i),
                  .q(BUS937)
              );


    assign alu_rt_fw[2:0] = BUS1345[2:0];
    assign dmem_fw[2:0] = BUS1345[2:0];

endmodule


/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 





module mem_module  (
    input clk,
    input [31:0] din,
    input [31:0] dmem_addr_i,
    input [3:0] dmem_ctl,
    input [31:0] zZ_din,
    output [31:0] Zz_addr,
    output [31:0] Zz_dout,
    output [3:0] Zz_wr_en,
    output [31:0] dout
    ) ;



    wire [3:0] BUS512;
    wire [1:0] BUS629;
    wire [31:0] BUS650;


    infile_dmem_ctl_reg dmem_ctl_post
                        (
                            .byte_addr_o(BUS629),
                            .clk(clk),
                            .ctl_i(dmem_ctl),
                            .ctl_o(BUS512),
                            .dmem_addr_i(BUS650)
                        );



    mem_addr_ctl i_mem_addr_ctl
                 (
                     .addr_i(BUS650),
                     .ctl(dmem_ctl),
                     .wr_en(Zz_wr_en)
                 );



    mem_din_ctl i_mem_din_ctl
                (
                    .ctl(dmem_ctl),
                    .din(din),
                    .dout(Zz_dout)
                );



    mem_dout_ctl i_mem_dout_ctl
                 (
                     .byte_addr(BUS629),
                     .ctl(BUS512),
                     .din(zZ_din),
                     .dout(dout)
                 );



    assign BUS650[31:0] = dmem_addr_i[31:0];

    assign Zz_addr[31:0] = BUS650[31:0];

endmodule


module infile_dmem_ctl_reg(
        input clk,
        input [3:0]ctl_i,
        input [31:0]dmem_addr_i,
        output reg [1:0]byte_addr_o,
        output reg [3:0]ctl_o
    );

    wire   [1:0]byte_addr_i;
    assign byte_addr_i = dmem_addr_i[1:0] ;

    always @(posedge clk)
    begin
        ctl_o<=(dmem_addr_i[31]==0)?ctl_i:0;
        byte_addr_o<=byte_addr_i;
    end

endmodule

module mem_addr_ctl(
        input [3:0]ctl,
        input [31:0]addr_i,
        output reg[3:0]wr_en
    );
    always@(*)
    case (ctl)
        1:
        begin
            case(addr_i[1:0])
                0:wr_en = 4'b1000;
                1:wr_en = 4'b0100;
                2:wr_en = 4'b0010;
                3:wr_en = 4'b0001;
                default :wr_en = 4'b000;
            endcase
        end
        7  :
        begin
            case(addr_i[1:0])
                'd0:wr_en=4'b1100;
                'd2:wr_en=4'b0011;
                default :wr_en = 4'b0000;
            endcase
        end
        5 :
        begin
            wr_en=4'b1111;
        end
        default wr_en=4'b0000;
    endcase

endmodule


module mem_dout_ctl(
        input [1:0]byte_addr,
        input [3:0]ctl,
        input [31:0] din,
        output reg [31:0] dout
    );

    always @(*)
    case (ctl)

        2 :
        case (byte_addr)

			'd0:dout={{24{din[31]}},din[31:24]};
            'd1:dout={{24{din[23]}},din[23:16]};
            'd2:dout={{24{din[15]}},din[15:8]};
            'd3:dout={{24{din[7]}},din[7:0] };
            default :
                dout=32'bX;
        endcase 
        4 :
        case (byte_addr)
            'd3:dout={24'b0,din[7:0]};
            'd2:dout={24'b0,din[15:8]};
            'd1:dout={24'b0,din[23:16]};
            'd0:dout={24'b0,din[31:24]};
            default :
                dout=32'bX;
        endcase
        10 :
        case (byte_addr)
            'd0:dout={16'b0,din[31:24],din[23:16]};
            'd2:dout={16'b0,din[15:8],din[7 :0]};
            default:dout=32'bX;
        endcase
        8 :
        case (byte_addr)
   			'd0 :dout={{16{din[31]}},din[31:24],din[23:16]};
            'd2 :dout={{16{din[15]}},din[15:8],din[7 :0]};
            default:dout=32'bX;
        endcase
        6  :
            dout=din;
        default :
            dout=0;
    endcase
endmodule

module mem_din_ctl(
        input [3:0]ctl,
        input [31:0]din,
        output reg [31:0]dout
    );

    always @(*)

    case (ctl)
        1   :
            dout={din[7:0],din[7:0],din[7:0],din[7:0]};
        7   :
            dout = {din[15:0],din[15:0]};
        5   :
            dout =din;
        default dout=32'bX;
    endcase

endmodule
/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 





/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/

/******************************************************************
 *                                                                * 
 *    Author: Liwei                                               * 
 *                                                                * 
 *    This file is part of the "mips789" project.                 * 
 *    Downloaded from:                                            * 
 *    http://www.opencores.org/pdownloads.cgi/list/mips789        * 
 *                                                                * 
 *    If you encountered any problem, please contact me via       * 
 *    Email:mcupro@opencores.org  or mcupro@163.com               * 
 *                                                                * 
 ******************************************************************/












































































































































































 




module cal_cpi (		 	   //just used to calculate CPI(Cycles Per Instruction) for stimulation
        input clk,
        input rst,
        input is_nop,
        output reg [100:0] ins_no,
        output reg [100:0] clk_no);

    always @(posedge clk  )
        if (~rst )clk_no=0;
        else
            clk_no = 1+clk_no;

    always @(posedge clk )
        if (~rst )ins_no=0;
        else if (~is_nop)
            ins_no = 1+ins_no;
endmodule


module add32(
        input [31:0]d_i,
        output [31:0]d_o
    );
    assign d_o = d_i + 4;
endmodule


module jack(
        input [31:0] ins_i ,
        output [4:0] rs_o,
        output [4:0] rt_o,
        output [4:0] rd_o
    );
    assign rs_o = ins_i[25:21];
    assign rt_o = ins_i[20:16];
    assign rd_o = ins_i[15:11];
endmodule



module wb_mux(
        input [31:0]alu_i,
        input [31:0]dmem_i,
        input sel,
        output [31:0]wb_o
    );

    assign wb_o = (sel==1)?dmem_i:alu_i;

endmodule

module or32(
        input [31:0]a,
        input [31:0]b,
        output [31:0]c
    );

    assign c = a|b ;

endmodule

module rd_sel(
        input [4:0]rd_i,
        input [4:0]rt_i,
        input[1:0] ctl,
        output reg [4:0]rd_o
    );

    always @(*)
    case (ctl)
        1:rd_o=rd_i;
        2:rd_o=rt_i;
        3:rd_o='d31;
        default :
            rd_o=0;
    endcase
endmodule

//these modules below are genated automaticly by a software written in C language...
//Some of these may not be used

module ext_ctl_reg_clr_cls(input[3-1:0] ext_ctl_i,output reg[3-1:0] ext_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) ext_ctl_o<=0;else if(cls)ext_ctl_o<=ext_ctl_o;else ext_ctl_o<=ext_ctl_i;endmodule
module rd_sel_reg_clr_cls(input[2-1:0] rd_sel_i,output reg[2-1:0] rd_sel_o,input clk,input clr,input cls);always@(posedge clk)if(clr) rd_sel_o<=0;else if(cls)rd_sel_o<=rd_sel_o;else rd_sel_o<=rd_sel_i;endmodule
module cmp_ctl_reg_clr_cls(input[3-1:0] cmp_ctl_i,output reg[3-1:0] cmp_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) cmp_ctl_o<=0;else if(cls)cmp_ctl_o<=cmp_ctl_o;else cmp_ctl_o<=cmp_ctl_i;endmodule
module pc_gen_ctl_reg_clr_cls(input[3-1:0] pc_gen_ctl_i,output reg[3-1:0] pc_gen_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) pc_gen_ctl_o<=0;else if(cls)pc_gen_ctl_o<=pc_gen_ctl_o;else pc_gen_ctl_o<=pc_gen_ctl_i;endmodule
module fsm_ctl_reg_clr_cls(input[3-1:0] fsm_ctl_i,output reg[3-1:0] fsm_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) fsm_ctl_o<=0;else if(cls)fsm_ctl_o<=fsm_ctl_o;else fsm_ctl_o<=fsm_ctl_i;endmodule
module muxa_ctl_reg_clr_cls(input[2-1:0] muxa_ctl_i,output reg[2-1:0] muxa_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) muxa_ctl_o<=0;else if(cls)muxa_ctl_o<=muxa_ctl_o;else muxa_ctl_o<=muxa_ctl_i;endmodule
module muxb_ctl_reg_clr_cls(input[2-1:0] muxb_ctl_i,output reg[2-1:0] muxb_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) muxb_ctl_o<=0;else if(cls)muxb_ctl_o<=muxb_ctl_o;else muxb_ctl_o<=muxb_ctl_i;endmodule
module alu_func_reg_clr_cls(input[5-1:0] alu_func_i,output reg[5-1:0] alu_func_o,input clk,input clr,input cls);always@(posedge clk)if(clr) alu_func_o<=0;else if(cls)alu_func_o<=alu_func_o;else alu_func_o<=alu_func_i;endmodule
module alu_we_reg_clr_cls(input[1-1:0] alu_we_i,output reg[1-1:0] alu_we_o,input clk,input clr,input cls);always@(posedge clk)if(clr) alu_we_o<=0;else if(cls)alu_we_o<=alu_we_o;else alu_we_o<=alu_we_i;endmodule
module dmem_ctl_reg_clr_cls(input[4-1:0] dmem_ctl_i,output reg[4-1:0] dmem_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) dmem_ctl_o<=0;else if(cls)dmem_ctl_o<=dmem_ctl_o;else dmem_ctl_o<=dmem_ctl_i;endmodule
module wb_mux_ctl_reg_clr_cls(input[1-1:0] wb_mux_ctl_i,output reg[1-1:0] wb_mux_ctl_o,input clk,input clr,input cls);always@(posedge clk)if(clr) wb_mux_ctl_o<=0;else if(cls)wb_mux_ctl_o<=wb_mux_ctl_o;else wb_mux_ctl_o<=wb_mux_ctl_i;endmodule
module wb_we_reg_clr_cls(input[1-1:0] wb_we_i,output reg[1-1:0] wb_we_o,input clk,input clr,input cls);always@(posedge clk)if(clr) wb_we_o<=0;else if(cls)wb_we_o<=wb_we_o;else wb_we_o<=wb_we_i;endmodule
module ins_reg_clr_cls(input[32-1:0] ins_i,output reg[32-1:0] ins_o,input clk,input clr,input cls);always@(posedge clk)if(clr) ins_o<=0;else if(cls)ins_o<=ins_o;else ins_o<=ins_i;endmodule
module pc_reg_clr_cls(input[32-1:0] pc_i,output reg[32-1:0] pc_o,input clk,input clr,input cls);always@(posedge clk)if(clr) pc_o<=0;else if(cls)pc_o<=pc_o;else pc_o<=pc_i;endmodule
module spc_reg_clr_cls(input[32-1:0] spc_i,output reg[32-1:0] spc_o,input clk,input clr,input cls);always@(posedge clk)if(clr) spc_o<=0;else if(cls)spc_o<=spc_o;else spc_o<=spc_i;endmodule
module r1_reg_clr_cls(input[1-1:0] r1_i,output reg[1-1:0] r1_o,input clk,input clr,input cls);always@(posedge clk)if(clr) r1_o<=0;else if(cls)r1_o<=r1_o;else r1_o<=r1_i;endmodule
module r2_reg_clr_cls(input[2-1:0] r2_i,output reg[2-1:0] r2_o,input clk,input clr,input cls);always@(posedge clk)if(clr) r2_o<=0;else if(cls)r2_o<=r2_o;else r2_o<=r2_i;endmodule
module r3_reg_clr_cls(input[3-1:0] r3_i,output reg[3-1:0] r3_o,input clk,input clr,input cls);always@(posedge clk)if(clr) r3_o<=0;else if(cls)r3_o<=r3_o;else r3_o<=r3_i;endmodule
module r4_reg_clr_cls(input[4-1:0] r4_i,output reg[4-1:0] r4_o,input clk,input clr,input cls);always@(posedge clk)if(clr) r4_o<=0;else if(cls)r4_o<=r4_o;else r4_o<=r4_i;endmodule
module r5_reg_clr_cls(input[5-1:0] r5_i,output reg[5-1:0] r5_o,input clk,input clr,input cls);always@(posedge clk)if(clr) r5_o<=0;else if(cls)r5_o<=r5_o;else r5_o<=r5_i;endmodule
module r32_reg_clr_cls(input[32-1:0] r32_i,output reg[32-1:0] r32_o,input clk,input clr,input cls);always@(posedge clk)if(clr) r32_o<=0;else if(cls)r32_o<=r32_o;else r32_o<=r32_i;endmodule


module ext_ctl_reg_clr(input[3-1:0] ext_ctl_i,output reg[3-1:0] ext_ctl_o,input clk,input clr);always@(posedge clk)if(clr)ext_ctl_o<=0;else ext_ctl_o<=ext_ctl_i;endmodule
module rd_sel_reg_clr(input[2-1:0] rd_sel_i,output reg[2-1:0] rd_sel_o,input clk,input clr);always@(posedge clk)if(clr)rd_sel_o<=0;else rd_sel_o<=rd_sel_i;endmodule
module cmp_ctl_reg_clr(input[3-1:0] cmp_ctl_i,output reg[3-1:0] cmp_ctl_o,input clk,input clr);always@(posedge clk)if(clr)cmp_ctl_o<=0;else cmp_ctl_o<=cmp_ctl_i;endmodule
module pc_gen_ctl_reg_clr(input[3-1:0] pc_gen_ctl_i,output reg[3-1:0] pc_gen_ctl_o,input clk,input clr);always@(posedge clk)if(clr)pc_gen_ctl_o<=0;else pc_gen_ctl_o<=pc_gen_ctl_i;endmodule
module fsm_ctl_reg_clr(input[3-1:0] fsm_ctl_i,output reg[3-1:0] fsm_ctl_o,input clk,input clr);always@(posedge clk)if(clr)fsm_ctl_o<=0;else fsm_ctl_o<=fsm_ctl_i;endmodule
module muxa_ctl_reg_clr(input[2-1:0] muxa_ctl_i,output reg[2-1:0] muxa_ctl_o,input clk,input clr);always@(posedge clk)if(clr)muxa_ctl_o<=0;else muxa_ctl_o<=muxa_ctl_i;endmodule
module muxb_ctl_reg_clr(input[2-1:0] muxb_ctl_i,output reg[2-1:0] muxb_ctl_o,input clk,input clr);always@(posedge clk)if(clr)muxb_ctl_o<=0;else muxb_ctl_o<=muxb_ctl_i;endmodule
module alu_func_reg_clr(input[5-1:0] alu_func_i,output reg[5-1:0] alu_func_o,input clk,input clr);always@(posedge clk)if(clr)alu_func_o<=0;else alu_func_o<=alu_func_i;endmodule
module alu_we_reg_clr(input[1-1:0] alu_we_i,output reg[1-1:0] alu_we_o,input clk,input clr);always@(posedge clk)if(clr)alu_we_o<=0;else alu_we_o<=alu_we_i;endmodule
module dmem_ctl_reg_clr(input[4-1:0] dmem_ctl_i,output reg[4-1:0] dmem_ctl_o,input clk,input clr);always@(posedge clk)if(clr)dmem_ctl_o<=0;else dmem_ctl_o<=dmem_ctl_i;endmodule
module wb_mux_ctl_reg_clr(input[1-1:0] wb_mux_ctl_i,output reg[1-1:0] wb_mux_ctl_o,input clk,input clr);always@(posedge clk)if(clr)wb_mux_ctl_o<=0;else wb_mux_ctl_o<=wb_mux_ctl_i;endmodule
module wb_we_reg_clr(input[1-1:0] wb_we_i,output reg[1-1:0] wb_we_o,input clk,input clr);always@(posedge clk)if(clr)wb_we_o<=0;else wb_we_o<=wb_we_i;endmodule
module ins_reg_clr(input[32-1:0] ins_i,output reg[32-1:0] ins_o,input clk,input clr);always@(posedge clk)if(clr)ins_o<=0;else ins_o<=ins_i;endmodule
module pc_reg_clr(input[32-1:0] pc_i,output reg[32-1:0] pc_o,input clk,input clr);always@(posedge clk)if(clr)pc_o<=0;else pc_o<=pc_i;endmodule
module spc_reg_clr(input[32-1:0] spc_i,output reg[32-1:0] spc_o,input clk,input clr);always@(posedge clk)if(clr)spc_o<=0;else spc_o<=spc_i;endmodule
module r1_reg_clr(input[1-1:0] r1_i,output reg[1-1:0] r1_o,input clk,input clr);always@(posedge clk)if(clr)r1_o<=0;else r1_o<=r1_i;endmodule
module r2_reg_clr(input[2-1:0] r2_i,output reg[2-1:0] r2_o,input clk,input clr);always@(posedge clk)if(clr)r2_o<=0;else r2_o<=r2_i;endmodule
module r3_reg_clr(input[3-1:0] r3_i,output reg[3-1:0] r3_o,input clk,input clr);always@(posedge clk)if(clr)r3_o<=0;else r3_o<=r3_i;endmodule
module r4_reg_clr(input[4-1:0] r4_i,output reg[4-1:0] r4_o,input clk,input clr);always@(posedge clk)if(clr)r4_o<=0;else r4_o<=r4_i;endmodule
module r5_reg_clr(input[5-1:0] r5_i,output reg[5-1:0] r5_o,input clk,input clr);always@(posedge clk)if(clr)r5_o<=0;else r5_o<=r5_i;endmodule
module r32_reg_clr(input[32-1:0] r32_i,output reg[32-1:0] r32_o,input clk,input clr);always@(posedge clk)if(clr)r32_o<=0;else r32_o<=r32_i;endmodule


module ext_ctl_reg(input[3-1:0] ext_ctl_i,output reg[3-1:0] ext_ctl_o,input clk);always@(posedge clk) ext_ctl_o<=ext_ctl_i;endmodule
module rd_sel_reg(input[2-1:0] rd_sel_i,output reg[2-1:0] rd_sel_o,input clk);always@(posedge clk) rd_sel_o<=rd_sel_i;endmodule
module cmp_ctl_reg(input[3-1:0] cmp_ctl_i,output reg[3-1:0] cmp_ctl_o,input clk);always@(posedge clk) cmp_ctl_o<=cmp_ctl_i;endmodule
module pc_gen_ctl_reg(input[3-1:0] pc_gen_ctl_i,output reg[3-1:0] pc_gen_ctl_o,input clk);always@(posedge clk) pc_gen_ctl_o<=pc_gen_ctl_i;endmodule
module fsm_ctl_reg(input[3-1:0] fsm_ctl_i,output reg[3-1:0] fsm_ctl_o,input clk);always@(posedge clk) fsm_ctl_o<=fsm_ctl_i;endmodule
module muxa_ctl_reg(input[2-1:0] muxa_ctl_i,output reg[2-1:0] muxa_ctl_o,input clk);always@(posedge clk) muxa_ctl_o<=muxa_ctl_i;endmodule
module muxb_ctl_reg(input[2-1:0] muxb_ctl_i,output reg[2-1:0] muxb_ctl_o,input clk);always@(posedge clk) muxb_ctl_o<=muxb_ctl_i;endmodule
module alu_func_reg(input[5-1:0] alu_func_i,output reg[5-1:0] alu_func_o,input clk);always@(posedge clk) alu_func_o<=alu_func_i;endmodule
module alu_we_reg(input[1-1:0] alu_we_i,output reg[1-1:0] alu_we_o,input clk);always@(posedge clk) alu_we_o<=alu_we_i;endmodule
module dmem_ctl_reg(input[4-1:0] dmem_ctl_i,output reg[4-1:0] dmem_ctl_o,input clk);always@(posedge clk) dmem_ctl_o<=dmem_ctl_i;endmodule
module wb_mux_ctl_reg(input[1-1:0] wb_mux_ctl_i,output reg[1-1:0] wb_mux_ctl_o,input clk);always@(posedge clk) wb_mux_ctl_o<=wb_mux_ctl_i;endmodule
module wb_we_reg(input[1-1:0] wb_we_i,output reg[1-1:0] wb_we_o,input clk);always@(posedge clk) wb_we_o<=wb_we_i;endmodule
module ins_reg(input[32-1:0] ins_i,output reg[32-1:0] ins_o,input clk);always@(posedge clk) ins_o<=ins_i;endmodule
module pc_reg(input[32-1:0] pc_i,output reg[32-1:0] pc_o,input clk);always@(posedge clk) pc_o<=pc_i;endmodule
module spc_reg(input[32-1:0] spc_i,output reg[32-1:0] spc_o,input clk);always@(posedge clk) spc_o<=spc_i;endmodule
module r1_reg(input[1-1:0] r1_i,output reg[1-1:0] r1_o,input clk);always@(posedge clk) r1_o<=r1_i;endmodule
module r2_reg(input[2-1:0] r2_i,output reg[2-1:0] r2_o,input clk);always@(posedge clk) r2_o<=r2_i;endmodule
module r3_reg(input[3-1:0] r3_i,output reg[3-1:0] r3_o,input clk);always@(posedge clk) r3_o<=r3_i;endmodule
module r4_reg(input[4-1:0] r4_i,output reg[4-1:0] r4_o,input clk);always@(posedge clk) r4_o<=r4_i;endmodule
module r5_reg(input[5-1:0] r5_i,output reg[5-1:0] r5_o,input clk);always@(posedge clk) r5_o<=r5_i;endmodule
module r32_reg(input[32-1:0] r32_i,output reg[32-1:0] r32_o,input clk);always@(posedge clk) r32_o<=r32_i;endmodule


module ext_ctl_reg_cls(input[3-1:0] ext_ctl_i,output reg[3-1:0] ext_ctl_o,input clk,input cls);always@(posedge clk)if(cls) ext_ctl_o<=ext_ctl_o;else ext_ctl_o<=ext_ctl_i;endmodule
module rd_sel_reg_cls(input[2-1:0] rd_sel_i,output reg[2-1:0] rd_sel_o,input clk,input cls);always@(posedge clk)if(cls) rd_sel_o<=rd_sel_o;else rd_sel_o<=rd_sel_i;endmodule
module cmp_ctl_reg_cls(input[3-1:0] cmp_ctl_i,output reg[3-1:0] cmp_ctl_o,input clk,input cls);always@(posedge clk)if(cls) cmp_ctl_o<=cmp_ctl_o;else cmp_ctl_o<=cmp_ctl_i;endmodule
module pc_gen_ctl_reg_cls(input[3-1:0] pc_gen_ctl_i,output reg[3-1:0] pc_gen_ctl_o,input clk,input cls);always@(posedge clk)if(cls) pc_gen_ctl_o<=pc_gen_ctl_o;else pc_gen_ctl_o<=pc_gen_ctl_i;endmodule
module fsm_ctl_reg_cls(input[3-1:0] fsm_ctl_i,output reg[3-1:0] fsm_ctl_o,input clk,input cls);always@(posedge clk)if(cls) fsm_ctl_o<=fsm_ctl_o;else fsm_ctl_o<=fsm_ctl_i;endmodule
module muxa_ctl_reg_cls(input[2-1:0] muxa_ctl_i,output reg[2-1:0] muxa_ctl_o,input clk,input cls);always@(posedge clk)if(cls) muxa_ctl_o<=muxa_ctl_o;else muxa_ctl_o<=muxa_ctl_i;endmodule
module muxb_ctl_reg_cls(input[2-1:0] muxb_ctl_i,output reg[2-1:0] muxb_ctl_o,input clk,input cls);always@(posedge clk)if(cls) muxb_ctl_o<=muxb_ctl_o;else muxb_ctl_o<=muxb_ctl_i;endmodule
module alu_func_reg_cls(input[5-1:0] alu_func_i,output reg[5-1:0] alu_func_o,input clk,input cls);always@(posedge clk)if(cls) alu_func_o<=alu_func_o;else alu_func_o<=alu_func_i;endmodule
module alu_we_reg_cls(input[1-1:0] alu_we_i,output reg[1-1:0] alu_we_o,input clk,input cls);always@(posedge clk)if(cls) alu_we_o<=alu_we_o;else alu_we_o<=alu_we_i;endmodule
module dmem_ctl_reg_cls(input[4-1:0] dmem_ctl_i,output reg[4-1:0] dmem_ctl_o,input clk,input cls);always@(posedge clk)if(cls) dmem_ctl_o<=dmem_ctl_o;else dmem_ctl_o<=dmem_ctl_i;endmodule
module wb_mux_ctl_reg_cls(input[1-1:0] wb_mux_ctl_i,output reg[1-1:0] wb_mux_ctl_o,input clk,input cls);always@(posedge clk)if(cls) wb_mux_ctl_o<=wb_mux_ctl_o;else wb_mux_ctl_o<=wb_mux_ctl_i;endmodule
module wb_we_reg_cls(input[1-1:0] wb_we_i,output reg[1-1:0] wb_we_o,input clk,input cls);always@(posedge clk)if(cls) wb_we_o<=wb_we_o;else wb_we_o<=wb_we_i;endmodule
module ins_reg_cls(input[32-1:0] ins_i,output reg[32-1:0] ins_o,input clk,input cls);always@(posedge clk)if(cls) ins_o<=ins_o;else ins_o<=ins_i;endmodule
module pc_reg_cls(input[32-1:0] pc_i,output reg[32-1:0] pc_o,input clk,input cls);always@(posedge clk)if(cls) pc_o<=pc_o;else pc_o<=pc_i;endmodule
module spc_reg_cls(input[32-1:0] spc_i,output reg[32-1:0] spc_o,input clk,input cls);always@(posedge clk)if(cls) spc_o<=spc_o;else spc_o<=spc_i;endmodule
module r1_reg_cls(input[1-1:0] r1_i,output reg[1-1:0] r1_o,input clk,input cls);always@(posedge clk)if(cls) r1_o<=r1_o;else r1_o<=r1_i;endmodule
module r2_reg_cls(input[2-1:0] r2_i,output reg[2-1:0] r2_o,input clk,input cls);always@(posedge clk)if(cls) r2_o<=r2_o;else r2_o<=r2_i;endmodule
module r3_reg_cls(input[3-1:0] r3_i,output reg[3-1:0] r3_o,input clk,input cls);always@(posedge clk)if(cls) r3_o<=r3_o;else r3_o<=r3_i;endmodule
module r4_reg_cls(input[4-1:0] r4_i,output reg[4-1:0] r4_o,input clk,input cls);always@(posedge clk)if(cls) r4_o<=r4_o;else r4_o<=r4_i;endmodule
module r5_reg_cls(input[5-1:0] r5_i,output reg[5-1:0] r5_o,input clk,input cls);always@(posedge clk)if(cls) r5_o<=r5_o;else r5_o<=r5_i;endmodule
module r32_reg_cls(input[32-1:0] r32_i,output reg[32-1:0] r32_o,input clk,input cls);always@(posedge clk)if(cls) r32_o<=r32_o;else r32_o<=r32_i;endmodule


	 
module portio16(
        inout [15:0] io_port,
        output [15:0] dfport,
        input [15:0] d2port,
        input wr_en
    );

    assign dfport = io_port ;
    assign io_port = wr_en ? d2port : 16'bz;

endmodule
