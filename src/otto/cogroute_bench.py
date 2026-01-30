"""
CogRoute-Bench: Cognitive Routing Benchmark Suite
=================================================

A standardized benchmark for evaluating cognitive routing systems.
Measures routing accuracy, latency, determinism, and explainability quality.

Usage:
    python cogroute_bench.py                    # Run full benchmark
    python cogroute_bench.py --category safety  # Run specific category
    python cogroute_bench.py --quick            # Quick 10-task subset

Metrics:
    - Accuracy: Does router select expected expert for each category?
    - Latency: How fast is routing decision?
    - Determinism: Same task → same result across runs?
    - Explainability: Does explanation match actual routing?

Author: Framework Orchestrator Team
Version: 1.0.0
"""

import asyncio
import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

# Import the orchestrator components
from framework_orchestrator import MoERouterAgent, Mycelium, ContextRestorer

logging.basicConfig(level=logging.WARNING)  # Suppress info logs during benchmark
logger = logging.getLogger("CogRouteBench")


@dataclass
class BenchmarkTask:
    """A single benchmark task with expected routing."""
    task: str
    expected_expert: str
    category: str
    difficulty: str = "standard"  # easy, standard, hard, adversarial
    notes: str = ""


@dataclass
class BenchmarkResult:
    """Result from a single benchmark task."""
    task: str
    expected_expert: str
    actual_expert: str
    correct: bool
    latency_ms: float
    category: str
    explanation_quality: float  # 0-1 score
    determinism_verified: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkSummary:
    """Summary of benchmark run."""
    total_tasks: int
    correct: int
    accuracy: float
    avg_latency_ms: float
    determinism_score: float
    explainability_score: float
    by_category: Dict[str, Dict[str, Any]]
    by_expert: Dict[str, Dict[str, Any]]
    failures: List[BenchmarkResult]


