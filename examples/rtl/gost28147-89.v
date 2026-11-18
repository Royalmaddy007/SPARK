module gost89_cfb_decrypt(
  input              clk,
  input              reset,
  input              load_data,
  input      [511:0] sbox,
  input      [255:0] key,
  input      [63:0]  in,
  output reg [63:0]  out,
  output reg         busy
);
  reg  [63:0] gamma;
  reg  [63:0] in_value;
  wire [63:0] out_ecb;
  wire        load_ecb, busy_ecb;

  assign load_ecb = !reset && load_data;
  assign reset_ecb = load_ecb;

  gost89_ecb_encrypt
    ecb_encrypt(clk, reset_ecb, load_ecb, sbox, key, gamma, out_ecb, busy_ecb);

  always @(posedge clk) begin
    if (reset && !load_data) begin
      gamma <= in;
      busy <= 0;
    end

    if (!reset & load_data) begin
      in_value <= in;
      busy <= 1;
    end

    if (!reset && !load_data && !busy_ecb && busy) begin
      gamma <= in_value;
      out   <= out_ecb ^ in_value;
      busy  <= 0;
    end
  end
endmodule
module gost89_cfb(
  input              clk,
  input              reset,
  input              mode,
  input              load_data,
  input      [511:0] sbox,
  input      [255:0] key,
  input      [63:0]  in,
  output reg [63:0]  out,
  output reg         busy
);
  reg  [63:0] gamma;
  reg  [63:0] in_value;
  wire [63:0] out_ecb;
  wire        reset_ecb, load_ecb, busy_ecb;

  assign load_ecb = !reset && load_data;
  assign reset_ecb = load_ecb;

  gost89_ecb_encrypt
    ecb_encrypt(clk, reset_ecb, load_ecb, sbox, key, gamma, out_ecb, busy_ecb);

  always @(posedge clk) begin
    if (reset && !load_data) begin
      gamma <= in;
      busy <= 0;
    end

    if (!reset & load_data) begin
      in_value <= in;
      busy <= 1;
    end

    if (!reset && !load_data && !busy_ecb && busy) begin
      if (mode) gamma <= in_value;
      else      gamma <= out_ecb ^ in_value;
      out   <= out_ecb ^ in_value;
      busy  <= 0;
    end
  end
endmodule

module gost89_cfb_encrypt(
  input              clk,
  input              reset,
  input              load_data,
  input      [511:0] sbox,
  input      [255:0] key,
  input      [63:0]  in,
  output reg [63:0]  out,
  output reg         busy
);
  reg  [63:0] gamma;
  reg  [63:0] in_value;
  wire [63:0] out_ecb;
  wire        load_ecb, busy_ecb;

  assign load_ecb = !reset && load_data;
  assign reset_ecb = load_ecb;

  gost89_ecb_encrypt
    ecb_encrypt(clk, reset_ecb, load_ecb, sbox, key, gamma, out_ecb, busy_ecb);

  always @(posedge clk) begin
    if (reset && !load_data) begin
      gamma <= in;
      busy <= 0;
    end

    if (!reset & load_data) begin
      in_value <= in;
      busy <= 1;
    end

    if (!reset && !load_data && !busy_ecb && busy) begin
      gamma <= out_ecb ^ in_value;
      out   <= out_ecb ^ in_value;
      busy  <= 0;
    end
  end
endmodule


