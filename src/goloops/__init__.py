"""Graph of loops: schedule a fleet, run each node as a bounded loop, take done back."""

from goloops.dag import CycleError, Node, waves
from goloops.gate import GateResult, run_gate, unfinish
from goloops.loop import LoopResult, run_loop

__version__ = "0.1.0"
__all__ = [
    "CycleError",
    "GateResult",
    "LoopResult",
    "Node",
    "run_gate",
    "run_loop",
    "unfinish",
    "waves",
]
