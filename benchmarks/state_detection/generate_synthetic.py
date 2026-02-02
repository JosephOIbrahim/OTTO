"""
[He2025]-Compliant Synthetic Data Generator
============================================

Generates labeled test messages for state detection benchmarking.
All operations use fixed seeds and sorted iterations for determinism.

[He2025] Compliance:
- Fixed seed (0xCAFEBABE) for all random operations
- Sorted key iteration for dict/set operations
- round(x, 6) for all float values
- Deterministic message generation order
"""
import json
import random
from pathlib import Path
from typing import Final
from dataclasses import dataclass, asdict

# [He2025] Fixed seed for reproducibility
_DETERMINISM_SEED: Final[int] = 0xCAFEBABE

# Signal patterns from PRISM detector - maps state to example messages
PATTERNS: dict[str, list[str]] = {
    "frustrated": [
        "This is so frustrating",
        "Why won't this work",
        "I've tried everything and nothing works",
        "UGH this is broken",
        "I give up, this is impossible",
        "This is driving me crazy",
        "I can't figure this out no matter what I try",
        "Everything I do makes it worse",
        "I'm so done with this",
        "WHY IS THIS SO HARD",
    ],
    "overwhelmed": [
        "There's too much to do",
        "I can't keep track of everything",
        "I don't know where to start",
        "Everything is piling up",
        "I'm drowning in tasks",
        "So many things need attention",
        "I can't handle all of this",
        "It's all too much right now",
        "I feel paralyzed by choices",
        "Where do I even begin",
    ],
    "depleted": [
        "I'm so tired",
        "I can't focus anymore",
        "My brain is fried",
        "I need a break",
        "Running on empty",
        "I'm exhausted",
        "Can't think straight",
        "Too wiped to continue",
        "I'm burnt out",
        "Need to stop for today",
    ],
    "stuck": [
        "I don't know what to do next",
        "I'm going in circles",
        "I keep coming back to the same problem",
        "Nothing is working",
        "I've hit a wall",
        "Can't figure out the next step",
        "I'm blocked on this",
        "No idea how to proceed",
        "Been stuck on this for hours",
        "I keep trying the same thing",
    ],
    "exploring": [
        "What if we tried a different approach",
        "I wonder whether this would work",
        "Have you thought about doing it this way",
        "Let me think about this differently",
        "Could we explore another option",
        "What about trying something new",
        "I'm curious about alternatives",
        "Let's brainstorm some ideas",
        "What are the possibilities here",
        "I want to experiment with this",
    ],
    "focused": [
        "Let's continue with the implementation",
        "Here's my next step",
        "Moving on to the next task",
        "Making good progress",
        "I know exactly what to do",
        "Let me finish this section",
        "On track, proceeding as planned",
        "Got it, implementing now",
        "Clear on the approach, executing",
        "This is going well, continuing",
    ],
}

# Context additions for message variation
CONTEXTS: list[str] = [
    "I'm working on {task}.",
    "Trying to {action}.",
    "Dealing with {issue}.",
    "",  # No context
]

TASKS: list[str] = ["the API", "this feature", "the bug fix", "my project", "the refactor"]
ACTIONS: list[str] = ["finish this", "understand the code", "get this to work", "meet the deadline"]
ISSUES: list[str] = ["a difficult problem", "unexpected errors", "scope creep", "technical debt"]

# State to expert mapping (fixed, deterministic)
STATE_TO_EXPERT: dict[str, str] = {
    "frustrated": "Validator",
    "overwhelmed": "Scaffolder",
    "depleted": "Restorer",
    "stuck": "Scaffolder",
    "exploring": "Socratic",
    "focused": "Direct",
}


@dataclass
class Sample:
    """A single labeled sample for benchmarking."""
    id: str
    message: str
    annotated_state: str
    annotated_expert: str
    confidence: float
    source: str


def create_deterministic_rng(seed_offset: int = 0) -> random.Random:
    """Create a deterministic RNG with fixed seed + offset."""
    return random.Random(_DETERMINISM_SEED + seed_offset)


def generate_message(state: str, rng: random.Random, add_context: bool = False) -> str:
    """
    Generate a message for a given state.

    [He2025] Compliance:
    - Uses provided RNG (caller controls seed)
    - Deterministic selection from sorted pattern list
    """
    patterns = PATTERNS[state]
    base = rng.choice(patterns)

    if add_context and rng.random() < 0.3:
        context_template = rng.choice(CONTEXTS)
        if context_template:
            context = context_template.format(
                task=rng.choice(TASKS),
                action=rng.choice(ACTIONS),
                issue=rng.choice(ISSUES)
            )
            base = f"{base} {context}"

    return base


def generate_dataset(n_per_state: int = 35, include_context: bool = True) -> list[Sample]:
    """
    Generate balanced dataset across all states.

    [He2025] Compliance:
    - Sorted iteration over states
    - Fixed seed RNG for all random operations
    - Deterministic sample ordering

    Args:
        n_per_state: Number of samples per state (default 35 = 210 total)
        include_context: Whether to add context to some messages

    Returns:
        List of Sample objects in deterministic order
    """
    rng = create_deterministic_rng()
    samples: list[Sample] = []

    # [He2025] Sorted iteration over states
    for state in sorted(PATTERNS.keys()):
        for i in range(n_per_state):
            # Create sample with deterministic ID
            sample = Sample(
                id=f"syn_{state}_{i:03d}",
                message=generate_message(state, rng, add_context=include_context),
                annotated_state=state,
                annotated_expert=STATE_TO_EXPERT[state],
                confidence=round(0.85, 6),  # [He2025] fixed precision
                source="synthetic"
            )
            samples.append(sample)

    # [He2025] Deterministic shuffle with same RNG
    rng.shuffle(samples)

    return samples


