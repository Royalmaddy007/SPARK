"""Recursive Graph-of-Thoughts (RGoT) data structures -- paper Section 3.

A ReasoningNode is a hypothesis/evidence state, NOT a netlist signal. Edges
express reasoning relationships (supports, contradicts, depends_on,
corresponds_to, verifies, refines), not circuit connectivity. Because
branches can merge and cross-reference one another, this is a genuine graph
rather than a search tree (Section 3.1).

This module is pure stdlib (no numpy/torch) so it stays as cheap to run as
the rest of the orchestration pipeline; it is driven by the linear-softmax
policy in great/rgot_policy.py and scored by great/graph_reward.py.
"""
from __future__ import annotations
import itertools
from dataclasses import dataclass, field

VALID_RELATIONS = {
    "supports", "contradicts", "depends_on",
    "corresponds_to", "verifies", "refines",
}

# Section 3.2's discrete action set.
VALID_ACTIONS = [
    "CREATE_NODE", "EXPAND_NODE", "FOLLOW_DEPENDENCY", "COMPARE_KGS",
    "CLASSIFY", "MERGE", "VERIFY", "COMPUTE_CLOSURE", "REVISE", "TERMINATE",
]

_id_counter = itertools.count(1)


def next_reasoning_id() -> str:
    return f"R{next(_id_counter)}"


@dataclass
class ReasoningNode:
    reasoning_id: str
    hypothesis: str
    evidence: list[str] = field(default_factory=list)              # G_O refs
    synthesized_evidence: list[str] = field(default_factory=list)  # G_S refs
    confidence: float = 0.5
    tier: str | None = None             # HIGH | MED | LOW, once classified
    depth: int = 0
    parent: str | None = None
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "reasoning_id": self.reasoning_id, "hypothesis": self.hypothesis,
            "evidence": self.evidence, "synthesized_evidence": self.synthesized_evidence,
            "confidence": round(self.confidence, 4), "tier": self.tier,
            "depth": self.depth, "parent": self.parent, "verified": self.verified,
        }


@dataclass
class ReasoningEdge:
    src: str
    dst: str
    relation: str

    def __post_init__(self) -> None:
        if self.relation not in VALID_RELATIONS:
            raise ValueError(f"Unknown reasoning relation: {self.relation}")


class ReasoningGraph:
    """A genuine graph (not a tree): branches can merge via MERGE / VERIFY /
    corresponds_to edges, per Section 3.1 of the design note."""

    def __init__(self) -> None:
        self.nodes: dict[str, ReasoningNode] = {}
        self.edges: list[ReasoningEdge] = []
        self.action_log: list[dict] = []   # (action, node_id, features) trail

    # ---- construction ----------------------------------------------------
    def add_node(self, node: ReasoningNode) -> ReasoningNode:
        self.nodes[node.reasoning_id] = node
        return node

    def new_node(self, hypothesis: str, evidence: list[str] | None = None,
                 synthesized_evidence: list[str] | None = None,
                 confidence: float = 0.5, tier: str | None = None,
                 parent: str | None = None) -> ReasoningNode:
        depth = 0
        if parent and parent in self.nodes:
            depth = self.nodes[parent].depth + 1
        node = ReasoningNode(
            reasoning_id=next_reasoning_id(), hypothesis=hypothesis,
            evidence=evidence or [], synthesized_evidence=synthesized_evidence or [],
            confidence=confidence, tier=tier, depth=depth, parent=parent)
        self.add_node(node)
        if parent:
            self.add_edge(parent, node.reasoning_id, "refines")
        return node

    def add_edge(self, src: str, dst: str, relation: str) -> None:
        self.edges.append(ReasoningEdge(src, dst, relation))

    # ---- queries -----------------------------------------------------------
    def children(self, node_id: str) -> list[ReasoningNode]:
        return [self.nodes[e.dst] for e in self.edges if e.src == node_id and e.dst in self.nodes]

    def related(self, node_id: str, relation: str) -> list[ReasoningNode]:
        out = []
        for e in self.edges:
            if e.relation != relation:
                continue
            if e.src == node_id and e.dst in self.nodes:
                out.append(self.nodes[e.dst])
            elif e.dst == node_id and e.src in self.nodes:
                out.append(self.nodes[e.src])
        return out

    def leaves(self) -> list[ReasoningNode]:
        """Terminal (leaf) nodes -- used by R_verify (paper Eq. 1)."""
        parents = {e.src for e in self.edges}
        return [n for nid, n in self.nodes.items() if nid not in parents]

    def merge(self, node_ids: list[str], into_hypothesis: str) -> ReasoningNode:
        """MERGE action: fold several supporting nodes into one node."""
        parents_conf = [self.nodes[nid].confidence for nid in node_ids if nid in self.nodes]
        merged_conf = sum(parents_conf) / max(len(parents_conf), 1)
        merged = self.new_node(into_hypothesis, confidence=merged_conf)
        for nid in node_ids:
            if nid in self.nodes:
                self.add_edge(nid, merged.reasoning_id, "supports")
        return merged

    def num_nodes(self) -> int:
        return len(self.nodes)

    def max_depth(self) -> int:
        return max((n.depth for n in self.nodes.values()), default=0)

    def log_action(self, action: str, node_id: str | None, features: dict) -> None:
        self.action_log.append({"action": action, "node_id": node_id, "features": features})

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [{"src": e.src, "dst": e.dst, "relation": e.relation} for e in self.edges],
            "action_log": self.action_log,
        }
