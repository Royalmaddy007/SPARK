"""Recursive Graph-of-Thoughts (RGoT) rollout driver -- paper Sections 3 and 5.

Reframes sensitivity analysis as graph construction over reasoning states
(Section 3.1): starting from a seed signal, the trained RGoTPolicy
(great/rgot_policy.py) selects a sequence of discrete actions that build a
ReasoningGraph, bounded by node/action/depth budgets (Section 3.3). A group
of G trajectories is sampled per seed signal, scored with the deterministic
reward of great/graph_reward.py (Eq. 1), and the best trajectory's tier map
feeds back into the orchestration pipeline; one GRPO group-relative update
(Section 5) is applied to the policy per seed.

This module is deliberately ADDITIVE: it never replaces Phase 2's N=3
ensemble vote (great/config.ENSEMBLE / phase2_sensitivity.vote) or the
dependency-closure pass that is already this pipeline's ground truth. It
runs the same deterministic closure as a second, RL-selected reasoning path
and is logged as a cross-check / confidence signal, exactly as the design
note frames RGoT: "the learned components decide what to investigate, while
fixed algorithms decide what is actually true."
"""
from __future__ import annotations
from dataclasses import dataclass, field

from . import vlog
from .graph_reward import RewardBreakdown, graph_reward
from .reasoning_graph import ReasoningGraph
from .rgot_policy import PolicyState, RGoTPolicy

TIER_RANK = {"LOW": 0, "MED": 1, "HIGH": 2}


@dataclass
class RGoTConfig:
    node_budget: int = 14
    action_budget: int = 24
    max_depth: int = 4
    group_size: int = 4