module gost89_ecb(
  input              clk,
  input              reset,
  input              mode,
  input              load_data,
  input      [511:0] sbox,
  input      [255:0] key,
  input      [63:0]  in,
  output reg [63:0]  out,
  output reg         busy
);
  reg  [5:0]  round_num;
  reg  [31:0] n1, n2, round_key;
  wire [31:0] out1, out2;

  gost89_round
    rnd(clk, sbox, round_key, n1, n2, out1, out2);

  always @(posedge clk) begin
    if (load_data) begin
      n1 <= in[63:32];
      n2 <= in[31:0];
      busy <= 1;
      round_num <= 0;
    end

    if (reset && !load_data) begin
      busy <= 0;
      round_num <= 32;
    end

    if (!reset && !load_data) begin
      if (round_num < 32)
        round_num <= round_num + 1;
      if (round_num > 0 && round_num < 32) begin
        n1 <= out1;
        n2 <= out2;
      end
      if (round_num == 32) begin
        out[63:32] <= out2;
        out[31:0]  <= out1;
        busy <= 0;
      end
    end
  end

  always @(posedge clk) begin
    if (mode)
      case (round_num)
        0:  round_key <= key[255:224];
        1:  round_key <= key[223:192];
        2:  round_key <= key[191:160];
        3:  round_key <= key[159:128];
        4:  round_key <= key[127:96];
        5:  round_key <= key[95:64];
        6:  round_key <= key[63:32];
        7:  round_key <= key[31:0];
        8:  round_key <= key[31:0];
        9:  round_key <= key[63:32];
        10: round_key <= key[95:64];
        11: round_key <= key[127:96];
        12: round_key <= key[159:128];
        13: round_key <= key[191:160];
        14: round_key <= key[223:192];
        15: round_key <= key[255:224];
        16: round_key <= key[31:0];
        17: round_key <= key[63:32];
        18: round_key <= key[95:64];
        19: round_key <= key[127:96];
        20: round_key <= key[159:128];
        21: round_key <= key[191:160];
        22: round_key <= key[223:192];
        23: round_key <= key[255:224];
        24: round_key <= key[31:0];
        25: round_key <= key[63:32];
        26: round_key <= key[95:64];
        27: round_key <= key[127:96];
        28: round_key <= key[159:128];
        29: round_key <= key[191:160];
        30: round_key <= key[223:192];
        31: round_key <= key[255:224];
      endcase
    else
      case (round_num)
        0:  round_key <= key[255:224];
        1:  round_key <= key[223:192];
        2:  round_key <= key[191:160];
        3:  round_key <= key[159:128];
        4:  round_key <= key[127:96];
        5:  round_key <= key[95:64];
        6:  round_key <= key[63:32];
        7:  round_key <= key[31:0];
        8:  round_key <= key[255:224];
        9:  round_key <= key[223:192];
        10: round_key <= key[191:160];
        11: round_key <= key[159:128];
        12: round_key <= key[127:96];
        13: round_key <= key[95:64];
        14: round_key <= key[63:32];
        15: round_key <= key[31:0];
        16: round_key <= key[255:224];
        17: round_key <= key[223:192];
        18: round_key <= key[191:160];
        19: round_key <= key[159:128];
        20: round_key <= key[127:96];
        21: round_key <= key[95:64];
        22: round_key <= key[63:32];
        23: round_key <= key[31:0];
        24: round_key <= key[31:0];
        25: round_key <= key[63:32];
        26: round_key <= key[95:64];
        27: round_key <= key[127:96];
        28: round_key <= key[159:128];
        29: round_key <= key[191:160];
        30: round_key <= key[223:192];
        31: round_key <= key[255:224];
      endcase
  end
endmodule

