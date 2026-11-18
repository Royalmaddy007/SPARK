"""RGoT action-selection policy -- paper Sections 3.2-3.4 and 5 (GRPO).

A linear-softmax policy pi_theta over the 12-feature state phi(s) in R^12
(Section 3.4): normalized depth, normalized graph size, confidence, a
one-hot tier hint, fan-in/fan-out/shared-bus flags, verified flag and
normalized tool-call budget usage. Action probabilities are

    pi_theta(a | s) = softmax(W phi(s))_a,   W in R^(10x12)

which keeps the policy small enough to train online with a handful of
rollouts per design (Section 3.4) while remaining a genuine, trainable
stochastic policy rather than a fixed heuristic.

Training uses the graph-navigation instantiation of GRPO (Section 5.3):
group-relative advantages (Eq. 3) over a batch of sampled trajectories for
the same seed signal, with NO KL/reference term, because -- as the paper
notes -- "there is no pretrained prior over graph-construction actions to
stay close to." This is pure-Python/stdlib (no torch) so it matches the
rest of this pipeline's dependency footprint; it is a faithful, much
smaller-scale realisation of the same group-relative-advantage update used
by the LLM-level GRPO trainer in great/grpo_llm_trainer.py.
"""
from __future__ import annotations
import json, math, random
from dataclasses import dataclass, field
from pathlib import Path

from .reasoning_graph import VALID_ACTIONS

N_FEATURES = 12
N_ACTIONS = len(VALID_ACTIONS)  # 10
_TIERS = ("HIGH", "MED", "LOW")


@dataclass
class PolicyState:
    """phi(s) inputs -- Section 3.4's 12 interpretable state features."""
    depth: int
    max_depth: int
    num_nodes: int
    node_budget: int
    confidence: float
    tier_hint: str | None
    has_fanout: bool
    has_fanin: bool
    on_shared_bus: bool
    unverified: bool
    tool_calls: int
    action_budget: int

    def features(self) -> list[float]:
        """The paper's 11 named, interpretable state features (normalized
        depth, normalized graph size, confidence, 3-way tier one-hot,
        fan-out, fan-in, shared-bus, unverified, tool-call budget usage)
        plus a constant bias term, giving phi(s) in R^12 exactly as
        Section 3.4 specifies (W in R^(10x12))."""
        one_hot = [1.0 if self.tier_hint == t else 0.0 for t in _TIERS]
        return [
            self.depth / max(self.max_depth, 1),
            self.num_nodes / max(self.node_budget, 1),
            self.confidence,
            *one_hot,                                   # HIGH, MED, LOW
            1.0 if self.has_fanout else 0.0,
            1.0 if self.has_fanin else 0.0,
            1.0 if self.on_shared_bus else 0.0,
            1.0 if self.unverified else 0.0,
            self.tool_calls / max(self.action_budget, 1),
            1.0,                                         # bias term
        ]


def _zeros(rows: int, cols: int) -> list[list[float]]:
    return [[0.0] * cols for _ in range(rows)]


def _softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps) or 1.0
    return [e / s for e in exps]


@dataclass
class RGoTPolicyConfig:
    learning_rate: float = 0.05
    seed: int = 0
    # A mild bias toward CLASSIFY/VERIFY/TERMINATE keeps a freshly-initialised
    # (all-zero weight) policy from wandering randomly over the full action
    # set before any training has happened -- rollouts still terminate with
    # a classified, verified node even with W == 0.
    init_bias: dict = field(default_factory=lambda: {
        "CLASSIFY": 0.4, "VERIFY": 0.3, "TERMINATE": 0.1,
        "COMPUTE_CLOSURE": 0.2,
    })


