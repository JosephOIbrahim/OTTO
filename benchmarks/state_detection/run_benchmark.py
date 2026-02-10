"""
Deterministic State Detection Benchmark Runner
====================================================

Measures PRISM detector accuracy against labeled dataset.

Determinism:
- Sorted key iteration throughout
- Deterministic metric aggregation (Kahan summation for floats)
- Fixed evaluation order
- Reproducible results
"""
import json
import sys
from pathlib import Path
from typing import Final
from dataclasses import dataclass, field
from collections import defaultdict

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from otto.prism_detector import PRISMDetector, SignalVector


# Constants
_DETERMINISM_SEED: Final[int] = 0xCAFEBABE


@dataclass
class ClassMetrics:
    """Metrics for a single class/state."""
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        if denom == 0:
            return 0.0
        return round(self.true_positives / denom, 6)

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        if denom == 0:
            return 0.0
        return round(self.true_positives / denom, 6)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        if p + r == 0:
            return 0.0
        return round(2 * p * r / (p + r), 6)


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""
    dataset_path: str
    sample_count: int
    accuracy: float
    per_class_metrics: dict[str, dict[str, float]]
    confusion_matrix: dict[str, dict[str, int]]
    macro_precision: float
    macro_recall: float
    macro_f1: float
    errors: list[dict] = field(default_factory=list)


def kahan_sum(values: list[float]) -> float:
    """
    Batch-invariant summation using Kahan algorithm.

    Reduces floating-point accumulation error for deterministic results.
    """
    # Sort for deterministic order
    sorted_values = sorted(values)

    total = 0.0
    compensation = 0.0

    for v in sorted_values:
        y = v - compensation
        t = total + y
        compensation = (t - total) - y
        total = t

    return total