module gost89_ecb_encrypt(
  input              clk,
  input              reset,
  input              load_data,
  input      [511:0] sbox,
  input      [255:0] key,
  input      [63:0]  in,
  output reg [63:0]  out,
  output reg         busy
);
  reg  [5:0]  round_num;
  reg  [31:0] n1, n2, round_key;
  wire [31:0] out1, out2;

  gost89_round
    rnd(clk, sbox, round_key, n1, n2, out1, out2);

  always @(posedge clk) begin
    if (load_data) begin
      n1 <= in[63:32];
      n2 <= in[31:0];
      busy <= 1;
      round_num <= 0;
    end

    if (reset && !load_data) begin
      busy <= 0;
      round_num <= 32;
    end

    if (!reset && !load_data) begin
      if (round_num < 32)
        round_num <= round_num + 1;
      if (round_num > 0 && round_num < 32) begin
        n1 <= out1;
        n2 <= out2;
      end
      if (round_num == 32) begin
        out[63:32] <= out2;
        out[31:0]  <= out1;
        busy <= 0;
      end
    end
  end

  always @(posedge clk)
    case (round_num)
      0:  round_key <= key[255:224];
      1:  round_key <= key[223:192];
      2:  round_key <= key[191:160];
      3:  round_key <= key[159:128];
      4:  round_key <= key[127:96];
      5:  round_key <= key[95:64];
      6:  round_key <= key[63:32];
      7:  round_key <= key[31:0];
      8:  round_key <= key[255:224];
      9:  round_key <= key[223:192];
      10: round_key <= key[191:160];
      11: round_key <= key[159:128];
      12: round_key <= key[127:96];
      13: round_key <= key[95:64];
      14: round_key <= key[63:32];
      15: round_key <= key[31:0];
      16: round_key <= key[255:224];
      17: round_key <= key[223:192];
      18: round_key <= key[191:160];
      19: round_key <= key[159:128];
      20: round_key <= key[127:96];
      21: round_key <= key[95:64];
      22: round_key <= key[63:32];
      23: round_key <= key[31:0];
      24: round_key <= key[31:0];
      25: round_key <= key[63:32];
      26: round_key <= key[95:64];
      27: round_key <= key[127:96];
      28: round_key <= key[159:128];
      29: round_key <= key[191:160];
      30: round_key <= key[223:192];
      31: round_key <= key[255:224];
    endcase
endmodule

module gost89_ecb_decrypt(
  input              clk,
  input              reset,
  input              load_data,
  input      [511:0] sbox,
  input      [255:0] key,
  input      [63:0]  in,
  output reg [63:0]  out,
  output reg         busy
);
  reg  [5:0]  round_num;
  reg  [31:0] n1, n2, round_key;
  wire [31:0] out1, out2;

  gost89_round
    rnd(clk, sbox, round_key, n1, n2, out1, out2);

  initial begin
    busy = 0;
    round_num = 32;
  end

  always @(posedge clk) begin
    if (load_data) begin
      n1 <= in[63:32];
      n2 <= in[31:0];
      busy <= 1;
      round_num <= 0;
    end

    if (reset && !load_data) begin
      busy <= 0;
      round_num <= 32;
    end

    if (!reset && !load_data) begin
      if (round_num < 32)
        round_num <= round_num + 1;
      if (round_num > 0 && round_num < 32) begin
        n1 <= out1;
        n2 <= out2;
      end
      if (round_num == 32) begin
        out[63:32] = out2;
        out[31:0]  = out1;
        busy <= 0;
      end
    end
  end

  always @(posedge clk)
    case (round_num)
      0:  round_key <= key[255:224];
      1:  round_key <= key[223:192];
      2:  round_key <= key[191:160];
      3:  round_key <= key[159:128];
      4:  round_key <= key[127:96];
      5:  round_key <= key[95:64];
      6:  round_key <= key[63:32];
      7:  round_key <= key[31:0];
      8:  round_key <= key[31:0];
      9:  round_key <= key[63:32];
      10: round_key <= key[95:64];
      11: round_key <= key[127:96];
      12: round_key <= key[159:128];
      13: round_key <= key[191:160];
      14: round_key <= key[223:192];
      15: round_key <= key[255:224];
      16: round_key <= key[31:0];
      17: round_key <= key[63:32];
      18: round_key <= key[95:64];
      19: round_key <= key[127:96];
      20: round_key <= key[159:128];
      21: round_key <= key[191:160];
      22: round_key <= key[223:192];
      23: round_key <= key[255:224];
      24: round_key <= key[31:0];
      25: round_key <= key[63:32];
      26: round_key <= key[95:64];
      27: round_key <= key[127:96];
      28: round_key <= key[159:128];
      29: round_key <= key[191:160];
      30: round_key <= key[223:192];
      31: round_key <= key[255:224];
    endcase
