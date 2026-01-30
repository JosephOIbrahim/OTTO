"""
Synthesis Agent - Worker Agent
==============================

A worker agent that combines outputs from multiple agents into cohesive results.

This agent:
- Aggregates routing agent metadata
- Combines worker agent outputs
- Resolves conflicts using LIVRPS priority
- Produces final actionable synthesis

Synthesis Modes:
- COMBINE: Merge outputs into unified response
- RANK: Rank and prioritize multiple outputs
- RESOLVE: Resolve conflicts between outputs
- SUMMARIZE: Condense multiple outputs into summary

ThinkingMachines [He2025] Compliance:
- Fixed combination order (LIVRPS)
- Deterministic conflict resolution
- Reproducible synthesis
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
import logging

from .cognitive_state import CognitiveState, BurnoutLevel, CognitiveMode

logger = logging.getLogger(__name__)


# =============================================================================
# Synthesis Modes
# =============================================================================

class SynthesisMode(Enum):
    """Modes of synthesis operation."""
    COMBINE = "combine"        # Merge into unified response
    RANK = "rank"              # Rank and prioritize
    RESOLVE = "resolve"        # Resolve conflicts
    SUMMARIZE = "summarize"    # Condense into summary


# =============================================================================
# LIVRPS Priority for Conflict Resolution
# =============================================================================

# Agent categories for LIVRPS-style priority resolution
AGENT_PRIORITY = {
    # LOCAL (session state - highest priority)
    "cognitive_state": 1,

    # INHERITS (context from parent)
    "echo_curator": 2,

    # VARIANTSETS (mode variants)
    "moe_router": 3,

    # REFERENCES (calibration)
    "self_reflector": 4,

    # PAYLOADS (domain knowledge)
    "domain_intelligence": 5,
    "research_agent": 5,

    # SPECIALIZES (foundational - lowest override priority but always consulted)
    "determinism_guard": 6,
    "world_modeler": 6,
    "code_generator": 7,
    "synthesis_agent": 7,  # Self - lowest priority
}


# =============================================================================
# Synthesis Result
# =============================================================================

@dataclass
class SynthesisResult:
    """Result of synthesis operation."""
    mode: SynthesisMode
    combined_output: Dict[str, Any] = field(default_factory=dict)
    rankings: List[Tuple[str, float]] = field(default_factory=list)
    conflicts_resolved: int = 0
    agents_synthesized: int = 0
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    checksum: str = ""

    # Confidence and coherence metrics
    coherence_score: float = 0.0  # How well outputs align
    confidence_score: float = 0.0  # Overall confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "combined_output": self.combined_output,
            "rankings": self.rankings,
            "conflicts_resolved": self.conflicts_resolved,
            "agents_synthesized": self.agents_synthesized,
            "summary": self.summary,
            "recommendations": self.recommendations,
            "coherence_score": self.coherence_score,
            "confidence_score": self.confidence_score,
            "execution_time_ms": self.execution_time_ms,
            "checksum": self.checksum
        }


# =============================================================================
# Synthesis Agent
# =============================================================================

class SynthesisAgent:
    """
    Worker agent that synthesizes outputs from multiple agents.

    Produces real, actionable synthesis - not just metadata.
    """

    def __init__(self):
        """Initialize synthesis agent."""
        self.name = "synthesis_agent"
        self.logger = logging.getLogger(f"Agent.{self.name}")

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute synthesis operation.

        Args:
            task: Synthesis task description
            context: Execution context with agent_results to synthesize

        Returns:
            Dict containing synthesis results
        """
        import time
        start_time = time.time()

        self.logger.info(f"Synthesis agent executing: {task[:100]}...")

        # Get agent results from context
        agent_results = context.get("agent_results", {})

        if not agent_results:
            return {
                "error": "No agent results to synthesize",
                "agents_synthesized": 0
            }

        # Detect synthesis mode
        mode = self._detect_mode(task, agent_results)

        # Execute appropriate synthesis
        if mode == SynthesisMode.COMBINE:
            result = await self._combine(agent_results, context)
        elif mode == SynthesisMode.RANK:
            result = await self._rank(agent_results, context)
        elif mode == SynthesisMode.RESOLVE:
            result = await self._resolve(agent_results, context)
        else:  # SUMMARIZE
            result = await self._summarize(agent_results, context)

        result.mode = mode
        result.agents_synthesized = len(agent_results)
        result.execution_time_ms = (time.time() - start_time) * 1000
        result.checksum = self._compute_checksum(result)

        self.logger.info(
            f"Synthesis complete: {result.agents_synthesized} agents, "
            f"coherence={result.coherence_score:.2f}"
        )

        return result.to_dict()

    def _detect_mode(self, task: str, agent_results: Dict) -> SynthesisMode:
        """Detect synthesis mode from task."""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["conflict", "resolve", "disagree", "differ"]):
            return SynthesisMode.RESOLVE

        if any(kw in task_lower for kw in ["rank", "priority", "best", "order", "top"]):
            return SynthesisMode.RANK

        if any(kw in task_lower for kw in ["summary", "brief", "short", "condense"]):
            return SynthesisMode.SUMMARIZE

        # Default to combine
        return SynthesisMode.COMBINE

    async def _combine(self, agent_results: Dict[str, Any],
                       context: Dict[str, Any]) -> SynthesisResult:
        """
        Combine agent outputs into unified response.

        Uses LIVRPS priority for overlay order.
        """
        result = SynthesisResult(mode=SynthesisMode.COMBINE)
        combined = {}

        # Sort agents by priority (lowest number = highest priority)
        sorted_agents = sorted(
            agent_results.keys(),
            key=lambda a: AGENT_PRIORITY.get(a, 99)
        )

        # Combine in priority order (higher priority overwrites)
        for agent_name in reversed(sorted_agents):  # Start with lowest priority
            agent_output = agent_results[agent_name]

            # Handle AgentResult objects vs dicts
            if hasattr(agent_output, 'output'):
                output = agent_output.output
            elif isinstance(agent_output, dict):
                output = agent_output.get('output', agent_output)
            else:
                continue

            if isinstance(output, dict):
                # Merge output into combined
                for key, value in output.items():
                    if key not in combined:
                        combined[key] = value
                    elif isinstance(combined[key], dict) and isinstance(value, dict):
                        # Deep merge for dicts
                        combined[key].update(value)
                    elif isinstance(combined[key], list) and isinstance(value, list):
                        # Extend lists
                        combined[key].extend(value)
                    else:
                        # Higher priority wins (don't overwrite)
                        pass

        result.combined_output = combined

        # Calculate coherence
        result.coherence_score = self._calculate_coherence(agent_results)
        result.confidence_score = self._calculate_confidence(agent_results)

        # Generate summary
        result.summary = self._generate_combine_summary(agent_results, combined)
        result.recommendations = self._extract_recommendations(combined)

        return result

    async def _rank(self, agent_results: Dict[str, Any],
                    context: Dict[str, Any]) -> SynthesisResult:
        """
        Rank agent outputs by relevance and quality.
        """
        result = SynthesisResult(mode=SynthesisMode.RANK)
        rankings = []

        for agent_name, agent_output in agent_results.items():
            # Calculate score based on multiple factors
            score = 0.0

            # Factor 1: Priority (higher priority = higher score)
            priority = AGENT_PRIORITY.get(agent_name, 99)
            score += (10 - min(priority, 10)) / 10 * 0.3  # 30% weight

            # Factor 2: Execution status
            status = "completed"
            if hasattr(agent_output, 'status'):
                status = agent_output.status.value if hasattr(agent_output.status, 'value') else str(agent_output.status)
            elif isinstance(agent_output, dict):
                status = agent_output.get('status', 'completed')

            if status == "completed":
                score += 0.3  # 30% weight
            elif status == "degraded":
                score += 0.15

            # Factor 3: Output richness
            output = agent_output.output if hasattr(agent_output, 'output') else agent_output.get('output', {})
            if isinstance(output, dict):
                richness = min(len(output) / 10, 1.0)
                score += richness * 0.4  # 40% weight

            rankings.append((agent_name, round(score, 3)))

        # Sort by score descending
        rankings.sort(key=lambda x: x[1], reverse=True)
        result.rankings = rankings

        # Combined output from top-ranked agent
        if rankings:
            top_agent = rankings[0][0]
            top_output = agent_results[top_agent]
            result.combined_output = top_output.output if hasattr(top_output, 'output') else top_output.get('output', {})

        result.summary = f"Ranked {len(rankings)} agents. Top: {rankings[0][0] if rankings else 'none'}"
        result.coherence_score = self._calculate_coherence(agent_results)
        result.confidence_score = rankings[0][1] if rankings else 0.0

        return result

    async def _resolve(self, agent_results: Dict[str, Any],
                       context: Dict[str, Any]) -> SynthesisResult:
        """
        Resolve conflicts between agent outputs using LIVRPS priority.
        """
        result = SynthesisResult(mode=SynthesisMode.RESOLVE)
        conflicts_found = []
        resolved = {}

        # Collect all keys across all outputs
        all_keys = set()
        agent_outputs = {}

        for agent_name, agent_output in agent_results.items():
            output = agent_output.output if hasattr(agent_output, 'output') else agent_output.get('output', {})
            if isinstance(output, dict):
                agent_outputs[agent_name] = output
                all_keys.update(output.keys())

        # Check each key for conflicts
        for key in all_keys:
            values = {}
            for agent_name, output in agent_outputs.items():
                if key in output:
                    value = output[key]
                    # Normalize for comparison
                    value_str = json.dumps(value, sort_keys=True, default=str) if isinstance(value, (dict, list)) else str(value)
                    values[agent_name] = (value, value_str)

            if len(values) > 1:
                # Check if values actually differ
                unique_values = set(v[1] for v in values.values())
                if len(unique_values) > 1:
                    # Conflict detected - resolve by priority
                    conflicts_found.append({
                        "key": key,
                        "agents": list(values.keys()),
                        "values": {a: v[0] for a, v in values.items()}
                    })

                    # Resolve: highest priority wins
                    winner = min(values.keys(), key=lambda a: AGENT_PRIORITY.get(a, 99))
                    resolved[key] = values[winner][0]
                else:
                    # No conflict - values are same
                    resolved[key] = list(values.values())[0][0]
            elif values:
                # Only one agent has this key
                resolved[key] = list(values.values())[0][0]

        result.combined_output = resolved
        result.conflicts_resolved = len(conflicts_found)

        # Generate conflict summary
        if conflicts_found:
            conflict_keys = [c["key"] for c in conflicts_found[:5]]
            result.summary = f"Resolved {len(conflicts_found)} conflicts. Keys: {', '.join(conflict_keys)}"
            result.recommendations = [
                f"Conflict on '{c['key']}' - resolved to {AGENT_PRIORITY.get(min(c['agents'], key=lambda a: AGENT_PRIORITY.get(a, 99)), 'unknown')} priority"
                for c in conflicts_found[:3]
            ]
        else:
            result.summary = "No conflicts detected - agents are in agreement"

        result.coherence_score = 1.0 - (len(conflicts_found) / max(len(all_keys), 1))
        result.confidence_score = self._calculate_confidence(agent_results)

        return result

    async def _summarize(self, agent_results: Dict[str, Any],
                         context: Dict[str, Any]) -> SynthesisResult:
        """
        Summarize agent outputs into concise overview.
        """
        result = SynthesisResult(mode=SynthesisMode.SUMMARIZE)

        summaries = []
        key_findings = []

        for agent_name, agent_output in agent_results.items():
            output = agent_output.output if hasattr(agent_output, 'output') else agent_output.get('output', {})
            status = "completed"
            if hasattr(agent_output, 'status'):
                status = agent_output.status.value if hasattr(agent_output.status, 'value') else str(agent_output.status)

            # Extract key information
            summary_parts = [f"{agent_name}: {status}"]

            if isinstance(output, dict):
                # Extract notable keys
                for key in ['selected_expert', 'primary_domain', 'active_mode', 'summary']:
                    if key in output:
                        summary_parts.append(f"  {key}={output[key]}")
                        key_findings.append(f"{agent_name}.{key}: {output[key]}")

            summaries.append(" | ".join(summary_parts))

        result.combined_output = {
            "agent_summaries": summaries,
            "key_findings": key_findings[:10]
        }

        result.summary = f"Summarized {len(agent_results)} agents. " + \
                         f"Key findings: {len(key_findings)}"
        result.recommendations = key_findings[:5]
        result.coherence_score = self._calculate_coherence(agent_results)
        result.confidence_score = self._calculate_confidence(agent_results)

        return result

    def _calculate_coherence(self, agent_results: Dict[str, Any]) -> float:
        """
        Calculate coherence score across agent outputs.

        Higher score = more agreement between agents.
        """
        if len(agent_results) <= 1:
            return 1.0

        # Check completion status agreement
        statuses = []
        for agent_output in agent_results.values():
            if hasattr(agent_output, 'status'):
                statuses.append(agent_output.status.value if hasattr(agent_output.status, 'value') else str(agent_output.status))
            elif isinstance(agent_output, dict):
                statuses.append(agent_output.get('status', 'unknown'))

        # Status coherence
        status_coherence = statuses.count('completed') / len(statuses) if statuses else 0.5

        return round(status_coherence, 3)

    def _calculate_confidence(self, agent_results: Dict[str, Any]) -> float:
        """
        Calculate overall confidence score.
        """
        if not agent_results:
            return 0.0

        scores = []
        for agent_output in agent_results.values():
            # Check for explicit confidence
            output = agent_output.output if hasattr(agent_output, 'output') else agent_output.get('output', {})
            if isinstance(output, dict):
                if 'confidence' in output:
                    scores.append(output['confidence'])
                elif 'self_confidence' in output:
                    scores.append(output['self_confidence'])
                elif 'coherence_score' in output:
                    scores.append(output['coherence_score'])

            # Factor in status
            status = "completed"
            if hasattr(agent_output, 'status'):
                status = agent_output.status.value if hasattr(agent_output.status, 'value') else str(agent_output.status)
            elif isinstance(agent_output, dict):
                status = agent_output.get('status', 'unknown')

            if status == 'completed':
                scores.append(1.0)
            elif status == 'degraded':
                scores.append(0.5)
            else:
                scores.append(0.0)

        return round(sum(scores) / len(scores), 3) if scores else 0.5

    def _generate_combine_summary(self, agent_results: Dict, combined: Dict) -> str:
        """Generate summary for combine operation."""
        completed = sum(1 for r in agent_results.values()
                        if (hasattr(r, 'status') and str(r.status.value) == 'completed') or
                        (isinstance(r, dict) and r.get('status') == 'completed'))

        return f"Combined {len(agent_results)} agents ({completed} completed). " + \
               f"Output keys: {len(combined)}"

    def _extract_recommendations(self, combined: Dict) -> List[str]:
        """Extract recommendations from combined output."""
        recs = []

        # Look for recommendation-like keys
        rec_keys = ['recommendations', 'suggestions', 'next_steps', 'actions']
        for key in rec_keys:
            if key in combined:
                value = combined[key]
                if isinstance(value, list):
                    recs.extend(str(v) for v in value[:3])
                elif isinstance(value, str):
                    recs.append(value)

        return recs[:5]

    def _compute_checksum(self, result: SynthesisResult) -> str:
        """Compute deterministic checksum."""
        result_str = json.dumps(result.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(result_str.encode()).hexdigest()[:16]


# =============================================================================
# Cognitive-Aware Synthesis
# =============================================================================

class CognitiveAwareSynthesis(SynthesisAgent):
    """
    Synthesis agent that adapts to cognitive state.

    Adjusts synthesis based on:
    - Burnout level (simpler output when stressed)
    - Mode (different emphasis for exploring vs focused)
    - Cognitive safety constraints (chunking, working memory limits)
    """

    def __init__(self, cognitive_state: CognitiveState = None):
        """
        Initialize with optional cognitive state.

        Args:
            cognitive_state: Current cognitive state for adaptation
        """
        super().__init__()
        self.cognitive_state = cognitive_state

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute cognitive-aware synthesis."""
        # Get cognitive state from context if not set
        if self.cognitive_state is None and 'cognitive_state' in context:
            self.cognitive_state = context['cognitive_state']

        result = await super().execute(task, context)

        # Adapt based on cognitive state
        if self.cognitive_state:
            result = self._adapt_to_cognitive_state(result)

        return result

    def _adapt_to_cognitive_state(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt synthesis result to cognitive state."""
        if not self.cognitive_state:
            return result

        # Simplify output when burned out
        if self.cognitive_state.burnout_level in (BurnoutLevel.ORANGE, BurnoutLevel.RED):
            # Truncate recommendations
            if 'recommendations' in result:
                result['recommendations'] = result['recommendations'][:2]
            # Add recovery note
            result['cognitive_note'] = "Output simplified due to elevated burnout level"

        # Adjust for exploration mode
        if self.cognitive_state.mode == CognitiveMode.EXPLORING:
            # Include more options/possibilities
            result['exploration_friendly'] = True

        # Add cognitive context
        result['cognitive_context'] = {
            'burnout': self.cognitive_state.burnout_level.value,
            'mode': self.cognitive_state.mode.value,
            'focus_level': self.cognitive_state.focus_level,
            'urgency': self.cognitive_state.urgency
        }

        return result


__all__ = [
    'SynthesisAgent', 'CognitiveAwareSynthesis', 'SynthesisResult',
    'SynthesisMode', 'AGENT_PRIORITY'
]