def load_dataset(path: Path) -> list[dict]:
    """Load dataset from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return data["samples"]


def detect_state(detector: PRISMDetector, message: str) -> str:
    """
    Detect state from message using PRISM detector.

    FIXED evaluation order matching PRISM priority:
    0. CAPS detection (indicates frustration/anger)
    1. EMOTIONAL (frustrated, overwhelmed, stuck) - highest priority
    2. ENERGY (depleted) - maps to depleted state
    3. MODE (exploring, focused) - maps to exploring/focused
    4. Default to focused

    Returns the primary detected state.
    """
    # 0. Check for ALL CAPS (indicates frustration)
    if detector.detect_caps_anger(message):
        return "frustrated"

    signals: SignalVector = detector.detect(message)

    # Detection threshold - lowered from 0.5 to 0.3
    # Single keyword match gives 0.33, so we need threshold < 0.33
    DETECTION_THRESHOLD: Final[float] = 0.3

    # 1. Check EMOTIONAL signals first (highest priority)
    # Maps PRISM emotional signals to benchmark states
    emotional_state_map = {
        "frustrated": "frustrated",
        "overwhelmed": "overwhelmed",
        "stuck": "stuck",
        "angry": "frustrated",  # angry maps to frustrated
        "anxious": "overwhelmed",  # anxious maps to overwhelmed
    }

    if signals.emotional:
        # Find highest emotional signal using sorted iteration
        max_score = 0.0
        detected_emotion = None
        for emotion in sorted(signals.emotional.keys()):
            score = signals.emotional[emotion]
            if score > max_score and score >= DETECTION_THRESHOLD:
                max_score = score
                detected_emotion = emotion

        if detected_emotion and detected_emotion in emotional_state_map:
            return emotional_state_map[detected_emotion]

    # 2. Check ENERGY signals (depleted is here, not in emotional)
    if signals.energy:
        for energy_state in sorted(signals.energy.keys()):
            if signals.energy[energy_state] >= DETECTION_THRESHOLD:
                if energy_state == "depleted":
                    return "depleted"
                elif energy_state == "low":
                    return "depleted"  # low energy also maps to depleted

    # 3. Check MODE signals
    if signals.mode:
        for mode in sorted(signals.mode.keys()):
            if signals.mode[mode] >= DETECTION_THRESHOLD:
                if mode == "exploring":
                    return "exploring"
                elif mode == "focused":
                    return "focused"

    # 4. Default to focused (per CLAUDE.md: assume focused unless signals indicate otherwise)
    return "focused"


def run_benchmark(dataset_path: Path) -> BenchmarkResult:
    """
    Run benchmark on dataset.

    Determinism:
    - Sorted iteration over samples and states
    - Kahan summation for aggregations
    - Deterministic evaluation order
    """
    dataset = load_dataset(dataset_path)
    detector = PRISMDetector()

    # Initialize metrics with sorted state keys
    all_states = sorted(set(s["annotated_state"] for s in dataset))
    metrics: dict[str, ClassMetrics] = {state: ClassMetrics() for state in all_states}

    # Confusion matrix: actual -> predicted -> count
    confusion: dict[str, dict[str, int]] = {
        actual: {pred: 0 for pred in all_states}
        for actual in all_states
    }

    errors: list[dict] = []
    correct = 0
    total = len(dataset)

    # Process samples in sorted order by ID for determinism
    sorted_samples = sorted(dataset, key=lambda s: s["id"])

    for sample in sorted_samples:
        message = sample["message"]
        actual = sample["annotated_state"]

        predicted = detect_state(detector, message)

        # Update confusion matrix
        confusion[actual][predicted] += 1

        if predicted == actual:
            correct += 1
            metrics[actual].true_positives += 1
        else:
            metrics[actual].false_negatives += 1
            metrics[predicted].false_positives += 1
            errors.append({
                "id": sample["id"],
                "message": message[:100],
                "actual": actual,
                "predicted": predicted,
            })

    # Calculate aggregate metrics using Kahan summation
    precisions = [metrics[s].precision for s in all_states]
    recalls = [metrics[s].recall for s in all_states]
    f1s = [metrics[s].f1 for s in all_states]

    n_classes = len(all_states)
    macro_precision = round(kahan_sum(precisions) / n_classes, 6)
    macro_recall = round(kahan_sum(recalls) / n_classes, 6)
    macro_f1 = round(kahan_sum(f1s) / n_classes, 6)

    # Build per-class metrics dict with sorted keys
    per_class = {}
    for state in all_states:
        per_class[state] = {
            "precision": metrics[state].precision,
            "recall": metrics[state].recall,
            "f1": metrics[state].f1,
            "support": metrics[state].true_positives + metrics[state].false_negatives,
        }

    return BenchmarkResult(
        dataset_path=str(dataset_path),
        sample_count=total,
        accuracy=round(correct / total, 6) if total > 0 else 0.0,
        per_class_metrics=per_class,
        confusion_matrix=confusion,
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
        errors=errors[:20],  # Limit error examples
    )


def print_results(result: BenchmarkResult) -> None:
    """Print benchmark results in formatted output."""
    print("\n" + "="*70)
    print("STATE DETECTION BENCHMARK RESULTS")
    print("="*70)
    print(f"Dataset: {result.dataset_path}")
    print(f"Samples: {result.sample_count}")
    print(f"Determinism: Yes (sorted iteration, Kahan summation)")
    print()

    # Overall metrics
    print("OVERALL METRICS")
    print("-"*40)
    print(f"  Accuracy:        {result.accuracy:.4f}")
    print(f"  Macro Precision: {result.macro_precision:.4f}")
    print(f"  Macro Recall:    {result.macro_recall:.4f}")
    print(f"  Macro F1:        {result.macro_f1:.4f}")
    print()

    # Per-class metrics
    print("PER-CLASS METRICS")
    print("-"*70)
    print(f"{'State':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-"*70)

    for state in sorted(result.per_class_metrics.keys()):
        m = result.per_class_metrics[state]
        print(f"{state:<15} {m['precision']:>10.4f} {m['recall']:>10.4f} {m['f1']:>10.4f} {m['support']:>10}")
    print()

    # Confusion matrix
    print("CONFUSION MATRIX")
    print("-"*70)
    states = sorted(result.confusion_matrix.keys())

    # Header
    header = "Actual\\Pred".ljust(15)
    for s in states:
        header += s[:8].rjust(10)
    print(header)
    print("-"*70)

    # Rows
    for actual in states:
        row = actual.ljust(15)
        for pred in states:
            count = result.confusion_matrix[actual][pred]
            row += str(count).rjust(10)
        print(row)
    print()

    # Sample errors
    if result.errors:
        print("SAMPLE ERRORS (first 10)")
        print("-"*70)
        for err in result.errors[:10]:
            print(f"  [{err['id']}] {err['actual']} -> {err['predicted']}")
            print(f"    \"{err['message'][:60]}...\"")
        print()


def save_results(result: BenchmarkResult, output_path: Path) -> None:
    """Save results to JSON file."""
    output = {
        "dataset_path": result.dataset_path,
        "sample_count": result.sample_count,
        "accuracy": result.accuracy,
        "macro_precision": result.macro_precision,
        "macro_recall": result.macro_recall,
        "macro_f1": result.macro_f1,
        "per_class_metrics": result.per_class_metrics,
        "confusion_matrix": result.confusion_matrix,
        "error_count": len(result.errors),
        "sample_errors": result.errors,
        "deterministic": True,
    }

    output_path.write_text(json.dumps(output, indent=2, sort_keys=True))


def main():
    """
    Run benchmark on available datasets.

    Usage:
        python run_benchmark.py                    # Run on all datasets
        python run_benchmark.py dataset.json      # Run on specific file
    """
    benchmark_dir = Path(__file__).parent

    # Check for command-line argument
    if len(sys.argv) > 1:
        dataset_path = Path(sys.argv[1])
        if not dataset_path.exists():
            # Try relative to benchmark dir
            dataset_path = benchmark_dir / sys.argv[1]

        if not dataset_path.exists():
            print(f"Dataset not found: {sys.argv[1]}")
            return

        dataset_files = [dataset_path]
    else:
        # Find all dataset files (exclude .results.json files)
        dataset_files = sorted([
            f for f in benchmark_dir.glob("*dataset*.json")
            if ".results." not in f.name
        ])

    if not dataset_files:
        print("No dataset files found. Run generate_synthetic.py first.")
        print("  python generate_synthetic.py")
        return

    for dataset_path in dataset_files:
        print(f"\nRunning benchmark on: {dataset_path.name}")

        result = run_benchmark(dataset_path)
        print_results(result)

        # Save results
        results_path = dataset_path.with_suffix(".results.json")
        save_results(result, results_path)
        print(f"Results saved to: {results_path.name}")


if __name__ == "__main__":
    main()
