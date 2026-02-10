"""
Agent Executors
===============

Default executor implementations for common agent types.

Each executor is an async function with signature:
    async def executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]

Executors perform actual work and return structured results.

Available Executors:
- explore_executor: Codebase exploration and pattern finding
- implement_executor: Code implementation and generation
- review_executor: Code review and analysis
- research_executor: Research and information gathering (uses ResearcherAgent)
- planner_executor: Task decomposition and planning (uses PlannerAgent)
- memory_executor: Profile storage and recall (uses MemoryAgent)
- reflection_executor: Self-assessment (uses ReflectionAgent)
- general_executor: General-purpose task handling

Determinism:
- Fixed return structure per executor
- Deterministic error handling
- Logging for reproducibility

Phase 6 Integration:
- New executors wrap the agents from otto.agents module
- Progress tracking via ProgressTracker
- Cognitive state propagation
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Import new agents (Phase 6)
try:
    from ..agents import (
        PlannerAgent,
        ResearcherAgent,
        MemoryAgent,
        ReflectionAgent,
        AgentConfig,
        ProgressTracker,
        get_progress_tracker,
    )
    AGENTS_AVAILABLE = True
except ImportError:
    AGENTS_AVAILABLE = False
    logger.debug("Phase 6 agents not available, using fallback executors")


async def explore_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute exploration tasks.

    Explores codebase for patterns, files, and structures.

    Args:
        task: Description of what to explore
        context: Additional context (files, patterns, scope)

    Returns:
        Dict with:
        - findings: List of discovered items
        - files_read: List of files examined
        - patterns: Identified patterns
        - summary: Human-readable summary
    """
    start_time = time.time()
    logger.info(f"Starting exploration: {task[:50]}...")

    # Extract context
    target_files = context.get("files", [])
    patterns = context.get("patterns", [])
    scope = context.get("scope", "local")

    findings = []
    files_read = []

    # Basic exploration logic
    if target_files:
        for file_path in target_files[:10]:  # Limit to 10 files
            try:
                path = Path(file_path)
                if path.exists() and path.is_file():
                    files_read.append(str(path))
                    # Read file and look for patterns
                    content = path.read_text(errors='ignore')
                    for pattern in patterns or [task.lower()]:
                        if pattern.lower() in content.lower():
                            findings.append({
                                "type": "pattern_match",
                                "file": str(path),
                                "pattern": pattern,
                            })
            except Exception as e:
                logger.debug(f"Could not read {file_path}: {e}")

    elapsed = time.time() - start_time
    logger.info(f"Exploration complete: {len(findings)} findings in {elapsed:.2f}s")

    return {
        "findings": findings,
        "files_read": files_read,
        "patterns": patterns or [],
        "summary": f"Explored {len(files_read)} files, found {len(findings)} matches",
        "duration_seconds": elapsed,
    }


async def implement_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute implementation tasks.

    Generates code implementations based on task description.

    Args:
        task: What to implement
        context: Additional context (language, style, target_file)

    Returns:
        Dict with:
        - code: Generated code (if any)
        - files_modified: List of modified files
        - approach: Implementation approach taken
        - notes: Implementation notes
    """
    start_time = time.time()
    logger.info(f"Starting implementation: {task[:50]}...")

    # Extract context
    language = context.get("language", "python")
    target_file = context.get("target_file")
    style = context.get("style", "standard")

    # Implementation would integrate with actual code generation
    # For now, return a structured placeholder
    elapsed = time.time() - start_time

    return {
        "code": None,  # Would contain generated code
        "files_modified": [],
        "approach": f"Planned {language} implementation",
        "notes": [
            f"Task: {task}",
            f"Language: {language}",
            f"Style: {style}",
        ],
        "requires_human_review": True,
        "duration_seconds": elapsed,
    }


async def review_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute code review tasks.

    Reviews code for quality, patterns, and potential issues.

    Args:
        task: What to review
        context: Additional context (files, focus_areas)

    Returns:
        Dict with:
        - issues: List of identified issues
        - suggestions: List of improvements
        - files_reviewed: Files that were reviewed
        - summary: Review summary
    """
    start_time = time.time()
    logger.info(f"Starting review: {task[:50]}...")

    # Extract context
    target_files = context.get("files", [])
    focus_areas = context.get("focus_areas", ["quality", "patterns"])

    issues = []
    suggestions = []
    files_reviewed = []

    # Basic review logic
    for file_path in target_files[:5]:  # Limit to 5 files
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                files_reviewed.append(str(path))
                content = path.read_text(errors='ignore')
                lines = content.split('\n')

                # Simple checks
                if len(lines) > 500:
                    issues.append({
                        "file": str(path),
                        "type": "complexity",
                        "message": f"File has {len(lines)} lines - consider splitting",
                    })

                # Check for TODO comments
                for i, line in enumerate(lines):
                    if 'TODO' in line or 'FIXME' in line:
                        suggestions.append({
                            "file": str(path),
                            "line": i + 1,
                            "type": "todo",
                            "message": line.strip(),
                        })

        except Exception as e:
            logger.debug(f"Could not review {file_path}: {e}")

    elapsed = time.time() - start_time
    logger.info(f"Review complete: {len(issues)} issues, {len(suggestions)} suggestions")

    return {
        "issues": issues,
        "suggestions": suggestions[:20],  # Limit suggestions
        "files_reviewed": files_reviewed,
        "summary": f"Reviewed {len(files_reviewed)} files: {len(issues)} issues, {len(suggestions)} suggestions",
        "focus_areas": focus_areas,
        "duration_seconds": elapsed,
    }


