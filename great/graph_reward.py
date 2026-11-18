"""Reward formulation for the RL-RGOT SensitivityAgent extension -- paper
Section 4.

Two distinct reward signals, both anchored to deterministic verifiers
already available in this pipeline rather than a learned reward model or
external labels, exactly as Section 4's closing note demands: "RL decides
what to investigate; deterministic algorithms decide what is actually
true."

  * graph_reward()   -- Eq. 1, scores one completed RGoT rollout (a
                         ReasoningGraph + the tier/strategy maps it produced).
                         Used to rank a GRPO rollout group in
                         great/rgot_policy.py.
  * generation_reward() -- Eq. 2, scores a single raw Phase-2/Phase-3 JSON
                         completion. Exposed so a future LLM-level GRPO
                         fine-tuning pass (paper Section 5, LLM instantiation)
                         has a ready-made, deterministic reward function; the
                         orchestration scripts also use it to log a reward
                         breakdown for every ensemble juror / strategy call
                         without requiring ground truth.

Both re-use this project's OWN deterministic tools rather than duplicating
them: great.vlog.dependency_closure for R_class / closure self-consistency,
and the paper's canonical Table 2 tier-to-transform policy (TABLE2, kept
local to this module since it is the RL-RGOT paper's own fixed mapping, not
the budget-tiered Table III used by great.config.BUDGET_TRANSFORMS /
Phase 3's B0/B1/B2 strategy) for R_strategy.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from . import config as C
from . import vlog
from .reasoning_graph import ReasoningGraph

# ------------------------------------------------------------------ Table 2
# Paper Table 2: tier -> transformations (T1-T10). Distinct from, and not a
# replacement for, great.config.BUDGET_TRANSFORMS (Phase 3's B0/B1/B2
# attacker-budget transformation sets, Table III of the GREAT/DAC-26 paper).
# This is the RL-RGOT paper's own canonical mapping, used purely as the
# ground truth R_strategy is checked against.
TABLE2: dict[str, list[str]] = {
    "HIGH": ["T1", "T2", "T3", "T4", "T5", "T8", "T9"],
    "MED": ["T2", "T6", "T8"],
    "LOW": ["T7", "T10"],  # applied globally, all tiers
}


def canonical_strategy(tier_map: dict[str, str]) -> dict[str, list[str]]:
    """Ground truth StrategyMap for R_strategy / generation-level Phase-3 reward."""
    out = {}
    for sig, tier in tier_map.items():
        transforms = list(TABLE2.get(tier, []))
        for g in TABLE2["LOW"]:
            if g not in transforms:
                transforms.append(g)
        out[sig] = transforms
    return out


@dataclass
class RewardWeights:
    """Eq. 1's w_c, w_g, w_x, w_v, w_s and lambda_d, lambda_n, lambda_t, lambda_a."""
    w_class: float = 1.0
    w_graph: float = 0.6
    w_cross: float = 0.6
    w_verify: float = 0.4
    w_strategy: float = 0.8
    lambda_depth: float = 0.02
    lambda_nodes: float = 0.01
    lambda_tokens: float = 0.0005
    lambda_actions: float = 0.01


@dataclass
class RewardBreakdown:
    r_class: float
    r_graph: float
    r_cross: float
    r_verify: float
    r_strategy: float
    c_depth: float
    c_nodes: float
    c_tokens: float
    c_actions: float
    total: float

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def _signal_refs(node) -> set:
    refs = set()
    for r in node.evidence + node.synthesized_evidence:
        refs.add(r.split(":")[-1])
    first_word = node.hypothesis.split()[0].strip(".,:;") if node.hypothesis else ""
    if first_word:
        refs.add(first_word)
    return refs


def _r_class(final_tier_map: dict[str, str], src: str) -> float:
    """Re-applies THIS pipeline's own deterministic closure
    (great.vlog.dependency_closure) to the rollout's own tier map and
    measures the fraction of signals whose tier is unchanged by closure.
    A self-consistent classification (closure has nothing to correct) scores 1.
    """
    if not final_tier_map:
        return 0.0
    seeds = [s for s, t in final_tier_map.items() if t == "HIGH"]
    closure = vlog.dependency_closure(src, seeds) if seeds else set()
    # a signal is "corrected" by closure if it sits in the closure set of a
    # HIGH seed but was not itself tagged HIGH by the rollout
    changed = {s for s in closure if final_tier_map.get(s) != "HIGH"}
    correct = len(final_tier_map) - len(changed)
    return max(0.0, correct / len(final_tier_map))


