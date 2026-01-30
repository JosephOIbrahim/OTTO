"""
ECHO Memory Payload - Weighted Tier
===================================

Implements LIVRPS memory architecture from ECHO 2.0 Framework.

Source Frameworks:
- ECHO 2.0 Framework
- USD Composition Semantics

Key Features:
- 6-layer memory composition (LIVRPS)
- Principles layer protection (NEVER compressed)
- Memory mode variants (focused/exploratory/recovery)

LIVRPS Resolution Order (strongest to weakest):
- LOCAL: Session state (compresses first)
- INHERITS: Parent context
- VARIANTSETS: Memory modes
- REFERENCES: Calibration data
- PAYLOADS: Domain knowledge
- SPECIALIZES: Principles (NEVER compressed)
"""

from typing import Dict, List, Any
from enum import Enum

class MemoryLayer(Enum):
    """LIVRPS memory layers in resolution order."""
    LOCAL = "local"
    INHERITS = "inherits"
    VARIANTSETS = "variantsets"
    REFERENCES = "references"
    PAYLOADS = "payloads"
    SPECIALIZES = "specializes"

# Compression order (lower = compress first, None = never compress)
COMPRESSION_ORDER = {
    MemoryLayer.LOCAL: 1,
    MemoryLayer.INHERITS: 2,
    MemoryLayer.PAYLOADS: 3,
    MemoryLayer.VARIANTSETS: None,  # Never compress
    MemoryLayer.REFERENCES: None,   # Never compress
    MemoryLayer.SPECIALIZES: None   # NEVER compress
}

# Memory modes (variants)
MEMORY_MODES = {
    "focused_recall": {
        "description": "Precise, task-relevant memory retrieval",
        "token_budget": 4096,
        "triggers": ["specific", "exact", "find", "locate"]
    },
    "exploratory_recall": {
        "description": "Associative, broad memory retrieval",
        "token_budget": 8192,
        "triggers": ["explore", "related", "similar", "brainstorm"]
    },
    "recovery_recall": {
        "description": "Minimal memory, safety-first retrieval",
        "token_budget": 2048,
        "triggers": ["help", "stuck", "error", "confused"]
    }
}

def get_triggers() -> List[str]:
    """Triggers for loading this payload."""
    return ["remember", "recall", "history", "context", "memory", "previous"]

def detect_memory_mode(task: str) -> str:
    """Detect appropriate memory mode from task signals."""
    task_lower = task.lower()

    for mode_name, mode_config in MEMORY_MODES.items():
        if any(t in task_lower for t in mode_config["triggers"]):
            return mode_name

    return "focused_recall"

def resolve_memory_query(query: str, layers: Dict[str, Dict]) -> Dict[str, Any]:
    """Resolve memory query using LIVRPS priority.

    Walks the stack from LOCAL (strongest) to SPECIALIZES (foundational).
    """
    resolution = {
        "query": query,
        "resolved_from": None,
        "resolution_path": [],
        "principles_consulted": False
    }

    for layer in MemoryLayer:
        layer_data = layers.get(layer.value, {})
        resolution["resolution_path"].append(layer.value)

        if layer == MemoryLayer.SPECIALIZES:
            resolution["principles_consulted"] = True

        if layer_data:
            resolution["resolved_from"] = layer.value
            break

    return resolution

def get_compression_candidates(layers: Dict[str, Dict]) -> List[str]:
    """Return layers that can be compressed, in compression order."""
    candidates = []

    for layer, order in COMPRESSION_ORDER.items():
        if order is not None and layers.get(layer.value):
            candidates.append((order, layer.value))

    return [layer for _, layer in sorted(candidates)]

__all__ = ["MemoryLayer", "COMPRESSION_ORDER", "MEMORY_MODES", "get_triggers",
           "detect_memory_mode", "resolve_memory_query", "get_compression_candidates"]
