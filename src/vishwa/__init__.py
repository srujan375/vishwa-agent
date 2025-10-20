"""
Vishwa - Terminal-based Agentic Coding Assistant

Named after Vishwakarma, the Hindu god of engineering and craftsmanship.
"""

__version__ = "0.1.0"
__author__ = "Vishwa Team"

from vishwa.agent.core import VishwaAgent
from vishwa.cli.commands import main

__all__ = ["VishwaAgent", "main", "__version__"]