class RGoTPolicy:
    """pi_theta(a|s) = softmax(W phi(s))_a, trained online with group-relative
    policy gradient (GRPO, no critic/value network -- Section 5.1)."""

    def __init__(self, config: RGoTPolicyConfig | None = None) -> None:
        self.cfg = config or RGoTPolicyConfig()
        self._rng = random.Random(self.cfg.seed)
        self.W: list[list[float]] = _zeros(N_ACTIONS, N_FEATURES)
        for action, bias in self.cfg.init_bias.items():
            if action in VALID_ACTIONS:
                row = VALID_ACTIONS.index(action)
                self.W[row][2] = bias  # weight on the confidence feature as a mild prior
        self.updates = 0

    # ---- inference ----------------------------------------------------
    def logits(self, state: PolicyState) -> list[float]:
        x = state.features()
        return [sum(w * xi for w, xi in zip(row, x)) for row in self.W]

    def action_probs(self, state: PolicyState, allowed_actions: list[str] | None = None) -> dict[str, float]:
        logits = self.logits(state)
        if allowed_actions:
            logits = [lg if a in allowed_actions else -1e9 for a, lg in zip(VALID_ACTIONS, logits)]
        probs = _softmax(logits)
        return dict(zip(VALID_ACTIONS, probs))

    def select_action(self, state: PolicyState, temperature: float = 1.0,
                       deterministic: bool = False,
                       allowed_actions: list[str] | None = None) -> tuple[str, float]:
        """Returns (action, log_prob_of_that_action)."""
        logits = self.logits(state)
        if allowed_actions:
            logits = [lg if a in allowed_actions else -1e9 for a, lg in zip(VALID_ACTIONS, logits)]
        scaled = [lg / max(temperature, 1e-6) for lg in logits]
        probs = _softmax(scaled)
        if deterministic:
            idx = max(range(N_ACTIONS), key=lambda i: probs[i])
        else:
            r = self._rng.random()
            cum = 0.0
            idx = N_ACTIONS - 1
            for i, p in enumerate(probs):
                cum += p
                if r <= cum:
                    idx = i
                    break
        action = VALID_ACTIONS[idx]
        logp = math.log(max(probs[idx], 1e-12))
        return action, logp

    # ---- GRPO group-relative policy-gradient update (Section 5.1, 5.3) ---
    def update_from_group(self, step_records_group: list[list[tuple[PolicyState, str]]],
                           rewards: list[float], eps: float = 1e-6) -> dict:
        """One GRPO step for the discrete graph-navigation policy.

        Per Eq. 3, advantage A_i = (r_i - mean(r)) / (std(r) + eps) is
        computed once per whole trajectory and broadcast to every action
        taken along it (sequence-level credit assignment, matching the
        LLM-level instantiation in great/grpo_llm_trainer.py). There is no
        clip term and no KL-to-reference term here: with trajectories of
        discrete actions rather than token sequences, and no pretrained
        prior over graph-construction actions, the paper's Section 5.3
        describes this as "the same structure [as the LLM case] ... with no
        KL/reference term." A single-step REINFORCE-with-group-baseline
        gradient ascent is used in place of PPO's clipped ratio objective.
        """
        G = len(rewards)
        if G == 0:
            return {"mean_reward": 0.0, "updated": False}
        mean_r = sum(rewards) / G
        var_r = sum((r - mean_r) ** 2 for r in rewards) / G
        std_r = math.sqrt(var_r)
        advantages = [(r - mean_r) / (std_r + eps) for r in rewards]

        if std_r < 1e-9:
            # Degenerate group (every trajectory scored identically): there is
            # no relative signal to learn from, so skip the update rather than
            # push weights on a meaningless all-equal advantage.
            return {"mean_reward": mean_r, "std_reward": std_r, "updated": False}

        lr = self.cfg.learning_rate
        for steps, A in zip(step_records_group, advantages):
            for state, action in steps:
                x = state.features()
                probs = self.action_probs(state)
                a_idx = VALID_ACTIONS.index(action)
                # d/dW_j log pi(a|s) = (1[j==a] - pi_j) * x   (standard softmax
                # policy-gradient identity); scale by the trajectory's
                # group-relative advantage and ascend.
                for j in range(N_ACTIONS):
                    indicator = 1.0 if j == a_idx else 0.0
                    coeff = lr * A * (indicator - probs[VALID_ACTIONS[j]])
                    if coeff == 0.0:
                        continue
                    row = self.W[j]
                    for k in range(N_FEATURES):
                        row[k] += coeff * x[k]
        self.updates += 1
        return {"mean_reward": mean_r, "std_reward": std_r, "updated": True,
                "advantages": [round(a, 4) for a in advantages]}

    # ---- persistence ----------------------------------------------------
    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({
            "actions": VALID_ACTIONS, "W": self.W, "updates": self.updates,
            "config": {"learning_rate": self.cfg.learning_rate, "seed": self.cfg.seed},
        }, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "RGoTPolicy":
        data = json.loads(Path(path).read_text())
        pol = cls(RGoTPolicyConfig(learning_rate=data["config"]["learning_rate"],
                                    seed=data["config"]["seed"]))
        pol.W = data["W"]
        pol.updates = data.get("updates", 0)
        return pol
