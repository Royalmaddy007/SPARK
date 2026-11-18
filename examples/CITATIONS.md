# Verilog Example Corpus — Provenance and Citations

Verilog example corpus for the GREAT/DAC-26 GenAI RTL redaction pipeline. All files are unmodified upstream sources, redistributed under their original licences (see examples/licenses/).

Retrieved on **2026-09-09** by shallow `git clone` of each upstream repository. Files are byte-identical to upstream; the pipeline never modifies them in place.

## `aes_sbox.v`

| | |
|---|---|
| Upstream | [secworks/aes](https://github.com/secworks/aes) |
| Path | `src/rtl/aes_sbox.v` |
| Commit | `80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc` |
| Permalink | https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_sbox.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-aes.LICENSE) |
| Copyright | Joachim Strömbergson |

AES S-box as a 256-entry combinational LUT. The S-box table itself is the crown jewel: it is a published constant, but its literal presence instantly identifies the design as AES.

Security-relevant features: `crypto S-box constants`, `combinational LUT`

## `aes_key_mem.v`

| | |
|---|---|
| Upstream | [secworks/aes](https://github.com/secworks/aes) |
| Path | `src/rtl/aes_key_mem.v` |
| Commit | `80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc` |
| Permalink | https://github.com/secworks/aes/blob/80dc4718e1dcbbdb4b0dd1bdb393d8f7b98981dc/src/rtl/aes_key_mem.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-aes.LICENSE) |
| Copyright | Joachim Strömbergson |

AES-128/256 key expansion memory with a round-key FSM and rcon generation. Holds the live key material and a named FSM (CTRL_IDLE/CTRL_INIT/CTRL_GENERATE/CTRL_DONE).

Security-relevant features: `key storage`, `FSM localparams`, `rcon constants`, `key compare`

## `sha256_k_constants.v`

| | |
|---|---|
| Upstream | [secworks/sha256](https://github.com/secworks/sha256) |
| Path | `src/rtl/sha256_k_constants.v` |
| Commit | `837c5cc396f001d18f2c765721c585716eb439ae` |
| Permalink | https://github.com/secworks/sha256/blob/837c5cc396f001d18f2c765721c585716eb439ae/src/rtl/sha256_k_constants.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-sha256.LICENSE) |
| Copyright | Joachim Strömbergson |

SHA-256 round-constant ROM: 64 x 32-bit K constants selected by round index. A pure algebraic-constant-masking target (Step 4c).

Security-relevant features: `algorithm-identifying constants`, `case-based ROM`

## `siphash_core.v`

| | |
|---|---|
| Upstream | [secworks/siphash](https://github.com/secworks/siphash) |
| Path | `src/rtl/siphash_core.v` |
| Commit | `25f5482f4ecbf1ab60a7b5e5dd7e2d7f56b0aa6c` |
| Permalink | https://github.com/secworks/siphash/blob/25f5482f4ecbf1ab60a7b5e5dd7e2d7f56b0aa6c/src/rtl/siphash_core.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-siphash.LICENSE) |
| Copyright | Secworks Sweden AB |

SipHash-2-4 keyed-hash core: 128-bit key register, ARX rounds, initialisation constants and a multi-state control FSM.

Security-relevant features: `128-bit key register`, `magic init constants`, `FSM`, `ARX adders`

## `chacha_qr.v`

| | |
|---|---|
| Upstream | [secworks/chacha](https://github.com/secworks/chacha) |
| Path | `src/rtl/chacha_qr.v` |
| Commit | `7eaba360df9fed9fc2db98d5f3df81cf01e5b604` |
| Permalink | https://github.com/secworks/chacha/blob/7eaba360df9fed9fc2db98d5f3df81cf01e5b604/src/rtl/chacha_qr.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-chacha.LICENSE) |
| Copyright | Joachim Strömbergson |

ChaCha quarter-round: four 32-bit modular adders, XORs and rotations. Chosen as the arithmetic structural-decomposition target (Step 4h).

Security-relevant features: `32-bit adders`, `rotation constants`

## `keywrap_core.v`

| | |
|---|---|
| Upstream | [assured/keywrap](https://github.com/secworks/keywrap) |
| Path | `src/rtl/keywrap_core.v` |
| Commit | `547e2a181abf3e5fc7624a1e56a47f4239bbf4b3` |
| Permalink | https://github.com/secworks/keywrap/blob/547e2a181abf3e5fc7624a1e56a47f4239bbf4b3/src/rtl/keywrap_core.v |
| Licence | BSD-2-Clause (examples/licenses/assured-keywrap.LICENSE) |
| Copyright | Assured AB / Joachim Strömbergson |

RFC-3394 AES key-wrap core: contains the A0 integrity-check constant 64'hA6A6A6A6A6A6A6A6 and the unwrap validity comparison — a textbook comparison-chain-obfuscation target (Step 4d).

Security-relevant features: `integrity check constant`, `equality comparison`, `unwrap validity flag`

> **Known issue (deliberately retained).** This upstream file is a work in progress and
> references several signals it never declares (`tmp_read_data`, `tmp_error`, `key0_reg`),
> so it does not elaborate standalone even with every sibling module supplied. It is kept
> in the corpus because it exercises the pipeline's advisory-mode path: Phase 4 logs
> `annotated_input_does_not_compile`, downgrades the per-step syntax gate to advisory, and
> still produces a transformed deliverable; Phase 5 then reports the FAIL honestly.

## `trng_debug_ctrl.v`

| | |
|---|---|
| Upstream | [secworks/trng](https://github.com/secworks/trng) |
| Path | `src/rtl/trng_debug_ctrl.v` |
| Commit | `3dd45d9c862a499201d9b734629641da685dbe43` |
| Permalink | https://github.com/secworks/trng/blob/3dd45d9c862a499201d9b734629641da685dbe43/src/rtl/trng_debug_ctrl.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-trng.LICENSE) |
| Copyright | Joachim Strömbergson |

TRNG debug/observability access-control block. Gates raw entropy onto a debug port under an enable — a privilege/access-control cone (MED/HIGH boundary logic).

Security-relevant features: `debug access gating`, `privilege logic`

## `tiny_aes_128.v`

| | |
|---|---|
| Upstream | [freecores/tiny_aes](https://github.com/freecores/tiny_aes) |
| Path | `rtl/aes_128.v` |
| Commit | `faf2afb2bcb6c3247c00d6bd7129b31b4fff91fb` |
| Permalink | https://github.com/freecores/tiny_aes/blob/faf2afb2bcb6c3247c00d6bd7129b31b4fff91fb/rtl/aes_128.v |
| Licence | Apache-2.0 (examples/licenses/freecores-tiny_aes.LICENSE) |
| Copyright | Homer Hsing |

Compact 10-round AES-128 encryption pipeline with inline round-key expansion. Second, independent AES implementation used to check that the pipeline is not over-fitted to one coding style.

Security-relevant features: `AES round pipeline`, `inline key expansion`, `rcon constants`

## `sha1_core.v`

| | |
|---|---|
| Upstream | [secworks/sha1](https://github.com/secworks/sha1) |
| Path | `src/rtl/sha1_core.v` |
| Commit | `50f82f4ca2f8194fd47d8360270ac7dd141d53d1` |
| Permalink | https://github.com/secworks/sha1/blob/50f82f4ca2f8194fd47d8360270ac7dd141d53d1/src/rtl/sha1_core.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-sha1.LICENSE) |
| Copyright | Joachim Strömbergson / Secworks Sweden AB |

SHA-1 compression-function core: a named round FSM (CTRL_IDLE/CTRL_ROUNDS/CTRL_DONE), a 512-bit message schedule (sha1_w_mem), the five 32-bit initial-hash constants H0..H4 and the four round constants K. The initial-hash and round constants are the crown jewels — they identify the design as SHA-1 outright.

Security-relevant features: `algorithm-identifying constants`, `round FSM`, `message schedule`, `hash datapath`

## `blake2s_core.v`

| | |
|---|---|
| Upstream | [secworks/blake2s](https://github.com/secworks/blake2s) |
| Path | `src/rtl/blake2s_core.v` |
| Commit | `dbecf482a6670fe0872621a8b25bf5b48efd9051` |
| Permalink | https://github.com/secworks/blake2s/blob/dbecf482a6670fe0872621a8b25bf5b48efd9051/src/rtl/blake2s_core.v |
| Licence | BSD-2-Clause (examples/licenses/assured-blake2s.LICENSE) |
| Copyright | Assured AB / Joachim Strömbergson |

BLAKE2s hashing core: the quarter-round G mixing function (blake2s_G), the message-word permutation select (blake2s_m_select), the eight IV constants and the parameter block, driven by a compression FSM. The IV constants plus the G-function rotation amounts are the crown jewels.

Security-relevant features: `IV constants`, `G mixing function`, `message permutation`, `compression FSM`

## `poly1305_core.v`

| | |
|---|---|
| Upstream | [secworks/poly1305](https://github.com/secworks/poly1305) |
| Path | `src/rtl/poly1305_core.v` |
| Commit | `7c950671355467ee9c28909f27a990f4b7fd10ec` |
| Permalink | https://github.com/secworks/poly1305/blob/7c950671355467ee9c28909f27a990f4b7fd10ec/src/rtl/poly1305_core.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-poly1305.LICENSE) |
| Copyright | Joachim Strömbergson / Secworks Sweden AB |

Poly1305 one-time-MAC core: a 130-bit modular multiply-accumulate over the block (poly1305_pblock feeding poly1305_mulacc) and the final 2^130-5 reduction (poly1305_final). Holds the r/s key material and its clamping mask; the prime-field reduction constants and the key clamp are the crown jewels.

Security-relevant features: `key material + clamp`, `prime-field reduction constants`, `modular multiply-accumulate`, `MAC FSM`

## `sha512_core.v`

| | |
|---|---|
| Upstream | [secworks/sha512](https://github.com/secworks/sha512) |
| Path | `src/rtl/sha512_core.v` |
| Commit | `e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd` |
| Permalink | https://github.com/secworks/sha512/blob/e4cdf33418a3aa95cee25e1f0b1d8a6ede51c1bd/src/rtl/sha512_core.v |
| Licence | BSD-2-Clause (examples/licenses/secworks-sha512.LICENSE) |
| Copyright | Joachim Strömbergson / Secworks Sweden AB |

SHA-512 compression-function core (also covers SHA-384/512-224/512-256 via mode): an 80-entry message schedule (sha512_w_mem), the 80x64-bit round-constant ROM (sha512_k_constants) and the mode-selected initial-hash constants (sha512_h_constants), sequenced by a round FSM. The round-constant ROM and init constants are the crown jewels.

Security-relevant features: `round-constant ROM`, `mode-selected init constants`, `message schedule`, `round FSM`

## Elaboration dependencies (not redaction targets)

Files under examples/deps/ are NOT redaction targets. They are unmodified upstream sibling modules required to elaborate several of the targets (keywrap_core.v, tiny_aes_128.v, sha1_core.v, blake2s_core.v, poly1305_core.v, sha512_core.v) so that Phase 5 can simulate and formally verify them. They are supplied to iverilog/yosys as context only and are never transformed or shipped.

| File | Upstream | Path | Commit | Licence | Role |
|---|---|---|---|---|---|
| `table.v` | [freecores/tiny_aes](https://github.com/freecores/tiny_aes) | `rtl/table.v` | `faf2afb2bcb6` | Apache-2.0 | S-box / T-table lookup modules (S4, T1-T4) instantiated by tiny_aes_128.v |
| `round.v` | [freecores/tiny_aes](https://github.com/freecores/tiny_aes) | `rtl/round.v` | `faf2afb2bcb6` | Apache-2.0 | one_round / final_round datapath stages instantiated by tiny_aes_128.v |
| `aes_core.v` | [secworks/aes](https://github.com/secworks/aes) | `src/rtl/aes_core.v` | `80dc4718e1dc` | BSD-2-Clause | AES core instantiated by keywrap_core.v |
| `aes_encipher_block.v` | [secworks/aes](https://github.com/secworks/aes) | `src/rtl/aes_encipher_block.v` | `80dc4718e1dc` | BSD-2-Clause | encryption datapath instantiated by aes_core.v |
| `aes_decipher_block.v` | [secworks/aes](https://github.com/secworks/aes) | `src/rtl/aes_decipher_block.v` | `80dc4718e1dc` | BSD-2-Clause | decryption datapath instantiated by aes_core.v |
| `aes_inv_sbox.v` | [secworks/aes](https://github.com/secworks/aes) | `src/rtl/aes_inv_sbox.v` | `80dc4718e1dc` | BSD-2-Clause | inverse S-box instantiated by aes_decipher_block.v |
| `sha1_w_mem.v` | [secworks/sha1](https://github.com/secworks/sha1) | `src/rtl/sha1_w_mem.v` | `50f82f4ca2f8` | BSD-2-Clause | 512-bit message-schedule (W) memory instantiated by sha1_core.v |
| `blake2s_G.v` | [secworks/blake2s](https://github.com/secworks/blake2s) | `src/rtl/blake2s_G.v` | `dbecf482a667` | BSD-2-Clause | quarter-round G mixing function instantiated by blake2s_core.v |
| `blake2s_m_select.v` | [secworks/blake2s](https://github.com/secworks/blake2s) | `src/rtl/blake2s_m_select.v` | `dbecf482a667` | BSD-2-Clause | message-word permutation select instantiated by blake2s_core.v |
| `poly1305_pblock.v` | [secworks/poly1305](https://github.com/secworks/poly1305) | `src/rtl/poly1305_pblock.v` | `7c9506713554` | BSD-2-Clause | per-block multiply stage (instantiates poly1305_mulacc) instantiated by poly1305_core.v |
| `poly1305_mulacc.v` | [secworks/poly1305](https://github.com/secworks/poly1305) | `src/rtl/poly1305_mulacc.v` | `7c9506713554` | BSD-2-Clause | multiply-accumulate unit instantiated by poly1305_pblock.v |
| `poly1305_final.v` | [secworks/poly1305](https://github.com/secworks/poly1305) | `src/rtl/poly1305_final.v` | `7c9506713554` | BSD-2-Clause | final 2^130-5 reduction instantiated by poly1305_core.v |
| `sha512_w_mem.v` | [secworks/sha512](https://github.com/secworks/sha512) | `src/rtl/sha512_w_mem.v` | `e4cdf33418a3` | BSD-2-Clause | 80-entry message-schedule (W) memory instantiated by sha512_core.v |
| `sha512_k_constants.v` | [secworks/sha512](https://github.com/secworks/sha512) | `src/rtl/sha512_k_constants.v` | `e4cdf33418a3` | BSD-2-Clause | 80x64-bit round-constant ROM instantiated by sha512_core.v |
| `sha512_h_constants.v` | [secworks/sha512](https://github.com/secworks/sha512) | `src/rtl/sha512_h_constants.v` | `e4cdf33418a3` | BSD-2-Clause | mode-selected initial-hash constants instantiated by sha512_core.v |

## Licences

Full upstream licence texts are reproduced verbatim in `examples/licenses/`. All twelve target files are redistributable: eleven under BSD-2-Clause, one (`tiny_aes_128.v`) under Apache-2.0.

## MIT-CEP benchmark overlap

Upstream: https://github.com/mit-ll/CEP, pinned commit `bcc812336910a095e6cb48a50ac123872fdac93f`. Source bytes are unchanged.

`des3` imports module `des3`; `sha256_core_cep` imports module `sha256`.
Dependencies are recorded individually in CITATIONS.json. No claim of GPS/round overlap is made.

- [examples/deps/cep_des3_crp.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/crp.v)
- [examples/rtl/des3.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/des3.v)
- [examples/deps/cep_des3_key_sel3.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/key_sel3.v)
- [examples/deps/cep_des3_sbox1.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox1.v)
- [examples/deps/cep_des3_sbox2.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox2.v)
- [examples/deps/cep_des3_sbox3.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox3.v)
- [examples/deps/cep_des3_sbox4.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox4.v)
- [examples/deps/cep_des3_sbox5.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox5.v)
- [examples/deps/cep_des3_sbox6.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox6.v)
- [examples/deps/cep_des3_sbox7.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox7.v)
- [examples/deps/cep_des3_sbox8.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/des3/sbox8.v)
- [examples/rtl/sha256_core_cep.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/sha256/sha256.v)
- [examples/deps/cep_sha256_sha256_k_constants.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/sha256/sha256_k_constants.v)
- [examples/deps/cep_sha256_sha256_w_mem.v](https://github.com/mit-ll/CEP/blob/bcc812336910a095e6cb48a50ac123872fdac93f/generators/mitll-blocks/src/main/resources/vsrc/sha256/sha256_w_mem.v)
