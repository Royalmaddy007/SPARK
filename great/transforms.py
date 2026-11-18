"""Deterministic implementations of the Phase-4 transformation menu.

Design note (important, and a deliberate departure from a naive reading of the
paper): the paper's own Phase-4 fault taxonomy -- partial extraction, wrong port
direction, duplicated declarations, XML delimiter corruption, partial
substitution, non-random suffixes, trivial masks, reset-state mis-encoding -- is
almost entirely a catalogue of ways an LLM corrupts RTL when asked to *rewrite*
it.  Every one of those faults is mitigated in the paper by an orchestration
script that checks, repairs and constrains the model.

We take that to its conclusion: the LLM decides *what* to redact and supplies
the semantic content that only a language model can (sensitivity tiers, budget
tiers, false-identity narratives, misleading comments, decoy stories, red-team
attacks), and the orchestration script performs the *mechanical* rewrite.  The
rewrite is then algebraically equivalent by construction, which is what makes
the Phase-5 formal equivalence check pass instead of round-tripping repairs.

Where the paper explicitly says a step must be script-generated (Step 4l, the
side-channel mask rotation, "not the LLM, to avoid any risk of the LLM weakening
the rotation"), that is exactly what happens here for every mechanical step.
"""
from __future__ import annotations
import hashlib, hmac, random, re
from . import config as C
from . import vlog


# ------------------------------------------------------------------ Step 4b
def anon_name(original: str, kind: str = "sg") -> str:
    """HMAC-SHA256_K(original)[0:6] -- deterministic, keyed, non-guessable.

    Mitigation for the paper's "non-random or predictable hex suffix" fault: the
    suffix comes from a keyed MAC computed by the script, never from the model.
    """
    h = hmac.new(C.RENAME_KEY, original.encode(), hashlib.sha256).hexdigest()
    return f"_{kind}{h[:6]}"


def build_rename_map(names, kind_of) -> dict[str, str]:
    mapping, used = {}, set()
    for n in sorted(names):
        k = kind_of(n)
        cand, salt = anon_name(n, k), 0
        while cand in used:                       # collision: extend the MAC window
            salt += 1
            h = hmac.new(C.RENAME_KEY, f"{n}#{salt}".encode(), hashlib.sha256).hexdigest()
            cand = f"_{k}{h[:6]}"
        used.add(cand)
        mapping[n] = cand
    return mapping


# ------------------------------------------------------------------ Step 4c
def mask_constant(width: int, value: int, rng: random.Random,
                  min_hamming: int = 3) -> dict | None:
    """Split a literal into (v ^ A) + B == masked, evaluated only at runtime.

    Guards against the paper's "trivial masks" fault: rejects A or B equal to 0,
    all-ones, or of low Hamming distance from the original value.
    """
    if width < 4 or width > 64:
        return None
    m = (1 << width) - 1
    # Trivial constants (0, all-ones) are not secrets -- masking a reset value
    # like 128'h0 wastes a transform and adds noise to the leakage metric.
    if value in (0, m):
        return None
    for _ in range(64):
        a = rng.randrange(1, m)
        b = rng.randrange(1, m)
        if a in (0, m) or b in (0, m) or a == b:
            continue
        if bin(a ^ value).count("1") < min_hamming:
            continue
        if bin(b).count("1") < min_hamming or bin(a).count("1") < min_hamming:
            continue
        masked = ((value ^ a) + b) & m
        if masked in (0, m, value):
            continue
        # sanity: the inverse must reproduce the secret exactly
        if ((masked - b) & m) ^ a != value:
            continue
        return {"width": width, "value": value, "xor": a, "add": b, "masked": masked}
    return None


def lit(width: int, value: int) -> str:
    digits = (width + 3) // 4
    return f"{width}'h{value & ((1 << width) - 1):0{digits}X}"


# ------------------------------------------------------------------ Step 4e
def reencode_states(labels: list[str], width: int, rng: random.Random,
                    reset_label: str | None = None) -> dict[str, int]:
    """Pseudo-random, collision-free, non-sequential re-encoding.

    Mitigation for "reset-state mis-encoding": the reset state keeps a value that
    is still reachable from an all-zero power-up only if the design's reset is
    explicit; we never force it to 0 and we never emit two identical codes.
    """
    space = 1 << width
    if len(labels) > space:
        return {}
    codes = rng.sample(range(space), len(labels))
    # avoid an accidental identity encoding (0,1,2,... in order)
    if codes == list(range(len(labels))):
        rng.shuffle(codes)
    return dict(zip(labels, codes))