endmodule
module gost89_mac(
  input              clk,
  input              reset,
  input              load_data,
  input      [511:0] sbox,
  input      [255:0] key,
  input      [63:0]  in,
  output reg [31:0]  out,
  output reg         busy
);
  reg  [4:0]  counter;
  reg  [31:0] round_key;
  reg         need_xor;
  reg  [31:0] n1, n2;
  wire [31:0] out1, out2;

  gost89_round
    rnd(clk, sbox, round_key, n1, n2, out1, out2);

  always @(posedge clk) begin
    if (reset && !load_data) begin
      counter  <= 17;
      need_xor <= 0;
      busy <= 0;
    end

    if (!reset && load_data) begin
      if (need_xor) begin
        n1 <= in[63:32] ^ n2;
        n2 <= in[31:0]  ^ n1;
      end else begin
        n1 <= in[63:32];
        n2 <= in[31:0];
        need_xor <= 1;
      end
      counter <= 0;
      busy <= 1;
    end

    if (reset && load_data) begin
      n1 <= in[63:32];
      n2 <= in[31:0];
      counter  <= 0;
      need_xor <= 1;
      busy <= 1;
    end

    if (!reset && !load_data) begin
      if (counter < 17)
        counter <= counter + 1;
      if (counter > 0 && counter < 17) begin
        n1 <= out1;
        n2 <= out2;
      end
      if (counter == 16) begin
        busy <= 0;
        out  <= out2;
      end
    end
  end

  always @(posedge clk)
    case (counter)
      0:  round_key <= key[255:224];
      1:  round_key <= key[223:192];
      2:  round_key <= key[191:160];
      3:  round_key <= key[159:128];
      4:  round_key <= key[127:96];
      5:  round_key <= key[95:64];
      6:  round_key <= key[63:32];
      7:  round_key <= key[31:0];
      8:  round_key <= key[255:224];
      9:  round_key <= key[223:192];
      10: round_key <= key[191:160];
      11: round_key <= key[159:128];
      12: round_key <= key[127:96];
      13: round_key <= key[95:64];
      14: round_key <= key[63:32];
      15: round_key <= key[31:0];
    endcase
