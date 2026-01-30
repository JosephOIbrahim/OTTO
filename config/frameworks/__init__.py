"""
Framework Orchestrator Payloads
===============================

Lazy-loadable framework modules following USD Payload Architecture.

Payloads are loaded on demand based on:
1. Signal detection (task triggers)
2. Mycelium weight distribution
3. Safety tier requirements

Loading Tiers:
- SAFETY: Always loaded (cognitive_safety_moe with safety floors)
- WEIGHTED: Loaded based on calibrated weights
- DEFERRED: Loaded only when explicitly needed

Usage:
    from framework_orchestrator.frameworks import PayloadManager

    manager = PayloadManager(mycelium)
    strategy = manager.get_loading_strategy(task)
    payloads = manager.load_payloads(strategy)
"""

from pathlib import Path

PAYLOAD_ROOT = Path(__file__).parent

AVAILABLE_PAYLOADS = [
    "cognitive_safety_moe",
    "adhd_moe",  # Backward compatibility alias
    "max_reflection",
    "nova_oracle",
    "echo_memory",
    "cortex_world"
]

__all__ = ["PAYLOAD_ROOT", "AVAILABLE_PAYLOADS"]
