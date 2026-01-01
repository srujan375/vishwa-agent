"""
Configuration management for Vishwa.

Loads settings from environment variables and provides configuration objects.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:

    """Vishwa configuration."""

    model: Optional[str] = None
    max_iterations: int = 15
    auto_approve: bool = False
    verbose: bool = False
    loop_detection_threshold: int = 15
    skip_review: bool = False

    def __init__(self):
        """Initialize config from environment variables."""
        self.model = os.getenv("VISHWA_MODEL")
        self.max_iterations = int(os.getenv("VISHWA_MAX_ITERATIONS", "30"))
        self.auto_approve = os.getenv("VISHWA_AUTO_APPROVE", "false").lower() == "true"
        self.verbose = os.getenv("VISHWA_VERBOSE", "false").lower() == "true"
        self.loop_detection_threshold = int(os.getenv("VISHWA_LOOP_THRESHOLD", "15"))
        self.skip_review = os.getenv("VISHWA_SKIP_REVIEW", "false").lower() == "true"