endmodule
module gost89_pipelined_ecb_encrypt(
  input          clk,
  input  [511:0] sbox,
  input  [255:0] key,
  input  [63:0]  in,
  output [63:0]  out
);
  reg  [31:0] n1[31:0], n2[31:0];
  wire [31:0] out1[31:0], out2[31:0];

  always @(posedge clk) begin
    n1[0]  <= in[63:32]; n2[0]  <= in[31:0];
    n1[1]  <= out1[0];   n2[1]  <= out2[0];
    n1[2]  <= out1[1];   n2[2]  <= out2[1];
    n1[3]  <= out1[2];   n2[3]  <= out2[2];
    n1[4]  <= out1[3];   n2[4]  <= out2[3];
    n1[5]  <= out1[4];   n2[5]  <= out2[4];
    n1[6]  <= out1[5];   n2[6]  <= out2[5];
    n1[7]  <= out1[6];   n2[7]  <= out2[6];
    n1[8]  <= out1[7];   n2[8]  <= out2[7];
    n1[9]  <= out1[8];   n2[9]  <= out2[8];
    n1[10] <= out1[9];   n2[10] <= out2[9];
    n1[11] <= out1[10];  n2[11] <= out2[10];
    n1[12] <= out1[11];  n2[12] <= out2[11];
    n1[13] <= out1[12];  n2[13] <= out2[12];
    n1[14] <= out1[13];  n2[14] <= out2[13];
    n1[15] <= out1[14];  n2[15] <= out2[14];
    n1[16] <= out1[15];  n2[16] <= out2[15];
    n1[17] <= out1[16];  n2[17] <= out2[16];
    n1[18] <= out1[17];  n2[18] <= out2[17];
    n1[19] <= out1[18];  n2[19] <= out2[18];
    n1[20] <= out1[19];  n2[20] <= out2[19];
    n1[21] <= out1[20];  n2[21] <= out2[20];
    n1[22] <= out1[21];  n2[22] <= out2[21];
    n1[23] <= out1[22];  n2[23] <= out2[22];
    n1[24] <= out1[23];  n2[24] <= out2[23];
    n1[25] <= out1[24];  n2[25] <= out2[24];
    n1[26] <= out1[25];  n2[26] <= out2[25];
    n1[27] <= out1[26];  n2[27] <= out2[26];
    n1[28] <= out1[27];  n2[28] <= out2[27];
    n1[29] <= out1[28];  n2[29] <= out2[28];
    n1[30] <= out1[29];  n2[30] <= out2[29];
    n1[31] <= out1[30];  n2[31] <= out2[30];
  end

  gost89_round
    r1 (clk, sbox, key[255:224], n1[0],  n2[0],  out1[0],  out2[0]),
    r2 (clk, sbox, key[223:192], n1[1],  n2[1],  out1[1],  out2[1]),
    r3 (clk, sbox, key[191:160], n1[2],  n2[2],  out1[2],  out2[2]),
    r4 (clk, sbox, key[159:128], n1[3],  n2[3],  out1[3],  out2[3]),
    r5 (clk, sbox, key[127:96],  n1[4],  n2[4],  out1[4],  out2[4]),
    r6 (clk, sbox, key[95:64],   n1[5],  n2[5],  out1[5],  out2[5]),
    r7 (clk, sbox, key[63:32],   n1[6],  n2[6],  out1[6],  out2[6]),
    r8 (clk, sbox, key[31:0],    n1[7],  n2[7],  out1[7],  out2[7]),
    r9 (clk, sbox, key[255:224], n1[8],  n2[8],  out1[8],  out2[8]),
    r10(clk, sbox, key[223:192], n1[9],  n2[9],  out1[9],  out2[9]),
    r11(clk, sbox, key[191:160], n1[10], n2[10], out1[10], out2[10]),
    r12(clk, sbox, key[159:128], n1[11], n2[11], out1[11], out2[11]),
    r13(clk, sbox, key[127:96],  n1[12], n2[12], out1[12], out2[12]),
    r14(clk, sbox, key[95:64],   n1[13], n2[13], out1[13], out2[13]),
    r15(clk, sbox, key[63:32],   n1[14], n2[14], out1[14], out2[14]),
    r16(clk, sbox, key[31:0],    n1[15], n2[15], out1[15], out2[15]),
    r17(clk, sbox, key[255:224], n1[16], n2[16], out1[16], out2[16]),
    r18(clk, sbox, key[223:192], n1[17], n2[17], out1[17], out2[17]),
    r19(clk, sbox, key[191:160], n1[18], n2[18], out1[18], out2[18]),
    r20(clk, sbox, key[159:128], n1[19], n2[19], out1[19], out2[19]),
    r21(clk, sbox, key[127:96],  n1[20], n2[20], out1[20], out2[20]),
    r22(clk, sbox, key[95:64],   n1[21], n2[21], out1[21], out2[21]),
    r23(clk, sbox, key[63:32],   n1[22], n2[22], out1[22], out2[22]),
    r24(clk, sbox, key[31:0],    n1[23], n2[23], out1[23], out2[23]),
    r25(clk, sbox, key[31:0],    n1[24], n2[24], out1[24], out2[24]),
    r26(clk, sbox, key[63:32],   n1[25], n2[25], out1[25], out2[25]),
    r27(clk, sbox, key[95:64],   n1[26], n2[26], out1[26], out2[26]),
    r28(clk, sbox, key[127:96],  n1[27], n2[27], out1[27], out2[27]),
    r29(clk, sbox, key[159:128], n1[28], n2[28], out1[28], out2[28]),
    r30(clk, sbox, key[191:160], n1[29], n2[29], out1[29], out2[29]),
    r31(clk, sbox, key[223:192], n1[30], n2[30], out1[30], out2[30]),
    r32(clk, sbox, key[255:224], n1[31], n2[31], out1[31], out2[31]);

  assign out[31:0]  = out1[31];
  assign out[63:32] = out2[31];
endmodule

