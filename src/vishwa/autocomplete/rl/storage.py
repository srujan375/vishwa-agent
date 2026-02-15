"""
Persistence for the autocomplete RL policy.

Saves/loads policy state to ~/.vishwa/rl/autocomplete_policy.json
and maintains a rolling feedback log at ~/.vishwa/rl/autocomplete_feedback.jsonl.
"""

import json
import time
import os
from pathlib import Path
from typing import Dict, Any

from vishwa.autocomplete.rl.policy import ThompsonSamplingPolicy

POLICY_DIR = Path.home() / ".vishwa" / "rl"
POLICY_FILE = POLICY_DIR / "autocomplete_policy.json"
FEEDBACK_FILE = POLICY_DIR / "autocomplete_feedback.jsonl"
MAX_FEEDBACK_ENTRIES = 1000
POLICY_VERSION = 1


class PolicyStorage:
    """Handles persistence of the Thompson Sampling policy."""

    def __init__(self, policy_dir: Path = POLICY_DIR):
        self.policy_dir = policy_dir
        self.policy_file = policy_dir / "autocomplete_policy.json"
        self.feedback_file = policy_dir / "autocomplete_feedback.jsonl"

    def save(self, policy: ThompsonSamplingPolicy) -> None:
        """Save policy state to disk."""
        self.policy_dir.mkdir(parents=True, exist_ok=True)

        data: Dict[str, Any] = {
            "version": POLICY_VERSION,
            "total_interactions": policy.total_interactions,
            "buckets": {},
            "disabled_strategies": dict(policy.disabled_strategies),
        }

        for bucket, strategies in policy.buckets.items():
            data["buckets"][bucket] = {}
            for strategy, params in strategies.items():
                data["buckets"][bucket][strategy] = [params[0], params[1]]

        tmp_file = self.policy_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            json.dump(data, f, indent=2)
        # Atomic rename
        tmp_file.replace(self.policy_file)

    def load(self, policy: ThompsonSamplingPolicy) -> None:
        """Load policy state from disk into the given policy object."""
        if not self.policy_file.exists():
            return

        with open(self.policy_file, "r") as f:
            data = json.load(f)

        if data.get("version") != POLICY_VERSION:
            return  # Incompatible version, start fresh

        policy.total_interactions = data.get("total_interactions", 0)

        for bucket, strategies in data.get("buckets", {}).items():
            policy.buckets[bucket] = {}
            for strategy, params in strategies.items():
                policy.buckets[bucket][strategy] = [float(params[0]), float(params[1])]

        policy.disabled_strategies = {}
        for bucket, disabled in data.get("disabled_strategies", {}).items():
            policy.disabled_strategies[bucket] = list(disabled)

    def log_feedback(
        self,
        bucket: str,
        strategy: str,
        accepted: bool,
        latency_ms: float,
    ) -> None:
        """Append a feedback entry to the rolling JSONL log."""
        self.policy_dir.mkdir(parents=True, exist_ok=True)

        entry = {
            "ts": int(time.time()),
            "bucket": bucket,
            "strategy": strategy,
            "accepted": accepted,
            "latency_ms": round(latency_ms, 1),
        }

        with open(self.feedback_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        self._truncate_feedback_log()

    def _truncate_feedback_log(self) -> None:
        """Keep only the last MAX_FEEDBACK_ENTRIES entries in the feedback log."""
        if not self.feedback_file.exists():
            return

        # Only check size periodically (every ~100 entries) to avoid constant reads
        try:
            file_size = self.feedback_file.stat().st_size
        except OSError:
            return

        # Rough heuristic: each entry is ~100-150 bytes
        # Only truncate if file seems large enough
        if file_size < MAX_FEEDBACK_ENTRIES * 100:
            return

        with open(self.feedback_file, "r") as f:
            lines = f.readlines()

        if len(lines) <= MAX_FEEDBACK_ENTRIES:
            return

        # Keep only the last MAX_FEEDBACK_ENTRIES entries
        lines = lines[-MAX_FEEDBACK_ENTRIES:]
        tmp_file = self.feedback_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            f.writelines(lines)
        tmp_file.replace(self.feedback_file)