def _r_graph(rgraph: ReasoningGraph, src: str) -> float:
    """Fraction of depends_on reasoning edges backed by a real driver_graph
    fan-in/fan-out edge in the RTL -- penalises reasoning about dependencies
    that do not actually exist in the netlist."""
    depends_edges = [e for e in rgraph.edges if e.relation == "depends_on"]
    if not depends_edges:
        return 1.0  # vacuously fine -- nothing false was claimed
    graph = vlog.driver_graph(src)
    rev: dict[str, set] = {}
    for dst, srcs in graph.items():
        for s in srcs:
            rev.setdefault(s, set()).add(dst)

    def connected(a: str, b: str) -> bool:
        return b in graph.get(a, ()) or a in graph.get(b, ()) \
            or b in rev.get(a, ()) or a in rev.get(b, ())

    ok = 0
    for e in depends_edges:
        s_node, d_node = rgraph.nodes.get(e.src), rgraph.nodes.get(e.dst)
        if s_node is None or d_node is None:
            continue
        s_sigs, d_sigs = _signal_refs(s_node), _signal_refs(d_node)
        if any(connected(a, b) for a in s_sigs for b in d_sigs):
            ok += 1
    return ok / len(depends_edges)


def _r_cross(rgraph: ReasoningGraph, correspondence: dict[str, str] | None) -> float:
    """Fraction of corresponds_to edges that agree with the ground-truth
    original<->synthesized correspondence mapping (paper Section 3.1)."""
    corr_edges = [e for e in rgraph.edges if e.relation == "corresponds_to"]
    if not corr_edges:
        return 1.0
    if not correspondence:
        return 0.5  # cannot verify -- neutral score
    ok = 0
    for e in corr_edges:
        s_node, d_node = rgraph.nodes.get(e.src), rgraph.nodes.get(e.dst)
        if s_node is None or d_node is None:
            continue
        o_sigs = _signal_refs(s_node) | _signal_refs(d_node)
        s_sigs = set(s_node.synthesized_evidence) | set(d_node.synthesized_evidence)
        for o in o_sigs:
            mapped = correspondence.get(o)
            if mapped and any(mapped in s for s in s_sigs):
                ok += 1
                break
    return ok / len(corr_edges)


def _r_verify(rgraph: ReasoningGraph) -> float:
    """Fraction of terminal (leaf) nodes passed through a VERIFY action
    before being finalized."""
    terminal = rgraph.leaves()
    if not terminal:
        return 0.0
    return sum(1 for n in terminal if n.verified) / len(terminal)


def _r_strategy(final_tier_map: dict[str, str], final_strategy_map: dict | None) -> float:
    """Agreement between the produced StrategyMap and the canonical Table 2 mapping."""
    if not final_tier_map:
        return 0.0
    canonical = canonical_strategy(final_tier_map)
    if not final_strategy_map:
        return 0.0
    matches = 0
    for sig, canon_transforms in canonical.items():
        got = set(final_strategy_map.get(sig, []))
        if got == set(canon_transforms):
            matches += 1
    return matches / len(canonical)


def graph_reward(rgraph: ReasoningGraph, src: str, final_tier_map: dict[str, str],
                  correspondence: dict[str, str] | None = None,
                  final_strategy_map: dict | None = None,
                  approx_tokens_used: int = 0,
                  weights: RewardWeights | None = None) -> RewardBreakdown:
    """Eq. 1 -- the composite graph-level reward for one completed rollout."""
    w = weights or RewardWeights()
    r_class = _r_class(final_tier_map, src)
    r_graph = _r_graph(rgraph, src)
    r_cross = _r_cross(rgraph, correspondence)
    r_verify = _r_verify(rgraph)
    r_strategy = _r_strategy(final_tier_map, final_strategy_map)

    c_depth = float(rgraph.max_depth())
    c_nodes = float(rgraph.num_nodes())
    c_tokens = float(approx_tokens_used)
    c_actions = float(len(rgraph.action_log))

    total = (w.w_class * r_class + w.w_graph * r_graph + w.w_cross * r_cross
             + w.w_verify * r_verify + w.w_strategy * r_strategy
             - w.lambda_depth * c_depth - w.lambda_nodes * c_nodes
             - w.lambda_tokens * c_tokens - w.lambda_actions * c_actions)

    return RewardBreakdown(r_class=r_class, r_graph=r_graph, r_cross=r_cross,
                            r_verify=r_verify, r_strategy=r_strategy,
                            c_depth=c_depth, c_nodes=c_nodes, c_tokens=c_tokens,
                            c_actions=c_actions, total=total)