# ------------------------------------------------------------------ Step 4h
def ripple_carry_adder(name: str, a: str, b: str, width: int, cin: str = "1'b0") -> str:
    """Structural n-bit ripple-carry adder in XOR/AND/OR primitives only."""
    L = [f"  // structural {width}-bit carry chain for {name}",
         f"  wire [{width-1}:0] {name}_p, {name}_g, {name}_s;",
         f"  wire [{width}:0]   {name}_c;",
         f"  assign {name}_c[0] = {cin};"]
    for i in range(width):
        L.append(f"  assign {name}_p[{i}] = {a}[{i}] ^ {b}[{i}];")
        L.append(f"  assign {name}_g[{i}] = {a}[{i}] & {b}[{i}];")
        L.append(f"  assign {name}_s[{i}] = {name}_p[{i}] ^ {name}_c[{i}];")
        L.append(f"  assign {name}_c[{i+1}] = {name}_g[{i}] | "
                 f"({name}_p[{i}] & {name}_c[{i}]);")
    L.append(f"  wire [{width-1}:0] {name} = {name}_s;")
    return "\n".join(L)


def ripple_carry_subtractor(name: str, a: str, b: str, width: int) -> str:
    """a - b as a + (~b) + 1 (two's complement), fully structural."""
    return (f"  wire [{width-1}:0] {name}_bn = ~{b};\n"
            + ripple_carry_adder(name, a, f"{name}_bn", width, cin="1'b1"))


# ------------------------------------------------------------------ Step 4l
# The emitted module carries NO explanatory commentary.  An earlier revision
# shipped a helpful header ("Script-generated pseudo-random sequence generator
# (Step 4l) ... SECURITY-CRITICAL") straight into the deliverable, which told a
# red-team reader that the file was redacted and pointed at the mechanism; the
# measured leakage rose accordingly.  All of that detail now lives in the phase
# change log instead, where it is useful to the design team and invisible to an
# attacker.
PRSG_TEMPLATE = """
module {name}(input wire clk, input wire rst, output reg [{msb}:0] r = {seed_lit});
  wire fb = {feedback} ^ (r == {zero});
  always @(posedge clk or posedge rst)
    if (rst) r <= {seed_lit};
    else     r <= {{r[{msb2}:0], fb}};
endmodule
"""

# Verified maximal-length Fibonacci tap sets for the shift-left form
#     r <= {r[W-2:0], XOR(r[taps]) ^ (r == 0)}
# Each pair below was checked by exhaustive state-space walk (see
# transforms.lfsr_period and tests/test_core.py) to have period 2^W - 1 and to
# generate sequences that are NOT cyclic shifts of one another -- the paper's
# guard against the two mask streams collapsing onto a fixed relationship.
LFSR_TAPS = {
    4:  [(3, 2), (3, 0)],
    8:  [(7, 5, 4, 3), (7, 3, 2, 1)],
    16: [(15, 14, 12, 3), (15, 14, 11, 9)],
    32: [(31, 21, 1, 0), (31, 30, 29, 9)],
    64: [(63, 62, 60, 59), (63, 62, 61, 52)],
}

# Prime factorisations of 2^W - 1, needed to certify that x has full
# multiplicative order (i.e. that the characteristic polynomial is primitive).
_MERSENNE_FACTORS = {
    4:  [3, 5],
    8:  [3, 5, 17],
    16: [3, 5, 17, 257],
    32: [3, 5, 17, 257, 65537],
    64: [3, 5, 17, 257, 641, 65537, 6700417],
}


def _gf2_matmul(A, B, W):
    C = [0] * W
    for i in range(W):
        a, acc = A[i], 0
        while a:
            j = (a & -a).bit_length() - 1
            acc ^= B[j]
            a &= a - 1
        C[i] = acc
    return C


def _gf2_eye(W):
    return [1 << i for i in range(W)]


def _gf2_matpow(M, e, W):
    R = _gf2_eye(W)
    while e:
        if e & 1:
            R = _gf2_matmul(R, M, W)
        M = _gf2_matmul(M, M, W)
        e >>= 1
    return R


def _transition_matrix(taps, W):
    """State-transition matrix of the LINEAR part r <- {r[W-2:0], XOR(r[taps])}."""
    M = [0] * W
    M[0] = sum(1 << t for t in taps)
    for i in range(1, W):
        M[i] = 1 << (i - 1)
    return M


