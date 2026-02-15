"""
Thompson Sampling policy for the autocomplete contextual bandit.

Maintains Beta(alpha, beta) distributions per (bucket, strategy) pair.
Selects strategies by sampling from posteriors and picking the highest.
"""

import random
from typing import Dict, List, Optional, Tuple

from vishwa.autocomplete.rl.strategies import STRATEGY_NAMES


# Default priors: standard gets a strong prior, others are uninformed
DEFAULT_PRIORS: Dict[str, Tuple[float, float]] = {
    "standard": (10.0, 1.0),
}
UNINFORMED_PRIOR: Tuple[float, float] = (1.0, 1.0)

COLD_START_THRESHOLD = 50
EXPLORATION_FLOOR = 0.10
DECAY_INTERVAL = 500
DECAY_FACTOR = 0.95
KILL_MIN_OBSERVATIONS = 50
KILL_THRESHOLD = 0.05


class ThompsonSamplingPolicy:
    """Thompson Sampling contextual bandit policy over discrete strategies."""

    def __init__(self):
        # {bucket_key: {strategy_name: [alpha, beta]}}
        self.buckets: Dict[str, Dict[str, List[float]]] = {}
        # {bucket_key: [disabled_strategy_names]}
        self.disabled_strategies: Dict[str, List[str]] = {}
        self.total_interactions: int = 0

    def _get_params(self, bucket: str, strategy: str) -> List[float]:
        """Get or initialize Beta params for a (bucket, strategy) pair."""
        if bucket not in self.buckets:
            self.buckets[bucket] = {}
        if strategy not in self.buckets[bucket]:
            a, b = DEFAULT_PRIORS.get(strategy, UNINFORMED_PRIOR)
            self.buckets[bucket][strategy] = [a, b]
        return self.buckets[bucket][strategy]

    def _is_disabled(self, bucket: str, strategy: str) -> bool:
        return strategy in self.disabled_strategies.get(bucket, [])

    def _available_strategies(self, bucket: str) -> List[str]:
        return [s for s in STRATEGY_NAMES if not self._is_disabled(bucket, s)]

    def select_strategy(self, bucket: str) -> str:
        """
        Select a strategy for the given bucket using Thompson Sampling.

        Returns "standard" during cold start (first 50 interactions).
        10% of the time, picks uniformly at random (exploration floor).
        Otherwise, samples from Beta posteriors and returns the highest.
        """
        # Cold start: always use standard
        if self.total_interactions < COLD_START_THRESHOLD:
            return "standard"

        available = self._available_strategies(bucket)
        if not available:
            return "standard"

        # Exploration floor: 10% random
        if random.random() < EXPLORATION_FLOOR:
            return random.choice(available)

        # Thompson Sampling: sample from each Beta, pick highest
        best_strategy = available[0]
        best_sample = -1.0
        for strategy in available:
            params = self._get_params(bucket, strategy)
            sample = random.betavariate(params[0], params[1])
            if sample > best_sample:
                best_sample = sample
                best_strategy = strategy

        return best_strategy

    def update(self, bucket: str, strategy: str, reward: float) -> None:
        """
        Update the Beta distribution for a (bucket, strategy) with observed reward.

        Also increments total_interactions, triggers decay every 500 interactions,
        and checks kill switch.
        """
        params = self._get_params(bucket, strategy)
        params[0] += reward          # alpha += reward
        params[1] += (1.0 - reward)  # beta += (1 - reward)

        self.total_interactions += 1

        # Recency decay every DECAY_INTERVAL interactions
        if self.total_interactions % DECAY_INTERVAL == 0:
            self._apply_decay()

        # Kill switch check
        self._check_kill_switch(bucket, strategy)

    def _apply_decay(self) -> None:
        """Multiply all alpha/beta values by decay factor to prevent old data domination."""
        for bucket_params in self.buckets.values():
            for params in bucket_params.values():
                params[0] *= DECAY_FACTOR
                params[1] *= DECAY_FACTOR

    def _check_kill_switch(self, bucket: str, strategy: str) -> None:
        """Disable a strategy for a bucket if it's consistently terrible."""
        if strategy == "standard":
            return  # Never disable the default
        params = self._get_params(bucket, strategy)
        total = params[0] + params[1]
        if total > KILL_MIN_OBSERVATIONS:
            success_rate = params[0] / total
            if success_rate < KILL_THRESHOLD:
                if bucket not in self.disabled_strategies:
                    self.disabled_strategies[bucket] = []
                if strategy not in self.disabled_strategies[bucket]:
                    self.disabled_strategies[bucket].append(strategy)

    def get_stats(self) -> Dict:
        """Return policy state for debugging."""
        stats: Dict = {
            "total_interactions": self.total_interactions,
            "buckets": {},
        }
        for bucket, strategies in self.buckets.items():
            bucket_stats: Dict = {}
            for strategy, params in strategies.items():
                total = params[0] + params[1]
                mean = params[0] / total if total > 0 else 0.0
                bucket_stats[strategy] = {
                    "alpha": round(params[0], 2),
                    "beta": round(params[1], 2),
                    "mean": round(mean, 3),
                    "observations": round(total, 1),
                    "disabled": self._is_disabled(bucket, strategy),
                }
            stats["buckets"][bucket] = bucket_stats
        stats["disabled_strategies"] = dict(self.disabled_strategies)
        return stats