# ============================================================================
# Generation-level reward -- Eq. 2 (scores a raw Phase-2/Phase-3 JSON completion,
# not a whole reasoning graph). Exposed for a future LLM-weight GRPO fine-tuning
# pass (paper Section 5); the phase scripts also use it to log a per-juror /
# per-strategy-call reward breakdown without needing ground truth.
# ============================================================================
@dataclass
class GenerationRewardConfig:
    w_format: float = 0.2
    w_task: float = 1.0
    length_soft_budget_tokens: int = 220
    length_penalty_per_extra_token: float = 0.002
    format_fail_reward: float = -1.0


@dataclass
class GenerationRewardTerms:
    format_ok: float
    task_score: float
    length_penalty: float
    total: float
    detail: dict = field(default_factory=dict)


def _length_penalty(cfg: GenerationRewardConfig, num_generated_tokens: int) -> float:
    overflow = max(0, num_generated_tokens - cfg.length_soft_budget_tokens)
    return overflow * cfg.length_penalty_per_extra_token


def phase2_generation_reward(tier_map: dict[str, dict], signals: list[str], src: str,
                              ground_truth_tiers: dict[str, str] | None = None,
                              num_generated_tokens: int = 0,
                              cfg: GenerationRewardConfig | None = None) -> GenerationRewardTerms:
    """Eq. 2 for a single Phase-2 juror completion that has already been
    parsed into {signal: {"tier": ...}}. rformat is the fraction of
    requested signals that received a schema-valid tier entry; rtask
    combines closure self-consistency with (if available) ground-truth
    tier accuracy.
    """
    cfg = cfg or GenerationRewardConfig()
    length_penalty = _length_penalty(cfg, num_generated_tokens)
    flat = {s: e["tier"] for s, e in tier_map.items()
            if isinstance(e, dict) and e.get("tier") in C.TIER_RANK}
    format_ok = len(flat) / max(len(signals), 1)
    if not flat:
        return GenerationRewardTerms(format_ok=format_ok, task_score=0.0,
                                      length_penalty=length_penalty,
                                      total=cfg.format_fail_reward - length_penalty,
                                      detail={"error": "no_recognizable_tier_entries"})
    seeds = [s for s, t in flat.items() if t == "HIGH"]
    closure = vlog.dependency_closure(src, seeds) if seeds else set()
    changed = {s for s in closure if flat.get(s) != "HIGH"}
    consistency = max(0.0, (len(flat) - len(changed)) / len(flat))

    accuracy = None
    if ground_truth_tiers:
        common = [s for s in flat if s in ground_truth_tiers]
        if common:
            accuracy = sum(1 for s in common if flat[s] == ground_truth_tiers[s]) / len(common)

    task_score = 0.5 * consistency + 0.5 * accuracy if accuracy is not None else consistency
    total = cfg.w_format * format_ok + cfg.w_task * task_score - length_penalty
    return GenerationRewardTerms(format_ok=format_ok, task_score=task_score,
                                  length_penalty=length_penalty, total=total,
                                  detail={"consistency": consistency, "accuracy": accuracy,
                                          "changed_by_closure": sorted(changed)})


def phase3_generation_reward(produced: dict[str, list[str]], tier_map: dict[str, str],
                              num_generated_tokens: int = 0,
                              cfg: GenerationRewardConfig | None = None) -> GenerationRewardTerms:
    """Eq. 2 for a single Phase-3 strategy completion already parsed into
    {signal: [transforms...]}. rformat is the fraction of sensitive signals
    with a schema-valid transforms list; rtask is the fraction whose
    transform set exactly matches the canonical Table 2 entry, with partial
    credit for a valid subset of the correct policy.
    """
    cfg = cfg or GenerationRewardConfig()
    length_penalty = _length_penalty(cfg, num_generated_tokens)
    canonical = canonical_strategy(tier_map)
    n = max(len(canonical), 1)
    schema_hits, matches = 0, 0.0
    for sig, canon_transforms in canonical.items():
        got = produced.get(sig)
        if got is None:
            continue
        schema_hits += 1
        got_set, canon_set = set(got), set(canon_transforms)
        if got_set == canon_set:
            matches += 1
        elif got_set and got_set.issubset(canon_set | {"T7", "T10"}):
            matches += 0.5
    format_ok = schema_hits / n
    task_score = matches / n
    total = cfg.w_format * format_ok + cfg.w_task * task_score - length_penalty
    return GenerationRewardTerms(format_ok=format_ok, task_score=task_score,
                                  length_penalty=length_penalty, total=total,
                                  detail={"schema_hits": schema_hits, "matches": matches, "n": n})