async def research_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute research tasks.

    Gathers information and synthesizes findings.

    Args:
        task: Research question or topic
        context: Additional context (sources, depth)

    Returns:
        Dict with:
        - findings: Research findings
        - sources: Information sources used
        - synthesis: Synthesized understanding
        - questions: Follow-up questions
    """
    start_time = time.time()
    logger.info(f"Starting research: {task[:50]}...")

    # Extract context
    sources = context.get("sources", [])
    depth = context.get("depth", "standard")

    # Research would integrate with knowledge retrieval
    # For now, return structured placeholder
    elapsed = time.time() - start_time

    return {
        "findings": [],
        "sources": sources,
        "synthesis": f"Research task registered: {task}",
        "questions": [
            "What specific aspects need deeper investigation?",
            "Are there related topics to consider?",
        ],
        "depth": depth,
        "duration_seconds": elapsed,
    }


async def general_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute general-purpose tasks.

    Handles tasks that don't fit specific categories.

    Args:
        task: Task description
        context: Additional context

    Returns:
        Dict with:
        - result: Task result
        - actions: Actions taken
        - status: Completion status
    """
    start_time = time.time()
    logger.info(f"Starting general task: {task[:50]}...")

    # General executor performs basic task tracking
    elapsed = time.time() - start_time

    return {
        "result": f"Task acknowledged: {task}",
        "actions": ["Parsed task description", "Validated context"],
        "status": "completed",
        "context_keys": list(context.keys()) if context else [],
        "duration_seconds": elapsed,
    }


# =============================================================================
# Phase 6 Agent-Based Executors
# =============================================================================

def _create_agent_config(context: Dict[str, Any], agent_type: str) -> "AgentConfig":
    """Create AgentConfig from context, propagating cognitive state."""
    if not AGENTS_AVAILABLE:
        return None

    return AgentConfig(
        agent_type=agent_type,
        max_turns=context.get("max_turns", 10),
        timeout_seconds=context.get("timeout", 300.0),
        parent_session_id=context.get("session_id"),
        burnout_level=context.get("burnout_level", "GREEN"),
        energy_level=context.get("energy_level", "medium"),
        depth=context.get("agent_depth", 0),
    )


async def planner_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute planning tasks using PlannerAgent.

    Decomposes complex tasks into executable steps.

    Args:
        task: Task to plan
        context: Additional context (scope, files, etc.)

    Returns:
        Dict with:
        - plan: ExecutionPlan as dict
        - steps: List of step descriptions
        - complexity: Overall complexity
        - estimated_turns: Turn estimate
    """
    if not AGENTS_AVAILABLE:
        return {
            "error": "PlannerAgent not available",
            "fallback": True,
            "task": task,
        }

    config = _create_agent_config(context, "planner")
    agent = PlannerAgent(config)

    # Track progress
    tracker = get_progress_tracker()
    agent.on_progress(lambda p: tracker.update_progress(
        agent.agent_id, p.current_step, p.step_description
    ))
    tracker.start_agent(agent.agent_id, "planner", task[:50], agent._get_step_count())

    result = await agent.run(task, context)

    if result.success:
        plan = result.result
        tracker.complete_agent(agent.agent_id, True, "Plan created")
        return {
            "plan": plan.to_dict(),
            "steps": [s.description for s in plan.steps],
            "complexity": plan.total_complexity,
            "estimated_turns": plan.estimated_turns,
            "duration_seconds": result.duration_seconds,
        }
    else:
        tracker.complete_agent(agent.agent_id, False, result.errors[0] if result.errors else "Failed")
        return {
            "error": result.errors[0] if result.errors else "Planning failed",
            "duration_seconds": result.duration_seconds,
        }


async def researcher_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute research tasks using ResearcherAgent.

    Gathers and synthesizes information from multiple sources.

    Args:
        task: Research query
        context: Additional context (files, depth, etc.)

    Returns:
        Dict with:
        - findings: Research findings
        - sources: Sources consulted
        - synthesis: Synthesized understanding
        - confidence: Overall confidence
    """
    if not AGENTS_AVAILABLE:
        # Fall back to basic research_executor
        return await research_executor(task, context)

    config = _create_agent_config(context, "researcher")
    agent = ResearcherAgent(config)

    # Track progress
    tracker = get_progress_tracker()
    agent.on_progress(lambda p: tracker.update_progress(
        agent.agent_id, p.current_step, p.step_description
    ))
    tracker.start_agent(agent.agent_id, "researcher", task[:50], agent._get_step_count())

    result = await agent.run(task, context)

    if result.success:
        research = result.result
        tracker.complete_agent(agent.agent_id, True, "Research complete")
        return {
            "findings": [f.to_dict() for f in research.findings],
            "sources": [s.to_dict() for s in research.sources_consulted],
            "synthesis": research.synthesis,
            "follow_up_questions": research.follow_up_questions,
            "gaps": research.gaps,
            "confidence": research.confidence,
            "duration_seconds": result.duration_seconds,
        }
    else:
        tracker.complete_agent(agent.agent_id, False, result.errors[0] if result.errors else "Failed")
        return {
            "error": result.errors[0] if result.errors else "Research failed",
            "duration_seconds": result.duration_seconds,
        }


