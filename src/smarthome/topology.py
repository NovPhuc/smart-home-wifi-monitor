from __future__ import annotations
import numpy as np


def build_transition_matrix(rooms: list[str], topology: dict[str, list[str]], self_weight: float = 0.75) -> np.ndarray:
    n = len(rooms)
    mat = np.zeros((n, n), dtype=np.float32)
    idx = {r: i for i, r in enumerate(rooms)}
    for src in rooms:
        allowed = [r for r in topology.get(src, []) if r in idx]
        if src not in allowed:
            allowed.append(src)
        others = [r for r in allowed if r != src]
        i = idx[src]
        if others:
            mat[i, i] = self_weight
            share = (1.0 - self_weight) / len(others)
            for dst in others:
                mat[i, idx[dst]] = share
        else:
            mat[i, i] = 1.0
    return mat


class TopologyFilter:
    def __init__(self, rooms: list[str], topology: dict[str, list[str]], self_weight: float = 0.75):
        self.rooms = rooms
        self.transition = build_transition_matrix(rooms, topology, self_weight)
        self.posterior: np.ndarray | None = None

    def reset(self):
        self.posterior = None

    def update(self, emission_probs: np.ndarray) -> np.ndarray:
        p = np.asarray(emission_probs, dtype=np.float32)
        total = float(p.sum())
        if not np.isfinite(total) or total <= 1e-12:
            # A degenerate emission (all zeros, NaN, +inf) must not zero out the
            # posterior: every later update would collapse to zero as well and
            # argmax would then always return the first room.
            p = np.full(p.shape, 1.0 / max(p.size, 1), dtype=np.float32)
        else:
            p = p / total
        if self.posterior is None:
            self.posterior = p
        else:
            prior = self.posterior @ self.transition
            post = prior * p
            post_total = float(post.sum())
            if not np.isfinite(post_total) or post_total <= 1e-12:
                # Carry the last normalised belief forward instead of
                # permanently poisoning the filter with a single bad reading.
                prior_total = float(prior.sum())
                if np.isfinite(prior_total) and prior_total > 1e-12:
                    post = prior / prior_total
                else:
                    post = np.full(prior.shape, 1.0 / max(prior.size, 1), dtype=np.float32)
            else:
                post = post / post_total
            self.posterior = post
        return self.posterior.copy()


def viterbi_decode(probabilities: np.ndarray, transition: np.ndarray) -> list[int]:
    probs = np.asarray(probabilities, dtype=np.float64)
    t_steps, n_states = probs.shape
    log_emit = np.log(probs + 1e-12)
    log_trans = np.log(transition + 1e-12)
    dp = np.full((t_steps, n_states), -np.inf)
    back = np.zeros((t_steps, n_states), dtype=np.int64)
    dp[0] = log_emit[0] - np.log(n_states)
    for t in range(1, t_steps):
        for j in range(n_states):
            candidates = dp[t - 1] + log_trans[:, j]
            best = int(np.argmax(candidates))
            dp[t, j] = candidates[best] + log_emit[t, j]
            back[t, j] = best
    states = [int(np.argmax(dp[-1]))]
    for t in range(t_steps - 1, 0, -1):
        states.append(int(back[t, states[-1]]))
    return list(reversed(states))
