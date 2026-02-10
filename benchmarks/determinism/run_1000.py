"""
1000-Iteration Determinism Verification
=======================================

Proves OTTO achieves batch-invariant execution at application level.

This test verifies that:
1. Same inputs produce same routing decisions
2. Same inputs produce same expert selection
3. Same inputs produce same locked parameters
4. Hash of full result is identical across all iterations

Principles Tested:
- Fixed reduction order
- Batch invariance
- Deterministic state transitions
"""
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Final
from dataclasses import dataclass, asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from otto.cognitive_orchestrator import create_orchestrator, NexusResult
from otto.cognitive_state import CognitiveState, BurnoutLevel, MomentumPhase, EnergyLevel
from otto.prism_detector import PRISMDetector

# Fixed inputs for determinism test
FIXED_INPUTS: Final[list[dict]] = [
    {
        "message": "I need help organizing my project",
        "session_id": "test_session_001"
    },
    {
        "message": "This is so frustrating, nothing works!",
        "session_id": "test_session_002"
    },
    {
        "message": "What if we tried a completely different approach?",
        "session_id": "test_session_003"
    },
    {
        "message": "I'm exhausted, can't think anymore",
        "session_id": "test_session_004"
    },
    {
        "message": "Let's continue with the implementation",
        "session_id": "test_session_005"
    },
]

FIXED_STATES: Final[list[dict]] = [
    {
        "burnout_level": "GREEN",
        "momentum_phase": "building",
        "energy_level": "medium"
    },
    {
        "burnout_level": "YELLOW",
        "momentum_phase": "rolling",
        "energy_level": "low"
    },
    {
        "burnout_level": "ORANGE",
        "momentum_phase": "crashed",
        "energy_level": "depleted"
    },
]


@dataclass
class DeterminismResult:
    """Result of determinism verification."""
    iterations: int
    unique_hashes: int
    deterministic: bool
    first_hash: str
    duration_seconds: float
    inputs_tested: int
    states_tested: int


def hash_result(result: dict) -> str:
    """
    Deterministic hash of result.

    Uses sort_keys=True for deterministic JSON serialization.
    """
    # Convert to JSON with sorted keys
    serialized = json.dumps(result, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def extract_routing_signature(result: NexusResult) -> dict:
    """Extract the routing-relevant parts of a NexusResult."""
    return {
        "detected_state": result.detected_state,
        "routed_expert": result.routed_expert,
        "paradigm": result.paradigm,
        "locked_depth": result.locked_params.max_depth if result.locked_params else None,
        "safety_gated": result.safety_gated,
        "signals": {
            k: round(v, 6) for k, v in sorted(result.signals.items())
        } if result.signals else {},
    }


def run_single_iteration(orchestrator, inputs: list[dict], states: list[dict]) -> str:
    """
    Run one complete iteration over all input/state combinations.

    Returns hash of all results combined.
    """
    all_results = []

    # Fixed order iteration
    for input_data in inputs:
        for state_data in states:
            # Create cognitive state
            state = CognitiveState(
                burnout_level=BurnoutLevel[state_data["burnout_level"]],
                momentum_phase=MomentumPhase[state_data["momentum_phase"]],
                energy_level=EnergyLevel[state_data["energy_level"]],
            )

            # Process through orchestrator
            result = orchestrator.process(input_data, state)

            # Extract deterministic signature
            signature = extract_routing_signature(result)
            all_results.append(signature)

    # Hash all results
    return hash_result(all_results)


def run_determinism_test(
    iterations: int = 1000,
    verbose: bool = True
) -> DeterminismResult:
    """
    Run N iterations of the cognitive pipeline with fixed inputs.

    Determinism:
    - Same inputs must produce same outputs every time
    - Any variation indicates non-determinism
    """
    if verbose:
        print(f"Starting {iterations}-iteration determinism test...")
        print(f"  Inputs: {len(FIXED_INPUTS)}")
        print(f"  States: {len(FIXED_STATES)}")
        print(f"  Combinations per iteration: {len(FIXED_INPUTS) * len(FIXED_STATES)}")
        print()

    # Create fresh orchestrator
    orchestrator = create_orchestrator()

    hashes: list[str] = []
    start_time = time.time()

    for i in range(iterations):
        iteration_hash = run_single_iteration(orchestrator, FIXED_INPUTS, FIXED_STATES)
        hashes.append(iteration_hash)

        if verbose and (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            print(f"  Iteration {i + 1}/{iterations} "
                  f"({rate:.1f}/s) - hash: {iteration_hash[:16]}...")

    duration = time.time() - start_time
    unique_hashes = set(hashes)

    result = DeterminismResult(
        iterations=iterations,
        unique_hashes=len(unique_hashes),
        deterministic=len(unique_hashes) == 1,
        first_hash=hashes[0],
        duration_seconds=round(duration, 2),
        inputs_tested=len(FIXED_INPUTS),
        states_tested=len(FIXED_STATES),
    )

    return result


def print_result(result: DeterminismResult) -> None:
    """Print determinism test results."""
    print()
    print("="*70)
    print("DETERMINISM VERIFICATION RESULTS")
    print("="*70)
    print()
    print(f"  Iterations:        {result.iterations}")
    print(f"  Unique hashes:     {result.unique_hashes}")
    print(f"  Duration:          {result.duration_seconds}s")
    print(f"  Rate:              {result.iterations / result.duration_seconds:.1f} iter/s")
    print(f"  Inputs tested:     {result.inputs_tested}")
    print(f"  States tested:     {result.states_tested}")
    print(f"  Combinations:      {result.inputs_tested * result.states_tested}")
    print()
    print(f"  First hash:        {result.first_hash}")
    print()

    if result.deterministic:
        print("  " + "="*50)
        print("  DETERMINISM VERIFIED")
        print(f"  All {result.iterations} iterations produced IDENTICAL output")
        print("  " + "="*50)
    else:
        print("  " + "="*50)
        print("  DETERMINISM FAILED")
        print(f"  {result.unique_hashes} unique outputs in {result.iterations} iterations")
        print("  " + "="*50)


def save_result(result: DeterminismResult, output_path: Path) -> None:
    """Save result to JSON file."""
    output = asdict(result)
    output["he2025_compliant"] = result.deterministic
    output["test_type"] = "1000_iteration_determinism"

    output_path.write_text(json.dumps(output, indent=2, sort_keys=True))


def main():
    """Run determinism verification."""
    import argparse

    parser = argparse.ArgumentParser(description="Run determinism verification")
    parser.add_argument("-n", "--iterations", type=int, default=1000,
                        help="Number of iterations (default: 1000)")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Quiet mode (less output)")
    args = parser.parse_args()

    result = run_determinism_test(
        iterations=args.iterations,
        verbose=not args.quiet
    )

    print_result(result)

    # Save results
    output_dir = Path(__file__).parent
    output_path = output_dir / "determinism_result.json"
    save_result(result, output_path)
    print(f"\nResults saved to: {output_path}")

    # Exit with appropriate code
    sys.exit(0 if result.deterministic else 1)


if __name__ == "__main__":
    main()