module gost89_pipelined_ecb_decrypt(
  input          clk,
  input  [511:0] sbox,
  input  [255:0] key,
  input  [63:0]  in,
  output [63:0]  out
);
  reg  [31:0] n1[31:0], n2[31:0];
  wire [31:0] out1[31:0], out2[31:0];

  always @(posedge clk) begin
    n1[0]  <= in[63:32]; n2[0]  <= in[31:0];
    n1[1]  <= out1[0];   n2[1]  <= out2[0];
    n1[2]  <= out1[1];   n2[2]  <= out2[1];
    n1[3]  <= out1[2];   n2[3]  <= out2[2];
    n1[4]  <= out1[3];   n2[4]  <= out2[3];
    n1[5]  <= out1[4];   n2[5]  <= out2[4];
    n1[6]  <= out1[5];   n2[6]  <= out2[5];
    n1[7]  <= out1[6];   n2[7]  <= out2[6];
    n1[8]  <= out1[7];   n2[8]  <= out2[7];
    n1[9]  <= out1[8];   n2[9]  <= out2[8];
    n1[10] <= out1[9];   n2[10] <= out2[9];
    n1[11] <= out1[10];  n2[11] <= out2[10];
    n1[12] <= out1[11];  n2[12] <= out2[11];
    n1[13] <= out1[12];  n2[13] <= out2[12];
    n1[14] <= out1[13];  n2[14] <= out2[13];
    n1[15] <= out1[14];  n2[15] <= out2[14];
    n1[16] <= out1[15];  n2[16] <= out2[15];
    n1[17] <= out1[16];  n2[17] <= out2[16];
    n1[18] <= out1[17];  n2[18] <= out2[17];
    n1[19] <= out1[18];  n2[19] <= out2[18];
    n1[20] <= out1[19];  n2[20] <= out2[19];
    n1[21] <= out1[20];  n2[21] <= out2[20];
    n1[22] <= out1[21];  n2[22] <= out2[21];
    n1[23] <= out1[22];  n2[23] <= out2[22];
    n1[24] <= out1[23];  n2[24] <= out2[23];
    n1[25] <= out1[24];  n2[25] <= out2[24];
    n1[26] <= out1[25];  n2[26] <= out2[25];
    n1[27] <= out1[26];  n2[27] <= out2[26];
    n1[28] <= out1[27];  n2[28] <= out2[27];
    n1[29] <= out1[28];  n2[29] <= out2[28];
    n1[30] <= out1[29];  n2[30] <= out2[29];
    n1[31] <= out1[30];  n2[31] <= out2[30];
  end

  gost89_round
    r1 (clk, sbox, key[255:224], n1[0],  n2[0],  out1[0],  out2[0]),
    r2 (clk, sbox, key[223:192], n1[1],  n2[1],  out1[1],  out2[1]),
    r3 (clk, sbox, key[191:160], n1[2],  n2[2],  out1[2],  out2[2]),
    r4 (clk, sbox, key[159:128], n1[3],  n2[3],  out1[3],  out2[3]),
    r5 (clk, sbox, key[127:96],  n1[4],  n2[4],  out1[4],  out2[4]),
    r6 (clk, sbox, key[95:64],   n1[5],  n2[5],  out1[5],  out2[5]),
    r7 (clk, sbox, key[63:32],   n1[6],  n2[6],  out1[6],  out2[6]),
    r8 (clk, sbox, key[31:0],    n1[7],  n2[7],  out1[7],  out2[7]),
    r9 (clk, sbox, key[31:0],    n1[8],  n2[8],  out1[8],  out2[8]),
    r10(clk, sbox, key[63:32],   n1[9],  n2[9],  out1[9],  out2[9]),
    r11(clk, sbox, key[95:64],   n1[10], n2[10], out1[10], out2[10]),
    r12(clk, sbox, key[127:96],  n1[11], n2[11], out1[11], out2[11]),
    r13(clk, sbox, key[159:128], n1[12], n2[12], out1[12], out2[12]),
    r14(clk, sbox, key[191:160], n1[13], n2[13], out1[13], out2[13]),
    r15(clk, sbox, key[223:192], n1[14], n2[14], out1[14], out2[14]),
    r16(clk, sbox, key[255:224], n1[15], n2[15], out1[15], out2[15]),
    r17(clk, sbox, key[31:0],    n1[16], n2[16], out1[16], out2[16]),
    r18(clk, sbox, key[63:32],   n1[17], n2[17], out1[17], out2[17]),
    r19(clk, sbox, key[95:64],   n1[18], n2[18], out1[18], out2[18]),
    r20(clk, sbox, key[127:96],  n1[19], n2[19], out1[19], out2[19]),
    r21(clk, sbox, key[159:128], n1[20], n2[20], out1[20], out2[20]),
    r22(clk, sbox, key[191:160], n1[21], n2[21], out1[21], out2[21]),
    r23(clk, sbox, key[223:192], n1[22], n2[22], out1[22], out2[22]),
    r24(clk, sbox, key[255:224], n1[23], n2[23], out1[23], out2[23]),
    r25(clk, sbox, key[31:0],    n1[24], n2[24], out1[24], out2[24]),
    r26(clk, sbox, key[63:32],   n1[25], n2[25], out1[25], out2[25]),
    r27(clk, sbox, key[95:64],   n1[26], n2[26], out1[26], out2[26]),
    r28(clk, sbox, key[127:96],  n1[27], n2[27], out1[27], out2[27]),
    r29(clk, sbox, key[159:128], n1[28], n2[28], out1[28], out2[28]),
    r30(clk, sbox, key[191:160], n1[29], n2[29], out1[29], out2[29]),
    r31(clk, sbox, key[223:192], n1[30], n2[30], out1[30], out2[30]),
    r32(clk, sbox, key[255:224], n1[31], n2[31], out1[31], out2[31]);

  assign out[31:0]  = out1[31];
  assign out[63:32] = out2[31];
