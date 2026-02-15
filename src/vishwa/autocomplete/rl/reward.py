"""
Reward computation for the autocomplete contextual bandit.

Combines acceptance signal and latency into a single [0, 1] reward.
"""


def compute_reward(accepted: bool, latency_ms: float) -> float:
    """
    Compute reward from acceptance and latency.

    accepted + fast (~0ms) = 1.0
    accepted + slow (2s)   = 0.7
    rejected + fast        = 0.3
    rejected + slow (2s+)  = 0.0

    Args:
        accepted: Whether the suggestion was accepted by the user.
        latency_ms: Time in milliseconds from request to response.

    Returns:
        Reward in [0.0, 1.0].
    """
    acceptance_reward = 0.7 * float(accepted)
    latency_reward = 0.3 * max(0.0, 1.0 - latency_ms / 2000.0)
    return acceptance_reward + latency_reward