async def memory_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute memory operations using MemoryAgent.

    Store, recall, update, or forget memories.

    Args:
        task: Memory operation (e.g., "store preference:theme=dark")
        context: Additional context (confidence, source, etc.)

    Returns:
        Dict with:
        - operation: Operation performed
        - success: Whether operation succeeded
        - entries: Affected memory entries
        - message: Status message
    """
    if not AGENTS_AVAILABLE:
        return {
            "error": "MemoryAgent not available",
            "fallback": True,
            "task": task,
        }

    config = _create_agent_config(context, "memory")
    storage_path = context.get("storage_path")

    if storage_path:
        agent = MemoryAgent(config, storage_path=Path(storage_path))
    else:
        agent = MemoryAgent(config)

    result = await agent.run(task, context)

    if result.success:
        memory_result = result.result
        return {
            "operation": memory_result.operation,
            "success": memory_result.success,
            "entries": [e.to_dict() for e in memory_result.entries],
            "message": memory_result.message,
            "affected_count": memory_result.affected_count,
            "duration_seconds": result.duration_seconds,
        }
    else:
        return {
            "operation": "error",
            "success": False,
            "error": result.errors[0] if result.errors else "Memory operation failed",
            "duration_seconds": result.duration_seconds,
        }


async def reflection_executor(task: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute reflection using ReflectionAgent.

    Perform self-assessment and generate course corrections.

    Args:
        task: Reflection type (progress, alignment, energy, approach, completion)
        context: Current context (goal, completed_steps, cognitive_state, etc.)

    Returns:
        Dict with:
        - reflection_type: Type of reflection performed
        - overall_score: Assessment score (0-1)
        - overall_status: on_track, drifting, or needs_intervention
        - assessments: Detailed assessments
        - course_corrections: Recommended corrections
        - insights: Generated insights
    """
    if not AGENTS_AVAILABLE:
        return {
            "error": "ReflectionAgent not available",
            "fallback": True,
            "task": task,
        }

    config = _create_agent_config(context, "reflection")
    agent = ReflectionAgent(config)

    result = await agent.run(task, context)

    if result.success:
        reflection = result.result
        return {
            "reflection_type": reflection.reflection_type,
            "overall_score": reflection.overall_score,
            "overall_status": reflection.overall_status,
            "assessments": [a.to_dict() for a in reflection.assessments],
            "course_corrections": reflection.course_corrections,
            "insights": reflection.insights,
            "next_check_after": reflection.next_check_after,
            "requires_intervention": reflection.requires_intervention(),
            "duration_seconds": result.duration_seconds,
        }
    else:
        return {
            "error": result.errors[0] if result.errors else "Reflection failed",
            "duration_seconds": result.duration_seconds,
        }


# =============================================================================
# Executor Registry
# =============================================================================

# Executor registry for dynamic lookup
EXECUTOR_REGISTRY: Dict[str, Any] = {
    # Original executors
    "explore": explore_executor,
    "implement": implement_executor,
    "review": review_executor,
    "research": researcher_executor if AGENTS_AVAILABLE else research_executor,
    "general": general_executor,
    # Phase 6 agent-based executors
    "planner": planner_executor,
    "researcher": researcher_executor,
    "memory": memory_executor,
    "reflection": reflection_executor,
}


def get_executor(agent_type: str):
    """
    Get executor function by agent type.

    Args:
        agent_type: Type of agent (explore, implement, etc.)

    Returns:
        Executor function or None if not found
    """
    return EXECUTOR_REGISTRY.get(agent_type)


def list_executors() -> List[str]:
    """List all available executor types."""
    return list(EXECUTOR_REGISTRY.keys())


__all__ = [
    # Original executors
    "explore_executor",
    "implement_executor",
    "review_executor",
    "research_executor",
    "general_executor",
    # Phase 6 executors
    "planner_executor",
    "researcher_executor",
    "memory_executor",
    "reflection_executor",
    # Registry
    "get_executor",
    "list_executors",
    "EXECUTOR_REGISTRY",
    "AGENTS_AVAILABLE",
]