class CogRouteBench:
    """Cognitive Routing Benchmark Suite.

    Provides standardized evaluation of routing accuracy across:
    - Safety-critical tasks (should route to Protector)
    - Complexity tasks (should route to Decomposer)
    - Recovery tasks (should route to Restorer)
    - Redirection tasks (should route to Redirector)
    - Acknowledgment tasks (should route to Acknowledger)
    - Exploration tasks (should route to Guide)
    - Execution tasks (should route to Executor)
    - Ambiguous tasks (tests tie-breaking and fallback behavior)
    """

    # Benchmark task categories with expected expert routing
    TASK_CATEGORIES = {
        "safety_critical": {
            "expected_expert": "protector",
            "description": "Tasks indicating user distress, frustration, or overwhelm",
            "tasks": [
                BenchmarkTask(
                    task="I'm so frustrated I want to quit this project",
                    expected_expert="protector",
                    category="safety_critical",
                    difficulty="easy",
                    notes="Clear frustration signal"
                ),
                BenchmarkTask(
                    task="This is overwhelming me, I can't handle all these requirements",
                    expected_expert="protector",
                    category="safety_critical",
                    difficulty="easy",
                    notes="Explicit overwhelm"
                ),
                BenchmarkTask(
                    task="HELP I'M COMPLETELY STUCK AND NOTHING WORKS",
                    expected_expert="protector",
                    category="safety_critical",
                    difficulty="standard",
                    notes="Caps + stuck + help signals"
                ),
                BenchmarkTask(
                    task="I feel like I'm not making any progress and it's making me anxious",
                    expected_expert="protector",
                    category="safety_critical",
                    difficulty="standard",
                    notes="Emotional distress without explicit keywords"
                ),
                BenchmarkTask(
                    task="Everything is broken and I don't know what to do anymore",
                    expected_expert="protector",
                    category="safety_critical",
                    difficulty="hard",
                    notes="Implicit overwhelm"
                ),
            ]
        },
        "complexity": {
            "expected_expert": "decomposer",
            "description": "Tasks that are too complex and need breaking down",
            "tasks": [
                BenchmarkTask(
                    task="I'm stuck on this complex algorithm, can you break it down?",
                    expected_expert="decomposer",
                    category="complexity",
                    difficulty="easy",
                    notes="Explicit break_down request"
                ),
                BenchmarkTask(
                    task="This is too complex, I need to simplify it",
                    expected_expert="decomposer",
                    category="complexity",
                    difficulty="easy",
                    notes="Explicit simplify request"
                ),
                BenchmarkTask(
                    task="There are too many moving parts in this system",
                    expected_expert="decomposer",
                    category="complexity",
                    difficulty="standard",
                    notes="too_many signal"
                ),
                BenchmarkTask(
                    task="I keep getting stuck trying to understand this architecture",
                    expected_expert="decomposer",
                    category="complexity",
                    difficulty="standard",
                    notes="stuck signal"
                ),
                BenchmarkTask(
                    task="The requirements document is 50 pages, where do I even start?",
                    expected_expert="decomposer",
                    category="complexity",
                    difficulty="hard",
                    notes="Implicit complexity, no explicit keywords"
                ),
            ]
        },
        "recovery": {
            "expected_expert": "restorer",
            "description": "Tasks indicating user fatigue or need for recovery",
            "tasks": [
                BenchmarkTask(
                    task="I'm completely depleted, been coding for 12 hours",
                    expected_expert="restorer",
                    category="recovery",
                    difficulty="easy",
                    notes="Explicit depleted"
                ),
                BenchmarkTask(
                    task="I think I'm heading towards burnout",
                    expected_expert="restorer",
                    category="recovery",
                    difficulty="easy",
                    notes="Explicit burnout"
                ),
                BenchmarkTask(
                    task="I'm so tired, but I need to finish this",
                    expected_expert="restorer",
                    category="recovery",
                    difficulty="standard",
                    notes="tired signal"
                ),
                BenchmarkTask(
                    task="Maybe I should take a rest before continuing",
                    expected_expert="restorer",
                    category="recovery",
                    difficulty="standard",
                    notes="rest signal"
                ),
                BenchmarkTask(
                    task="I've been at this all day and my brain is mush",
                    expected_expert="restorer",
                    category="recovery",
                    difficulty="hard",
                    notes="Implicit exhaustion"
                ),
            ]
        },
        "redirection": {
            "expected_expert": "redirector",
            "description": "Tasks indicating user has gone off-topic",
            "tasks": [
                BenchmarkTask(
                    task="I went on a tangent, let me get back to the main task",
                    expected_expert="redirector",
                    category="redirection",
                    difficulty="easy",
                    notes="Explicit tangent"
                ),
                BenchmarkTask(
                    task="I got distracted by something else, where were we?",
                    expected_expert="redirector",
                    category="redirection",
                    difficulty="easy",
                    notes="Explicit distracted"
                ),
                BenchmarkTask(
                    task="Wait, this is off_topic from what we were doing",
                    expected_expert="redirector",
                    category="redirection",
                    difficulty="standard",
                    notes="off_topic signal"
                ),
                BenchmarkTask(
                    task="I've been sidetracked, need to refocus",
                    expected_expert="redirector",
                    category="redirection",
                    difficulty="standard",
                    notes="sidetrack signal"
                ),
            ]
        },
        "acknowledgment": {
            "expected_expert": "acknowledger",
            "description": "Tasks celebrating completion or progress",
            "tasks": [
                BenchmarkTask(
                    task="Done! The feature is complete and working",
                    expected_expert="acknowledger",
                    category="acknowledgment",
                    difficulty="easy",
                    notes="Explicit done + complete"
                ),
                BenchmarkTask(
                    task="We hit a major milestone today!",
                    expected_expert="acknowledger",
                    category="acknowledgment",
                    difficulty="easy",
                    notes="Explicit milestone"
                ),
                BenchmarkTask(
                    task="That's a win, the tests are all passing now",
                    expected_expert="acknowledger",
                    category="acknowledgment",
                    difficulty="standard",
                    notes="win signal"
                ),
                BenchmarkTask(
                    task="Finally finished the refactoring",
                    expected_expert="acknowledger",
                    category="acknowledgment",
                    difficulty="standard",
                    notes="finished signal"
                ),
            ]
        },
        "exploration": {
            "expected_expert": "guide",
            "description": "Tasks involving exploration and learning",
            "tasks": [
                BenchmarkTask(
                    task="I'm exploring different approaches to this problem",
                    expected_expert="guide",
                    category="exploration",
                    difficulty="easy",
                    notes="Explicit exploring"
                ),
                BenchmarkTask(
                    task="What if we tried a completely different architecture?",
                    expected_expert="guide",
                    category="exploration",
                    difficulty="easy",
                    notes="what_if signal"
                ),
                BenchmarkTask(
                    task="I'm curious about how this framework handles state",
                    expected_expert="guide",
                    category="exploration",
                    difficulty="standard",
                    notes="curious signal"
                ),
                BenchmarkTask(
                    task="I want to learn more about the underlying algorithms",
                    expected_expert="guide",
                    category="exploration",
                    difficulty="standard",
                    notes="learn signal"
                ),
                BenchmarkTask(
                    task="Help me understand why this pattern works",
                    expected_expert="guide",
                    category="exploration",
                    difficulty="standard",
                    notes="understand signal"
                ),
            ]
        },
        "execution": {
            "expected_expert": "executor",
            "description": "Tasks requiring direct implementation",
            "tasks": [
                BenchmarkTask(
                    task="Implement the login feature with OAuth",
                    expected_expert="executor",
                    category="execution",
                    difficulty="easy",
                    notes="Explicit implement"
                ),
                BenchmarkTask(
                    task="Write the code for the API endpoint",
                    expected_expert="executor",
                    category="execution",
                    difficulty="easy",
                    notes="code signal"
                ),
                BenchmarkTask(
                    task="Execute the database migration script",
                    expected_expert="executor",
                    category="execution",
                    difficulty="standard",
                    notes="execute signal"
                ),
                BenchmarkTask(
                    task="Build the user dashboard component",
                    expected_expert="executor",
                    category="execution",
                    difficulty="standard",
                    notes="build signal"
                ),
                BenchmarkTask(
                    task="Create a new service for handling payments",
                    expected_expert="executor",
                    category="execution",
                    difficulty="standard",
                    notes="create signal"
                ),
                BenchmarkTask(
                    task="Do the thing we discussed",
                    expected_expert="executor",
                    category="execution",
                    difficulty="hard",
                    notes="do signal (minimal)"
                ),
            ]
        },
        "ambiguous": {
            "expected_expert": "protector",  # Safety floors should make protector win ties
            "description": "Tasks with no clear signals - tests fallback behavior",
            "tasks": [
                BenchmarkTask(
                    task="Hello",
                    expected_expert="protector",
                    category="ambiguous",
                    difficulty="adversarial",
                    notes="No signals - safety floor should win"
                ),
                BenchmarkTask(
                    task="What's the weather like?",
                    expected_expert="protector",
                    category="ambiguous",
                    difficulty="adversarial",
                    notes="Off-domain question"
                ),
                BenchmarkTask(
                    task="Thanks",
                    expected_expert="protector",
                    category="ambiguous",
                    difficulty="adversarial",
                    notes="Minimal input"
                ),
            ]
        }
    }

    def __init__(self, router: MoERouterAgent = None):
        """Initialize benchmark with optional custom router."""
        self.router = router or MoERouterAgent()
        self.results: List[BenchmarkResult] = []

    def get_all_tasks(self) -> List[BenchmarkTask]:
        """Get all benchmark tasks across categories."""
        tasks = []
        for category_data in self.TASK_CATEGORIES.values():
            tasks.extend(category_data["tasks"])
        return tasks

    def get_tasks_by_category(self, category: str) -> List[BenchmarkTask]:
        """Get tasks for a specific category."""
        if category not in self.TASK_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        return self.TASK_CATEGORIES[category]["tasks"]

    async def run_single_task(self, task: BenchmarkTask, verify_determinism: bool = True) -> BenchmarkResult:
        """Run benchmark on a single task."""
        context = {"seed": 42}

        # Measure latency
        start_time = time.perf_counter()
        result = await self.router.execute(task.task, context)
        latency_ms = (time.perf_counter() - start_time) * 1000

        actual_expert = result["selected_expert"]
        correct = actual_expert == task.expected_expert

        # Verify determinism (run twice, compare)
        determinism_verified = True
        if verify_determinism:
            result2 = await self.router.execute(task.task, context)
            determinism_verified = (
                result["selected_expert"] == result2["selected_expert"] and
                result["expert_hash"] == result2["expert_hash"]
            )

        # Score explainability quality
        explanation = result.get("explainability", {})
        explain_quality = self._score_explanation_quality(
            explanation, actual_expert, task.expected_expert, correct
        )

        return BenchmarkResult(
            task=task.task,
            expected_expert=task.expected_expert,
            actual_expert=actual_expert,
            correct=correct,
            latency_ms=latency_ms,
            category=task.category,
            explanation_quality=explain_quality,
            determinism_verified=determinism_verified,
            details={
                "difficulty": task.difficulty,
                "notes": task.notes,
                "bounded_scores": result.get("bounded_scores", {}),
                "matched_triggers": explanation.get("winner_triggers", []),
                "selection_rationale": explanation.get("selection_rationale", ""),
                "explain_human": explanation.get("explain_human", "")
            }
        )

    def _score_explanation_quality(self, explanation: Dict, actual: str,
                                   expected: str, correct: bool) -> float:
        """Score the quality of the routing explanation (0-1)."""
        score = 0.0

        # Has matched triggers? (+0.25)
        if explanation.get("winner_triggers"):
            score += 0.25

        # Has selection rationale? (+0.25)
        if explanation.get("selection_rationale"):
            score += 0.25

        # Has human explanation? (+0.25)
        if explanation.get("explain_human"):
            score += 0.25

        # Explanation consistent with result? (+0.25)
        if correct:
            score += 0.25
        elif explanation.get("selection_rationale"):
            # Partial credit if explanation makes sense even if unexpected
            score += 0.10

        return min(score, 1.0)

    async def run_benchmark(self, categories: List[str] = None,
                           quick: bool = False) -> BenchmarkSummary:
        """Run full benchmark suite.

        Args:
            categories: Optional list of categories to run (default: all)
            quick: If True, run only 2 tasks per category

        Returns:
            BenchmarkSummary with all metrics
        """
        self.results = []

        # Collect tasks
        tasks = []
        if categories:
            for cat in categories:
                tasks.extend(self.get_tasks_by_category(cat))
        else:
            tasks = self.get_all_tasks()

        # Quick mode: subset
        if quick:
            quick_tasks = []
            for cat_name in self.TASK_CATEGORIES.keys():
                cat_tasks = [t for t in tasks if t.category == cat_name]
                quick_tasks.extend(cat_tasks[:2])
            tasks = quick_tasks

        # Run all tasks
        for task in tasks:
            result = await self.run_single_task(task)
            self.results.append(result)

        return self._compute_summary()

    def _compute_summary(self) -> BenchmarkSummary:
        """Compute summary statistics from results."""
        if not self.results:
            return BenchmarkSummary(
                total_tasks=0, correct=0, accuracy=0.0,
                avg_latency_ms=0.0, determinism_score=0.0,
                explainability_score=0.0, by_category={},
                by_expert={}, failures=[]
            )

        total = len(self.results)
        correct = sum(1 for r in self.results if r.correct)
        accuracy = correct / total

        avg_latency = sum(r.latency_ms for r in self.results) / total
        determinism_score = sum(1 for r in self.results if r.determinism_verified) / total
        explainability_score = sum(r.explanation_quality for r in self.results) / total

        # By category
        by_category = {}
        for cat_name in self.TASK_CATEGORIES.keys():
            cat_results = [r for r in self.results if r.category == cat_name]
            if cat_results:
                cat_correct = sum(1 for r in cat_results if r.correct)
                by_category[cat_name] = {
                    "total": len(cat_results),
                    "correct": cat_correct,
                    "accuracy": cat_correct / len(cat_results),
                    "avg_latency_ms": sum(r.latency_ms for r in cat_results) / len(cat_results)
                }

        # By expert
        by_expert = {}
        for expert in ["protector", "decomposer", "restorer", "redirector",
                       "acknowledger", "guide", "executor"]:
            exp_results = [r for r in self.results if r.expected_expert == expert]
            if exp_results:
                exp_correct = sum(1 for r in exp_results if r.correct)
                by_expert[expert] = {
                    "expected": len(exp_results),
                    "correct": exp_correct,
                    "accuracy": exp_correct / len(exp_results)
                }

        # Failures
        failures = [r for r in self.results if not r.correct]

        return BenchmarkSummary(
            total_tasks=total,
            correct=correct,
            accuracy=accuracy,
            avg_latency_ms=avg_latency,
            determinism_score=determinism_score,
            explainability_score=explainability_score,
            by_category=by_category,
            by_expert=by_expert,
            failures=failures
        )

    def print_summary(self, summary: BenchmarkSummary) -> None:
        """Print formatted benchmark summary."""
        print("\n" + "=" * 60)
        print("CogRoute-Bench Results")
        print("=" * 60)

        print(f"\nOverall Metrics:")
        print(f"  Total Tasks:        {summary.total_tasks}")
        print(f"  Correct:            {summary.correct}")
        print(f"  Accuracy:           {summary.accuracy:.1%}")
        print(f"  Avg Latency:        {summary.avg_latency_ms:.2f}ms")
        print(f"  Determinism:        {summary.determinism_score:.1%}")
        print(f"  Explainability:     {summary.explainability_score:.1%}")

        print(f"\nBy Category:")
        for cat, stats in summary.by_category.items():
            print(f"  {cat:20} {stats['correct']}/{stats['total']} ({stats['accuracy']:.0%})")

        print(f"\nBy Expected Expert:")
        for expert, stats in summary.by_expert.items():
            print(f"  {expert:15} {stats['correct']}/{stats['expected']} ({stats['accuracy']:.0%})")

        if summary.failures:
            print(f"\nFailures ({len(summary.failures)}):")
            for f in summary.failures[:5]:  # Show first 5
                print(f"  - [{f.category}] Expected {f.expected_expert}, got {f.actual_expert}")
                print(f"    Task: {f.task[:60]}...")
                print(f"    Triggers: {f.details.get('matched_triggers', [])}")

        print("\n" + "=" * 60)

    def export_results(self, path: Path) -> None:
        """Export results to JSON file."""
        data = {
            "timestamp": time.time(),
            "results": [
                {
                    "task": r.task,
                    "expected": r.expected_expert,
                    "actual": r.actual_expert,
                    "correct": r.correct,
                    "latency_ms": r.latency_ms,
                    "category": r.category,
                    "explanation_quality": r.explanation_quality,
                    "determinism_verified": r.determinism_verified,
                    "details": r.details
                }
                for r in self.results
            ]
        }
        path.write_text(json.dumps(data, indent=2, sort_keys=True))
        print(f"Results exported to: {path}")


async def main():
    """Run benchmark from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="CogRoute-Bench: Cognitive Routing Benchmark")
    parser.add_argument("--category", type=str, help="Run specific category only")
    parser.add_argument("--quick", action="store_true", help="Quick run (2 tasks per category)")
    parser.add_argument("--export", type=str, help="Export results to JSON file")
    args = parser.parse_args()

    bench = CogRouteBench()

    categories = [args.category] if args.category else None
    summary = await bench.run_benchmark(categories=categories, quick=args.quick)

    bench.print_summary(summary)

    if args.export:
        bench.export_results(Path(args.export))

    # Return exit code based on accuracy
    return 0 if summary.accuracy >= 0.8 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