class RGoTAgent:
    """Runs recursive GoT rollouts over a netlist's driver graph (the same
    graph great.vlog.driver_graph / dependency_closure already build for the
    deterministic pass), using it in place of the paper's NetlistKG."""

    def __init__(self, config: RGoTConfig | None = None, policy: RGoTPolicy | None = None) -> None:
        self.cfg = config or RGoTConfig()
        self.policy = policy or RGoTPolicy()

    # ---- graph-navigation primitives over the RTL driver graph -----------
    def _fanout(self, graph: dict[str, set], rev: dict[str, set], sig: str) -> list[str]:
        return sorted(rev.get(sig, ()))   # signals DRIVEN BY sig

    def _fanin(self, graph: dict[str, set], rev: dict[str, set], sig: str) -> list[str]:
        return sorted(graph.get(sig, ()))  # signals that DRIVE sig

    def _policy_state(self, rgraph: ReasoningGraph, node, graph, rev, tool_calls: int) -> PolicyState:
        sig = node.hypothesis.split()[0].strip(".,:;") if node.hypothesis else ""
        fanout = self._fanout(graph, rev, sig)
        fanin = self._fanin(graph, rev, sig)
        on_shared_bus = len(fanin) > 1 and bool(fanout)
        return PolicyState(
            depth=node.depth, max_depth=self.cfg.max_depth,
            num_nodes=rgraph.num_nodes(), node_budget=self.cfg.node_budget,
            confidence=node.confidence, tier_hint=node.tier,
            has_fanout=bool(fanout), has_fanin=bool(fanin),
            on_shared_bus=on_shared_bus, unverified=not node.verified,
            tool_calls=tool_calls, action_budget=self.cfg.action_budget)

    def _handle_action(self, action: str, node, rgraph: ReasoningGraph, graph, rev,
                        seed_tiers: dict[str, str], correspondence):
        sig = node.hypothesis.split()[0].strip(".,:;") if node.hypothesis else ""

        if action == "CREATE_NODE":
            return rgraph.new_node(f"{sig} may be sensitive", evidence=[f"G_O:{sig}"],
                                   parent=node.reasoning_id)

        if action == "EXPAND_NODE":
            children = []
            for related in self._fanout(graph, rev, sig)[:3] + self._fanin(graph, rev, sig)[:1]:
                c = rgraph.new_node(f"{sig} relates to {related}", evidence=[f"G_O:{related}"],
                                    parent=node.reasoning_id)
                rgraph.add_edge(node.reasoning_id, c.reasoning_id, "refines")
                children.append(c)
            return children[0] if children else node

        if action == "FOLLOW_DEPENDENCY":
            downstream = self._fanout(graph, rev, sig)
            if not downstream:
                return node
            target = downstream[0]
            child = rgraph.new_node(f"{sig} drives {target}", evidence=[f"G_O:{target}"],
                                    parent=node.reasoning_id)
            rgraph.add_edge(node.reasoning_id, child.reasoning_id, "depends_on")
            return child

        if action == "COMPARE_KGS":
            if not correspondence:
                return node
            mapped = correspondence.get(sig)
            if mapped:
                child = rgraph.new_node(f"{sig} corresponds to synthesized {mapped}",
                                        evidence=[f"G_O:{sig}"], synthesized_evidence=[f"G_S:{mapped}"],
                                        parent=node.reasoning_id)
                rgraph.add_edge(node.reasoning_id, child.reasoning_id, "corresponds_to")
                return child
            return node

        if action == "CLASSIFY":
            # the learned components decide *what to investigate*; the actual
            # tier comes from the same seed-tier evidence the ensemble already
            # produced for this signal (fixed algorithms decide what is true).
            tier = seed_tiers.get(sig, "LOW")
            node.tier = tier
            node.confidence = min(1.0, node.confidence + 0.2)
            rgraph.log_action("CLASSIFY", node.reasoning_id, {"tier": tier})
            return node

        if action == "COMPUTE_CLOSURE":
            if node.tier:
                closure = vlog_closure_tier(graph, rev, sig, node.tier)
                for downstream_sig, new_tier in closure.items():
                    if downstream_sig == sig:
                        node.tier = new_tier
                        continue
                    child = rgraph.new_node(f"{downstream_sig} is {new_tier} sensitivity (closure)",
                                            evidence=[f"G_O:{downstream_sig}"], tier=new_tier,
                                            confidence=node.confidence, parent=node.reasoning_id)
                    rgraph.add_edge(node.reasoning_id, child.reasoning_id, "supports")
            return node

        if action == "VERIFY":
            if node.tier:
                closure = vlog_closure_tier(graph, rev, sig, node.tier)
                node.verified = closure.get(sig, node.tier) == node.tier
            rgraph.log_action("VERIFY", node.reasoning_id, {"verified": node.verified})
            return node

        if action == "MERGE":
            siblings = [n.reasoning_id for n in rgraph.children(node.parent)] if node.parent \
                else [node.reasoning_id]
            merged = rgraph.merge(siblings, f"{sig} = merged classification")
            merged.tier = node.tier
            merged.confidence = node.confidence
            return merged

        if action == "REVISE":
            node.confidence = max(0.0, min(1.0, node.confidence * 0.9))
            return node

        return node  # TERMINATE or unknown -- no-op

    def generate_trajectory(self, seed_signal: str, graph: dict[str, set], rev: dict[str, set],
                             seed_tiers: dict[str, str], correspondence: dict[str, str] | None = None,
                             temperature: float = 1.0, deterministic: bool = False
                             ) -> tuple[ReasoningGraph, dict[str, str], list[tuple[PolicyState, str]]]:
        """One recursive GoT rollout starting from `seed_signal`."""
        rgraph = ReasoningGraph()
        root = rgraph.new_node(f"{seed_signal} may be sensitive", evidence=[f"G_O:{seed_signal}"])
        current = root
        step_records: list[tuple[PolicyState, str]] = []
        tool_calls = 0

        while tool_calls < self.cfg.action_budget and rgraph.num_nodes() < self.cfg.node_budget:
            state = self._policy_state(rgraph, current, graph, rev, tool_calls)
            allowed = None
            if current.depth >= self.cfg.max_depth:
                allowed = ["CLASSIFY", "COMPUTE_CLOSURE", "VERIFY", "MERGE", "TERMINATE"]
            action, _logp = self.policy.select_action(
                state, temperature=temperature, deterministic=deterministic, allowed_actions=allowed)
            step_records.append((state, action))
            tool_calls += 1
            if action == "TERMINATE":
                break
            current = self._handle_action(action, current, rgraph, graph, rev, seed_tiers, correspondence)

        if current.tier is None:
            current = self._handle_action("CLASSIFY", current, rgraph, graph, rev, seed_tiers, correspondence)
            current = self._handle_action("VERIFY", current, rgraph, graph, rev, seed_tiers, correspondence)

        tier_map: dict[str, str] = {}
        for n in rgraph.nodes.values():
            n_sig = n.hypothesis.split()[0].strip(".,:;")
            if n.tier and n_sig:
                if n_sig not in tier_map or TIER_RANK[n.tier] > TIER_RANK[tier_map[n_sig]]:
                    tier_map[n_sig] = n.tier
        tier_map.setdefault(seed_signal, current.tier or "LOW")
        return rgraph, tier_map, step_records

    def run(self, src: str, seed_tiers: dict[str, str], seed_signals: list[str] | None = None,
            correspondence: dict[str, str] | None = None, group_size: int | None = None,
            train_policy: bool = True) -> dict:
        """Full recursive GRPO-GoT pass over one design: for every seed
        signal, sample a group of trajectories, score with graph_reward,
        keep the best, and (optionally) apply one GRPO policy update using
        the group's relative advantage. Aggregates best per-signal tier
        maps and re-applies the pipeline's own dependency closure.
        """
        group_size = group_size or self.cfg.group_size
        graph = vlog.driver_graph(src)
        rev: dict[str, set] = {}
        for dst, srcs in graph.items():
            for s in srcs:
                rev.setdefault(s, set()).add(dst)

        seeds = seed_signals or [s for s, t in seed_tiers.items() if t != "LOW"]
        aggregate_tiers: dict[str, str] = {}
        rollout_report: list[dict] = []

        for seed in seeds:
            trajectories, tier_maps, step_records_group = [], [], []
            rewards, breakdowns = [], []
            for _ in range(group_size):
                rgraph, tier_map, steps = self.generate_trajectory(
                    seed, graph, rev, seed_tiers, correspondence, temperature=1.0, deterministic=False)
                breakdown = graph_reward(rgraph, src, tier_map, correspondence,
                                         final_strategy_map=None,
                                         approx_tokens_used=200 * rgraph.num_nodes())
                trajectories.append(rgraph)
                tier_maps.append(tier_map)
                step_records_group.append(steps)
                rewards.append(breakdown.total)
                breakdowns.append(breakdown)

            best_idx = max(range(group_size), key=lambda i: rewards[i])
            best_tier_map = tier_maps[best_idx]
            for sig, tier in best_tier_map.items():
                if sig not in aggregate_tiers or TIER_RANK[tier] > TIER_RANK[aggregate_tiers[sig]]:
                    aggregate_tiers[sig] = tier

            if train_policy and len(set(rewards)) > 1:
                update_info = self.policy.update_from_group(step_records_group, rewards)
            else:
                update_info = {"mean_reward": sum(rewards) / len(rewards), "updated": False}

            rollout_report.append({
                "seed": seed, "rewards": [round(r, 4) for r in rewards],
                "best_trajectory": best_idx,
                "best_reward_breakdown": breakdowns[best_idx].to_dict(),
                "policy_update": update_info,
            })

        seed_high = [s for s, t in aggregate_tiers.items() if t == "HIGH"]
        closure = vlog.dependency_closure(src, seed_high) if seed_high else set()
        final_tiers = dict(aggregate_tiers)
        changed = set()
        for s in closure:
            if final_tiers.get(s) != "HIGH":
                changed.add(s)
                final_tiers[s] = "HIGH"

        return {
            "sensitivity_map": final_tiers,
            "closure_promoted": sorted(changed),
            "rollout_report": rollout_report,
            "policy_updates": self.policy.updates,
        }


def vlog_closure_tier(graph: dict[str, set], rev: dict[str, set], sig: str, tier: str) -> dict[str, str]:
    """Local one-signal closure helper used by COMPUTE_CLOSURE / VERIFY: if
    `sig` is `tier`, everything it (transitively) drives inherits at least
    that tier. Mirrors great.vlog.dependency_closure's promotion rule
    (fan-out only, since fan-in would reclassify the signal's own drivers
    rather than verify the signal itself)."""
    if tier not in TIER_RANK:
        return {sig: tier}
    out = {sig: tier}
    seen, work = {sig}, [sig]
    while work:
        n = work.pop()
        for nxt in rev.get(n, ()):
            if nxt not in seen:
                seen.add(nxt)
                work.append(nxt)
                out[nxt] = tier
    return out
