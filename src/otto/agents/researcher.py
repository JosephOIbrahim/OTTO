"""
Researcher Agent
================

Deep research agent with knowledge layer integration.

The Researcher gathers information from multiple sources:
- Local files and codebase
- Knowledge graph (if available)
- External documentation

Philosophy:
    Research is about synthesis, not just gathering.
    Surface insights, not just data.

ThinkingMachines [He2025] Compliance:
- Fixed research phases
- Deterministic source prioritization
- Bounded search depth
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import Agent, AgentConfig, RetryableError

logger = logging.getLogger(__name__)


@dataclass
class ResearchSource:
    """A source of research information."""
    source_type: str  # "file", "knowledge", "documentation", "web"
    path: str  # File path, knowledge path, or URL
    relevance: float  # 0.0 to 1.0
    excerpt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "path": self.path,
            "relevance": self.relevance,
            "excerpt": self.excerpt,
            "metadata": self.metadata,
        }


@dataclass
class ResearchFinding:
    """A finding from research."""
    topic: str
    summary: str
    confidence: float  # 0.0 to 1.0
    sources: List[ResearchSource] = field(default_factory=list)
    related_topics: List[str] = field(default_factory=list)
    actionable: bool = False  # Can this be acted upon?

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "summary": self.summary,
            "confidence": self.confidence,
            "sources": [s.to_dict() for s in self.sources],
            "related_topics": self.related_topics,
            "actionable": self.actionable,
        }


@dataclass
class ResearchResult:
    """Complete research result."""
    query: str
    findings: List[ResearchFinding]
    sources_consulted: List[ResearchSource]
    synthesis: str  # Overall synthesis of findings
    follow_up_questions: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)  # What we couldn't find
    confidence: float = 0.0  # Overall confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "findings": [f.to_dict() for f in self.findings],
            "sources_consulted": [s.to_dict() for s in self.sources_consulted],
            "synthesis": self.synthesis,
            "follow_up_questions": self.follow_up_questions,
            "gaps": self.gaps,
            "confidence": self.confidence,
        }

    def format_display(self) -> str:
        """Format for terminal display."""
        lines = [
            f"## Research: {self.query[:50]}...",
            "",
            f"### Synthesis (confidence: {self.confidence:.0%})",
            self.synthesis,
            "",
        ]

        if self.findings:
            lines.append("### Key Findings:")
            for finding in self.findings:
                lines.append(f"  - **{finding.topic}**: {finding.summary}")
                if finding.actionable:
                    lines.append(f"    (Actionable)")

        if self.follow_up_questions:
            lines.append("")
            lines.append("### Follow-up Questions:")
            for q in self.follow_up_questions:
                lines.append(f"  - {q}")

        if self.gaps:
            lines.append("")
            lines.append("### Information Gaps:")
            for g in self.gaps:
                lines.append(f"  - {g}")

        return "\n".join(lines)


class ResearcherAgent(Agent[ResearchResult]):
    """
    Agent for deep research and information synthesis.

    Features:
    - Multi-source information gathering
    - Knowledge graph integration
    - Confidence scoring
    - Gap detection
    - Follow-up question generation

    Example:
        agent = ResearcherAgent()
        result = await agent.run(
            "How does the authentication system work?",
            {"files": ["src/auth/"], "depth": "deep"}
        )
        research = result.result
    """

    agent_type = "researcher"

    # Search depth limits
    DEPTH_LIMITS = {
        "shallow": {"max_files": 5, "max_sources": 3},
        "standard": {"max_files": 15, "max_sources": 10},
        "deep": {"max_files": 30, "max_sources": 20},
    }

    def __init__(self, config: AgentConfig = None, knowledge_engine=None):
        super().__init__(config)
        self.knowledge_engine = knowledge_engine
        self._sources_consulted: List[ResearchSource] = []
        self._findings: List[ResearchFinding] = []

    def _get_step_count(self) -> int:
        """Researcher has 5 phases."""
        return 5

    async def _execute(self, query: str, context: Dict[str, Any]) -> ResearchResult:
        """
        Execute research process.

        Phases:
        1. Parse query and identify search strategy
        2. Search local files
        3. Search knowledge graph
        4. Synthesize findings
        5. Generate follow-up questions
        """
        self.increment_turn()

        depth = context.get("depth", "standard")
        limits = self.DEPTH_LIMITS.get(depth, self.DEPTH_LIMITS["standard"])

        # Adjust limits for cognitive state
        if self.config.should_reduce_scope():
            limits = self.DEPTH_LIMITS["shallow"]

        # Phase 1: Parse query
        await self.report_progress(1, "Parsing query and planning search")
        search_plan = self._create_search_plan(query, context)

        # Phase 2: Search local files
        await self.report_progress(2, "Searching local files")
        file_results = await self._search_files(search_plan, context, limits)

        # Phase 3: Search knowledge
        await self.report_progress(3, "Consulting knowledge sources")
        knowledge_results = await self._search_knowledge(search_plan, limits)

        # Phase 4: Synthesize
        await self.report_progress(4, "Synthesizing findings")
        synthesis = self._synthesize_findings(query)

        # Phase 5: Follow-up
        await self.report_progress(5, "Generating follow-up questions")
        follow_ups, gaps = self._generate_follow_ups(query)

        # Calculate overall confidence
        if self._findings:
            confidence = sum(f.confidence for f in self._findings) / len(self._findings)
        else:
            confidence = 0.0

        return ResearchResult(
            query=query,
            findings=self._findings.copy(),
            sources_consulted=self._sources_consulted.copy(),
            synthesis=synthesis,
            follow_up_questions=follow_ups,
            gaps=gaps,
            confidence=confidence,
        )

    def _create_search_plan(
        self, query: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create search plan from query."""
        query_lower = query.lower()

        # Extract search terms
        terms = self._extract_search_terms(query)

        # Identify search type
        search_types = []
        if any(w in query_lower for w in ["how", "work", "implement", "does"]):
            search_types.append("functional")
        if any(w in query_lower for w in ["where", "find", "locate", "which"]):
            search_types.append("locational")
        if any(w in query_lower for w in ["why", "reason", "purpose"]):
            search_types.append("conceptual")
        if any(w in query_lower for w in ["what", "define", "explain"]):
            search_types.append("definitional")

        if not search_types:
            search_types = ["general"]

        # Get file patterns from context
        file_patterns = context.get("files", [])
        if not file_patterns:
            file_patterns = context.get("patterns", ["**/*.py"])

        return {
            "terms": terms,
            "search_types": search_types,
            "file_patterns": file_patterns,
            "focus_areas": context.get("focus_areas", []),
        }

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract search terms from query."""
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "is", "are", "was", "were",
            "be", "been", "being", "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "may", "might", "must",
            "how", "what", "where", "when", "why", "which", "who",
            "this", "that", "these", "those", "i", "we", "you", "it", "they",
        }

        words = query.lower().split()
        terms = [w.strip("?.,!") for w in words if w not in stop_words and len(w) > 2]

        return terms[:10]  # Limit terms

    async def _search_files(
        self,
        search_plan: Dict[str, Any],
        context: Dict[str, Any],
        limits: Dict[str, int],
    ) -> List[ResearchSource]:
        """Search local files for relevant information."""
        sources = []
        terms = search_plan["terms"]
        patterns = search_plan["file_patterns"]

        # Get base directory
        base_dir = Path(context.get("base_dir", "."))

        files_searched = 0
        max_files = limits["max_files"]

        for pattern in patterns:
            if files_searched >= max_files:
                break

            try:
                # Glob for files
                if base_dir.exists():
                    matching_files = list(base_dir.glob(pattern))[:max_files - files_searched]

                    for file_path in matching_files:
                        if file_path.is_file():
                            source = self._search_file(file_path, terms)
                            if source:
                                sources.append(source)
                                self._sources_consulted.append(source)
                                self.track_file_read(str(file_path))
                            files_searched += 1

            except Exception as e:
                logger.debug(f"Error searching pattern {pattern}: {e}")

        return sources

    def _search_file(self, file_path: Path, terms: List[str]) -> Optional[ResearchSource]:
        """Search a single file for terms."""
        try:
            content = file_path.read_text(errors="ignore")
            content_lower = content.lower()

            # Check if any terms match
            matches = sum(1 for term in terms if term in content_lower)
            if matches == 0:
                return None

            # Calculate relevance based on match density
            relevance = min(1.0, matches / len(terms)) if terms else 0.5

            # Extract relevant excerpt
            excerpt = self._extract_excerpt(content, terms)

            return ResearchSource(
                source_type="file",
                path=str(file_path),
                relevance=relevance,
                excerpt=excerpt,
                metadata={"matches": matches},
            )

        except Exception as e:
            logger.debug(f"Error reading file {file_path}: {e}")
            return None

    def _extract_excerpt(self, content: str, terms: List[str], max_length: int = 200) -> str:
        """Extract relevant excerpt from content."""
        content_lower = content.lower()

        # Find first matching term
        for term in terms:
            idx = content_lower.find(term)
            if idx >= 0:
                # Get surrounding context
                start = max(0, idx - 50)
                end = min(len(content), idx + max_length - 50)

                excerpt = content[start:end]
                if start > 0:
                    excerpt = "..." + excerpt
                if end < len(content):
                    excerpt = excerpt + "..."

                return excerpt

        # No matches, return beginning
        return content[:max_length] + "..." if len(content) > max_length else content

    async def _search_knowledge(
        self, search_plan: Dict[str, Any], limits: Dict[str, int]
    ) -> List[ResearchSource]:
        """Search knowledge graph if available."""
        sources = []

        if not self.knowledge_engine:
            return sources

        terms = search_plan["terms"]
        max_sources = limits["max_sources"]

        try:
            # Search knowledge by terms
            for term in terms[:5]:  # Limit term searches
                results = self.knowledge_engine.search(term, limit=3)

                for result in results:
                    source = ResearchSource(
                        source_type="knowledge",
                        path=result.get("path", ""),
                        relevance=result.get("confidence", 0.5),
                        excerpt=result.get("summary", ""),
                        metadata=result.get("metadata", {}),
                    )
                    sources.append(source)
                    self._sources_consulted.append(source)

                    if len(sources) >= max_sources:
                        break

                if len(sources) >= max_sources:
                    break

        except Exception as e:
            logger.debug(f"Knowledge search error: {e}")
            self.add_warning(f"Knowledge search unavailable: {e}")

        return sources

    def _synthesize_findings(self, query: str) -> str:
        """Synthesize all sources into findings and summary."""
        # Group sources by type
        file_sources = [s for s in self._sources_consulted if s.source_type == "file"]
        knowledge_sources = [s for s in self._sources_consulted if s.source_type == "knowledge"]

        # Create findings from high-relevance sources
        high_relevance = [s for s in self._sources_consulted if s.relevance >= 0.5]

        for source in high_relevance[:5]:  # Limit findings
            finding = ResearchFinding(
                topic=Path(source.path).stem if source.source_type == "file" else source.path,
                summary=source.excerpt or "Relevant content found",
                confidence=source.relevance,
                sources=[source],
                actionable=source.source_type == "file",
            )
            self._findings.append(finding)

        # Generate synthesis
        if not self._sources_consulted:
            return "No relevant sources found for this query."

        synthesis_parts = []

        if file_sources:
            synthesis_parts.append(
                f"Found {len(file_sources)} relevant files"
            )

        if knowledge_sources:
            synthesis_parts.append(
                f"and {len(knowledge_sources)} knowledge entries"
            )

        if self._findings:
            high_conf = len([f for f in self._findings if f.confidence >= 0.7])
            if high_conf:
                synthesis_parts.append(
                    f"with {high_conf} high-confidence findings"
                )

        return ". ".join(synthesis_parts) + "." if synthesis_parts else "Research complete."

    def _generate_follow_ups(self, query: str) -> tuple[List[str], List[str]]:
        """Generate follow-up questions and identify gaps."""
        follow_ups = []
        gaps = []

        # Analyze what we found vs what was asked
        if not self._findings:
            gaps.append("No direct answers found - may need broader search")
            follow_ups.append("Would you like to search with different terms?")
        elif all(f.confidence < 0.5 for f in self._findings):
            gaps.append("Low confidence in findings - may need manual review")
            follow_ups.append("Should we examine the most relevant files in detail?")
        else:
            # High-confidence findings exist
            if len(self._findings) == 1:
                follow_ups.append("Would you like to explore related areas?")
            else:
                follow_ups.append("Should we dive deeper into any specific finding?")

        # Check for actionable items
        actionable = [f for f in self._findings if f.actionable]
        if actionable:
            follow_ups.append(f"Found {len(actionable)} files that could be modified")

        return follow_ups, gaps


__all__ = [
    "ResearcherAgent",
    "ResearchSource",
    "ResearchFinding",
    "ResearchResult",
]