def generate_edge_cases() -> list[Sample]:
    """
    Generate edge case samples for testing robustness.

    These are harder cases: ambiguous, multi-signal, or adversarial.
    """
    rng = create_deterministic_rng(seed_offset=1000)

    edge_cases = [
        # Ambiguous cases
        ("edge_ambig_001", "I don't know...", "stuck", 0.6),
        ("edge_ambig_002", "This is hard", "frustrated", 0.5),
        ("edge_ambig_003", "I need to think", "exploring", 0.55),

        # Multi-signal cases
        ("edge_multi_001", "I'm tired and frustrated", "frustrated", 0.7),
        ("edge_multi_002", "Too much to do and I'm stuck", "overwhelmed", 0.65),
        ("edge_multi_003", "What if... no wait, I'm too tired", "depleted", 0.6),

        # Short messages
        ("edge_short_001", "ugh", "frustrated", 0.7),
        ("edge_short_002", "ok", "focused", 0.5),
        ("edge_short_003", "hmm", "exploring", 0.4),

        # Long messages
        ("edge_long_001",
         "I've been working on this for three hours and every time I think I'm close "
         "something else breaks and I'm starting to wonder if this is even possible",
         "frustrated", 0.85),
        ("edge_long_002",
         "Let me think about this from a different angle, what if we approached it "
         "as a graph problem instead of trying to brute force the solution",
         "exploring", 0.8),

        # Neutral/unclear
        ("edge_neutral_001", "The code compiles", "focused", 0.4),
        ("edge_neutral_002", "Here's the output", "focused", 0.5),
        ("edge_neutral_003", "I ran the tests", "focused", 0.5),

        # Mixed signals
        ("edge_mixed_001", "Great progress but I'm exhausted", "depleted", 0.6),
        ("edge_mixed_002", "Finally fixed it but now there's more", "overwhelmed", 0.55),
    ]

    samples = []
    for sample_id, message, state, confidence in edge_cases:
        samples.append(Sample(
            id=sample_id,
            message=message,
            annotated_state=state,
            annotated_expert=STATE_TO_EXPERT[state],
            confidence=round(confidence, 6),
            source="edge_case"
        ))

    return samples


def save_dataset(samples: list[Sample], output_path: Path) -> None:
    """Save dataset to JSON file with metadata."""
    output = {
        "version": "1.0.0",
        "created": "2026-02-01",
        "determinism_seed": hex(_DETERMINISM_SEED),
        "he2025_compliant": True,
        "sample_count": len(samples),
        "samples": [asdict(s) for s in samples]
    }

    output_path.write_text(json.dumps(output, indent=2, sort_keys=True))


def verify_determinism(n_trials: int = 10) -> bool:
    """
    Verify that dataset generation is deterministic.

    [He2025] Compliance test: Same seed produces same output.
    """
    import hashlib

    hashes = []
    for _ in range(n_trials):
        samples = generate_dataset(n_per_state=10)
        # Hash the serialized samples
        serialized = json.dumps([asdict(s) for s in samples], sort_keys=True)
        h = hashlib.sha256(serialized.encode()).hexdigest()
        hashes.append(h)

    unique = set(hashes)
    if len(unique) == 1:
        print(f"[He2025] DETERMINISM VERIFIED: {n_trials} trials, hash={hashes[0][:16]}...")
        return True
    else:
        print(f"[He2025] DETERMINISM FAILED: {len(unique)} unique hashes in {n_trials} trials")
        return False


def main():
    """Generate and save benchmark datasets."""
    output_dir = Path(__file__).parent

    # Verify determinism first
    if not verify_determinism():
        print("ERROR: Determinism check failed. Aborting.")
        return

    # Generate main dataset (35 per state * 6 states = 210 synthetic)
    print("\nGenerating synthetic dataset...")
    synthetic = generate_dataset(n_per_state=35)
    save_dataset(synthetic, output_dir / "synthetic_dataset.json")
    print(f"  Saved {len(synthetic)} samples to synthetic_dataset.json")

    # Generate edge cases
    print("\nGenerating edge cases...")
    edge_cases = generate_edge_cases()
    save_dataset(edge_cases, output_dir / "edge_cases.json")
    print(f"  Saved {len(edge_cases)} samples to edge_cases.json")

    # Combined dataset
    print("\nGenerating combined dataset...")
    combined = synthetic + edge_cases
    save_dataset(combined, output_dir / "dataset.json")
    print(f"  Saved {len(combined)} samples to dataset.json")

    # Summary
    print("\n" + "="*60)
    print("DATASET GENERATION COMPLETE")
    print("="*60)
    print(f"  Synthetic samples: {len(synthetic)}")
    print(f"  Edge cases: {len(edge_cases)}")
    print(f"  Total: {len(combined)}")
    print(f"  Determinism seed: {hex(_DETERMINISM_SEED)}")
    print(f"  [He2025] Compliant: Yes")


if __name__ == "__main__":
    main()