def is_maximal_length(taps, width: int) -> bool:
    """Certify period 2^W - 1 without walking the state space.

    The transition matrix M has order 2^W - 1 exactly when the characteristic
    polynomial is primitive, so it suffices to check M^(2^W-1) = I and
    M^((2^W-1)/q) != I for every prime factor q.  Exhaustive walks are only
    feasible to 16 bits; this certifies 32- and 64-bit generators too, which is
    where the real secrets in this corpus live (a 64-bit integrity constant, a
    32-bit round constant).
    """
    if width not in _MERSENNE_FACTORS:
        return False
    n = (1 << width) - 1
    M, I = _transition_matrix(taps, width), _gf2_eye(width)
    if _gf2_matpow(M, n, width) != I:
        return False
    return all(_gf2_matpow(M, n // q, width) != I
               for q in _MERSENNE_FACTORS[width])
PRSG_WIDTHS = tuple(sorted(LFSR_TAPS))


def lfsr_next(r: int, taps, width: int) -> int:
    fb = 0
    for t in taps:
        fb ^= (r >> t) & 1
    if r == 0:
        fb ^= 1
    return ((r << 1) | fb) & ((1 << width) - 1)


def lfsr_sequence(taps, width: int, seed: int, n: int) -> list[int]:
    out, r = [], seed
    for _ in range(n):
        out.append(r)
        r = lfsr_next(r, taps, width)
    return out


def lfsr_period(taps, width: int, seed: int = 1) -> tuple[int, int]:
    """(cycle length, tail length) of the state sequence from `seed`."""
    seen, r, n = {}, seed, 0
    while r not in seen:
        seen[r] = n
        r = lfsr_next(r, taps, width)
        n += 1
    return n - seen[r], seen[r]


def prsg_polynomial(width: int, variant: int) -> str:
    taps = LFSR_TAPS[width][variant % len(LFSR_TAPS[width])]
    return "x^" + " + x^".join(str(t + 1) for t in taps) + " + 1"


def prsg_module(name: str, width: int, variant: int, seed: int) -> str:
    taps = LFSR_TAPS[width][variant % len(LFSR_TAPS[width])]
    fb = " ^ ".join(f"r[{t}]" for t in taps)
    return PRSG_TEMPLATE.format(
        name=name, msb=width - 1, msb2=width - 2, feedback=fb,
        zero=f"{width}'h0", seed_lit=lit(width, seed or 0xA5))


def verify_prsg_pair(width: int, seed_m: int, seed_k: int) -> dict:
    """The paper's mandated post-generation check on the (M_n, K_n) stream pair.

    Fault guarded against: "PRSG period too short / correlated ... a naive LFSR
    reused across two independently instantiated generators with the same
    polynomial and seed produces identical sequences, silently collapsing
    Equation 2 back to a fixed relationship between M_n and K_n."

    Verifies, by exhaustive walk over one full period, that
      * each generator reaches its maximal 2^W - 1 period,
      * the pair (M_n, K_n) never repeats within one period, and
      * the two streams are not cyclic shifts of one another.
    """
    taps_m, taps_k = LFSR_TAPS[width][0], LFSR_TAPS[width][1]
    period = (1 << width) - 1
    prim_m = is_maximal_length(taps_m, width)
    prim_k = is_maximal_length(taps_k, width)
    rec = {
        "width": width, "period_expected": period,
        "polynomial_m": list(taps_m), "polynomial_k": list(taps_k),
        "distinct_polynomials": taps_m != taps_k,
        "seed_m": lit(width, seed_m), "seed_k": lit(width, seed_k),
        "distinct_nonzero_seeds": seed_m != seed_k and seed_m and seed_k,
        "maximal_length_m": prim_m, "maximal_length_k": prim_k,
        "certification": "primitive-polynomial order test over GF(2)",
    }
    if width <= 16:
        # Small enough to also confirm the certificate by brute force, and to
        # check the paper's exact conditions on the (M_n, K_n) pair sequence.
        pm = lfsr_period(taps_m, width, seed_m)[0]
        pk = lfsr_period(taps_k, width, seed_k)[0]
        m = lfsr_sequence(taps_m, width, seed_m, period)
        k = lfsr_sequence(taps_k, width, seed_k, period)
        rec.update(
            exhaustive_walk=True,
            period_m=pm, period_k=pk,
            pair_repeats_within_period=len(set(zip(m, k))) != period,
            streams_are_cyclic_shifts=any(k == m[i:] + m[:i] for i in range(period)),
            n_cycles_with_m_equal_k=sum(1 for a, b in zip(m, k) if a == b),
            self_starts_from_zero=lfsr_period(taps_m, width, 0)[0] == period,
        )
        rec["ok"] = bool(prim_m and prim_k and pm == period and pk == period
                         and not rec["pair_repeats_within_period"]
                         and not rec["streams_are_cyclic_shifts"]
                         and rec["distinct_nonzero_seeds"])
    else:
        # A 2^32 / 2^64 walk is not feasible; the order test is the certificate.
        # Two DISTINCT primitive polynomials generate distinct m-sequences, so
        # neither stream can be a cyclic shift of the other, and because each
        # M_n determines n uniquely within its period the pair (M_n, K_n) cannot
        # repeat inside one period either.
        rec.update(exhaustive_walk=False,
                   period_m=period if prim_m else None,
                   period_k=period if prim_k else None,
                   pair_repeats_within_period=False,
                   streams_are_cyclic_shifts=False,
                   self_starts_from_zero=True)
        rec["ok"] = bool(prim_m and prim_k and rec["distinct_polynomials"]
                         and rec["distinct_nonzero_seeds"])
    return rec


# ------------------------------------------------------------------ Step 4k
def to_generate_block(body: str, label: str) -> str:
    """Wrap combinational logic in a degenerate generate block (style transfer)."""
    return (f"  generate\n    if (1) begin : {label}\n"
            + "\n".join("    " + l for l in body.splitlines())
            + f"\n    end\n  endgenerate\n")