endmodule
module gost89_round(
  input          clk,
  input  [511:0] sbox,
  input  [31:0]  key,
  input  [31:0]  n1,
  input  [31:0]  n2,
  output [31:0]  out1,
  output [31:0]  out2
);
  wire [31:0] tmp1, tmp2;

  assign tmp1 = n1 + key;

  gost89_sbox
    sbox1(sbox[511:448], tmp1[3:0],   tmp2[3:0]),
    sbox2(sbox[447:384], tmp1[7:4],   tmp2[7:4]),
    sbox3(sbox[383:320], tmp1[11:8],  tmp2[11:8]),
    sbox4(sbox[319:256], tmp1[15:12], tmp2[15:12]),
    sbox5(sbox[255:192], tmp1[19:16], tmp2[19:16]),
    sbox6(sbox[191:128], tmp1[23:20], tmp2[23:20]),
    sbox7(sbox[127:64],  tmp1[27:24], tmp2[27:24]),
    sbox8(sbox[63 :0],   tmp1[31:28], tmp2[31:28]);

  assign out1[10:0]  = tmp2[31:21] ^ n2[10:0];
  assign out1[31:11] = tmp2[20:0]  ^ n2[31:11];

  assign out2 = n1;
endmodule
module gost89_sbox(
  input      [63:0] sbox,
  input      [3:0]  in,
  output reg [3:0]  out
);
  always @(in or sbox)
    case (in)
      4'h0: out <= sbox[63:60];
      4'h1: out <= sbox[59:56];
      4'h2: out <= sbox[55:52];
      4'h3: out <= sbox[51:48];
      4'h4: out <= sbox[47:44];
      4'h5: out <= sbox[43:40];
      4'h6: out <= sbox[39:36];
      4'h7: out <= sbox[35:32];
      4'h8: out <= sbox[31:28];
      4'h9: out <= sbox[27:24];
      4'ha: out <= sbox[23:20];
      4'hb: out <= sbox[19:16];
      4'hc: out <= sbox[15:12];
      4'hd: out <= sbox[11:8];
      4'he: out <= sbox[7:4];
      4'hf: out <= sbox[3:0];
    endcase
endmodule
