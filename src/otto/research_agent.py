"""
Research Agent - Worker Agent
=============================

A worker agent that does REAL research work, not just routing/metadata.

This agent:
- Searches codebases for patterns and information
- Analyzes documentation
- Synthesizes findings into actionable research summaries
- Produces real output that can be used directly

Distinguishes from routing agents:
- Routing agents: echo_curator, domain_intel, moe_router (produce metadata)
- Worker agents: research_agent, synthesis_agent, code_generator (produce real output)

ThinkingMachines [He2025] Compliance:
- Deterministic search ordering
- Reproducible result synthesis
- Fixed evaluation patterns
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)


# =============================================================================
# Research Task Types
# =============================================================================

class ResearchType:
    """Types of research tasks this agent handles."""
    CODEBASE_SEARCH = "codebase_search"       # Search for patterns in code
    DOCUMENTATION = "documentation"            # Analyze docs
    DEPENDENCY_MAP = "dependency_map"          # Map dependencies
    PATTERN_ANALYSIS = "pattern_analysis"      # Analyze code patterns
    ARCHITECTURE = "architecture"              # Understand system architecture
    COMPARISON = "comparison"                  # Compare approaches/options


# =============================================================================
# Research Result
# =============================================================================

@dataclass
class ResearchFinding:
    """A single research finding."""
    category: str
    title: str
    content: str
    confidence: float  # 0-1 confidence in finding
    source: Optional[str] = None  # Source file/doc
    line_number: Optional[int] = None
    relevance: float = 1.0  # Relevance to query

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence,
            "source": self.source,
            "line_number": self.line_number,
            "relevance": self.relevance
        }


@dataclass
class ResearchResult:
    """Complete research result."""
    query: str
    research_type: str
    findings: List[ResearchFinding] = field(default_factory=list)
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    files_searched: int = 0
    patterns_found: int = 0
    execution_time_ms: float = 0.0
    checksum: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "research_type": self.research_type,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "recommendations": self.recommendations,
            "files_searched": self.files_searched,
            "patterns_found": self.patterns_found,
            "execution_time_ms": self.execution_time_ms,
            "checksum": self.checksum
        }


# =============================================================================
# Research Agent
# =============================================================================

class ResearchAgent:
    """
    Worker agent that performs actual research.

    Unlike routing agents that produce metadata, this agent
    produces real, actionable research output.
    """

    def __init__(self, workspace: Path = None):
        """
        Initialize research agent.

        Args:
            workspace: Root directory for codebase searches
        """
        self.name = "research_agent"
        self.workspace = workspace or Path.home() / "Orchestra"
        self.logger = logging.getLogger(f"Agent.{self.name}")

        # Search configuration
        self.max_files = 100  # Max files to search per query
        self.max_results = 20  # Max findings to return

        # File type filters
        self.code_extensions = {'.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml'}
        self.doc_extensions = {'.md', '.txt', '.rst', '.adoc'}

    async def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute research task.

        Args:
            task: Research query/task description
            context: Execution context with workspace, filters, etc.

        Returns:
            Dict containing research results
        """
        import time
        start_time = time.time()

        self.logger.info(f"Research agent executing: {task[:100]}...")

        # Detect research type
        research_type = self._detect_research_type(task)

        # Execute appropriate research method
        if research_type == ResearchType.CODEBASE_SEARCH:
            result = await self._search_codebase(task, context)
        elif research_type == ResearchType.DOCUMENTATION:
            result = await self._analyze_documentation(task, context)
        elif research_type == ResearchType.DEPENDENCY_MAP:
            result = await self._map_dependencies(task, context)
        elif research_type == ResearchType.PATTERN_ANALYSIS:
            result = await self._analyze_patterns(task, context)
        elif research_type == ResearchType.ARCHITECTURE:
            result = await self._analyze_architecture(task, context)
        else:
            # Default to codebase search
            result = await self._search_codebase(task, context)

        # Calculate execution time and checksum
        result.execution_time_ms = (time.time() - start_time) * 1000
        result.checksum = self._compute_checksum(result)

        self.logger.info(
            f"Research complete: {len(result.findings)} findings, "
            f"{result.files_searched} files searched"
        )

        return result.to_dict()

    def _detect_research_type(self, task: str) -> str:
        """Detect research type from task description."""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["import", "depend", "require", "package"]):
            return ResearchType.DEPENDENCY_MAP

        if any(kw in task_lower for kw in ["doc", "readme", "guide", "explain"]):
            return ResearchType.DOCUMENTATION

        if any(kw in task_lower for kw in ["pattern", "convention", "style", "how is"]):
            return ResearchType.PATTERN_ANALYSIS

        if any(kw in task_lower for kw in ["architecture", "structure", "overview", "design"]):
            return ResearchType.ARCHITECTURE

        if any(kw in task_lower for kw in ["compare", "vs", "difference", "versus"]):
            return ResearchType.COMPARISON

        return ResearchType.CODEBASE_SEARCH

    async def _search_codebase(self, query: str, context: Dict[str, Any]) -> ResearchResult:
        """
        Search codebase for patterns matching query.

        This is REAL search, not simulated.
        """
        result = ResearchResult(query=query, research_type=ResearchType.CODEBASE_SEARCH)
        workspace = Path(context.get("workspace", self.workspace))

        # Extract search terms from query
        search_terms = self._extract_search_terms(query)

        if not workspace.exists():
            result.summary = f"Workspace not found: {workspace}"
            return result

        # Search files
        files_searched = 0
        findings = []

        for ext in self.code_extensions:
            for file_path in workspace.rglob(f"*{ext}"):
                if files_searched >= self.max_files:
                    break

                # Skip common non-code directories
                if any(skip in str(file_path) for skip in ['node_modules', '__pycache__', '.git', 'venv']):
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    files_searched += 1

                    # Search for terms
                    for term in search_terms:
                        matches = self._find_matches(content, term, file_path)
                        findings.extend(matches)

                except Exception as e:
                    self.logger.debug(f"Error reading {file_path}: {e}")

        result.files_searched = files_searched
        result.patterns_found = len(findings)

        # Sort by relevance and limit
        findings.sort(key=lambda f: f.relevance, reverse=True)
        result.findings = findings[:self.max_results]

        # Generate summary
        result.summary = self._generate_summary(query, result.findings)
        result.recommendations = self._generate_recommendations(query, result.findings)

        return result

    async def _analyze_documentation(self, query: str, context: Dict[str, Any]) -> ResearchResult:
        """Analyze documentation files."""
        result = ResearchResult(query=query, research_type=ResearchType.DOCUMENTATION)
        workspace = Path(context.get("workspace", self.workspace))

        findings = []
        files_searched = 0

        # Search documentation files
        for ext in self.doc_extensions:
            for file_path in workspace.rglob(f"*{ext}"):
                if files_searched >= self.max_files:
                    break

                if any(skip in str(file_path) for skip in ['node_modules', '.git', 'venv']):
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    files_searched += 1

                    # Extract relevant sections
                    sections = self._extract_doc_sections(content, query, file_path)
                    findings.extend(sections)

                except Exception as e:
                    self.logger.debug(f"Error reading {file_path}: {e}")

        result.files_searched = files_searched
        result.patterns_found = len(findings)
        result.findings = sorted(findings, key=lambda f: f.relevance, reverse=True)[:self.max_results]
        result.summary = self._generate_doc_summary(query, result.findings)

        return result

    async def _map_dependencies(self, query: str, context: Dict[str, Any]) -> ResearchResult:
        """Map project dependencies."""
        result = ResearchResult(query=query, research_type=ResearchType.DEPENDENCY_MAP)
        workspace = Path(context.get("workspace", self.workspace))

        findings = []

        # Check common dependency files
        dep_files = [
            ("requirements.txt", "Python"),
            ("setup.py", "Python"),
            ("pyproject.toml", "Python"),
            ("package.json", "JavaScript"),
            ("Cargo.toml", "Rust"),
            ("go.mod", "Go"),
        ]

        for filename, lang in dep_files:
            dep_file = workspace / filename
            if dep_file.exists():
                try:
                    content = dep_file.read_text(encoding='utf-8')
                    deps = self._parse_dependencies(content, filename, lang)
                    findings.extend(deps)
                    result.files_searched += 1
                except Exception as e:
                    self.logger.debug(f"Error parsing {filename}: {e}")

        result.patterns_found = len(findings)
        result.findings = findings
        result.summary = f"Found {len(findings)} dependencies across {result.files_searched} files"

        return result

    async def _analyze_patterns(self, query: str, context: Dict[str, Any]) -> ResearchResult:
        """Analyze code patterns and conventions."""
        result = ResearchResult(query=query, research_type=ResearchType.PATTERN_ANALYSIS)
        workspace = Path(context.get("workspace", self.workspace))

        findings = []
        patterns_found = {}

        # Analyze Python files for patterns
        for py_file in workspace.rglob("*.py"):
            if result.files_searched >= self.max_files:
                break

            if any(skip in str(py_file) for skip in ['node_modules', '__pycache__', '.git', 'venv']):
                continue

            try:
                content = py_file.read_text(encoding='utf-8', errors='ignore')
                result.files_searched += 1

                # Detect patterns
                file_patterns = self._detect_patterns(content, py_file)
                for pattern, count in file_patterns.items():
                    patterns_found[pattern] = patterns_found.get(pattern, 0) + count

            except Exception as e:
                self.logger.debug(f"Error analyzing {py_file}: {e}")

        # Convert to findings
        for pattern, count in sorted(patterns_found.items(), key=lambda x: x[1], reverse=True):
            findings.append(ResearchFinding(
                category="pattern",
                title=pattern,
                content=f"Found {count} occurrences",
                confidence=min(count / 10, 1.0),
                relevance=count / max(patterns_found.values()) if patterns_found else 0
            ))

        result.patterns_found = len(findings)
        result.findings = findings[:self.max_results]
        result.summary = f"Analyzed {result.files_searched} files, found {len(patterns_found)} patterns"

        return result

    async def _analyze_architecture(self, query: str, context: Dict[str, Any]) -> ResearchResult:
        """Analyze system architecture."""
        result = ResearchResult(query=query, research_type=ResearchType.ARCHITECTURE)
        workspace = Path(context.get("workspace", self.workspace))

        findings = []

        # Find key architecture files
        arch_indicators = [
            ("__init__.py", "Python module"),
            ("index.ts", "TypeScript entry"),
            ("main.py", "Python entry"),
            ("app.py", "Application entry"),
            ("config.py", "Configuration"),
            ("settings.py", "Settings"),
        ]

        modules = set()
        for indicator, desc in arch_indicators:
            for file_path in workspace.rglob(indicator):
                if any(skip in str(file_path) for skip in ['node_modules', '__pycache__', '.git', 'venv']):
                    continue

                parent = file_path.parent
                rel_path = parent.relative_to(workspace) if parent != workspace else Path(".")
                modules.add(str(rel_path))

                findings.append(ResearchFinding(
                    category="architecture",
                    title=f"{desc}: {rel_path}",
                    content=f"Found at {file_path.relative_to(workspace)}",
                    confidence=0.8,
                    source=str(file_path),
                    relevance=0.8
                ))

        result.files_searched = len(findings)
        result.patterns_found = len(modules)
        result.findings = findings[:self.max_results]
        result.summary = f"Found {len(modules)} modules/components in architecture"
        result.recommendations = [f"Module: {m}" for m in sorted(modules)[:10]]

        return result

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract search terms from query."""
        # Remove common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                      'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                      'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                      'can', 'need', 'dare', 'ought', 'used', 'to', 'of', 'in',
                      'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
                      'through', 'during', 'before', 'after', 'above', 'below',
                      'between', 'under', 'again', 'further', 'then', 'once',
                      'here', 'there', 'when', 'where', 'why', 'how', 'all',
                      'each', 'few', 'more', 'most', 'other', 'some', 'such',
                      'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than',
                      'too', 'very', 'just', 'and', 'but', 'or', 'if', 'because',
                      'until', 'while', 'find', 'search', 'look', 'what', 'show'}

        words = re.findall(r'\b\w+\b', query.lower())
        terms = [w for w in words if w not in stop_words and len(w) > 2]

        # Also try to find quoted phrases
        quoted = re.findall(r'"([^"]+)"', query)
        terms.extend(quoted)

        return terms[:10]  # Limit to 10 terms

    def _find_matches(self, content: str, term: str, file_path: Path) -> List[ResearchFinding]:
        """Find matches for a term in content."""
        findings = []
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            if term.lower() in line.lower():
                # Get context (surrounding lines)
                start = max(0, i - 2)
                end = min(len(lines), i + 2)
                context_lines = lines[start:end]
                context = '\n'.join(context_lines)

                findings.append(ResearchFinding(
                    category="code_match",
                    title=f"Match in {file_path.name}:{i}",
                    content=context[:500],  # Limit content length
                    confidence=0.8,
                    source=str(file_path),
                    line_number=i,
                    relevance=0.7
                ))

                if len(findings) >= 5:  # Limit per file
                    break

        return findings

    def _extract_doc_sections(self, content: str, query: str, file_path: Path) -> List[ResearchFinding]:
        """Extract relevant sections from documentation."""
        findings = []
        terms = self._extract_search_terms(query)

        # Split by headers (markdown style)
        sections = re.split(r'\n#{1,3}\s+', content)

        for section in sections:
            if not section.strip():
                continue

            # Check relevance
            section_lower = section.lower()
            matches = sum(1 for term in terms if term in section_lower)

            if matches > 0:
                # Get first line as title
                lines = section.split('\n')
                title = lines[0][:100] if lines else "Section"

                findings.append(ResearchFinding(
                    category="documentation",
                    title=title,
                    content=section[:500],
                    confidence=min(matches / len(terms), 1.0) if terms else 0.5,
                    source=str(file_path),
                    relevance=matches / max(len(terms), 1)
                ))

        return findings

    def _parse_dependencies(self, content: str, filename: str, lang: str) -> List[ResearchFinding]:
        """Parse dependencies from dependency file."""
        findings = []

        if filename == "requirements.txt":
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    pkg = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                    findings.append(ResearchFinding(
                        category="dependency",
                        title=pkg,
                        content=line,
                        confidence=1.0,
                        source=filename,
                        relevance=1.0
                    ))

        elif filename == "package.json":
            try:
                data = json.loads(content)
                for dep_type in ['dependencies', 'devDependencies']:
                    for pkg, version in data.get(dep_type, {}).items():
                        findings.append(ResearchFinding(
                            category="dependency",
                            title=pkg,
                            content=f"{pkg}@{version} ({dep_type})",
                            confidence=1.0,
                            source=filename,
                            relevance=1.0
                        ))
            except json.JSONDecodeError:
                pass

        return findings

    def _detect_patterns(self, content: str, file_path: Path) -> Dict[str, int]:
        """Detect code patterns in content."""
        patterns = {}

        # Class definitions
        classes = re.findall(r'class\s+(\w+)', content)
        if classes:
            patterns['class_definitions'] = len(classes)

        # Async functions
        async_funcs = re.findall(r'async\s+def\s+', content)
        if async_funcs:
            patterns['async_functions'] = len(async_funcs)

        # Decorators
        decorators = re.findall(r'@\w+', content)
        if decorators:
            patterns['decorators'] = len(decorators)

        # Dataclasses
        if '@dataclass' in content:
            patterns['dataclasses'] = content.count('@dataclass')

        # Type hints
        type_hints = re.findall(r'->\s*\w+', content)
        if type_hints:
            patterns['type_hints'] = len(type_hints)

        # Exception handling
        try_blocks = content.count('try:')
        if try_blocks:
            patterns['exception_handling'] = try_blocks

        return patterns

    def _generate_summary(self, query: str, findings: List[ResearchFinding]) -> str:
        """Generate summary from findings."""
        if not findings:
            return f"No results found for: {query}"

        categories = {}
        for f in findings:
            categories[f.category] = categories.get(f.category, 0) + 1

        category_str = ", ".join(f"{k}: {v}" for k, v in categories.items())
        return f"Found {len(findings)} results for '{query}'. Categories: {category_str}"

    def _generate_doc_summary(self, query: str, findings: List[ResearchFinding]) -> str:
        """Generate documentation summary."""
        if not findings:
            return f"No documentation found for: {query}"

        sources = set(f.source for f in findings if f.source)
        return f"Found {len(findings)} relevant sections across {len(sources)} files"

    def _generate_recommendations(self, query: str, findings: List[ResearchFinding]) -> List[str]:
        """Generate recommendations based on findings."""
        recs = []

        if not findings:
            recs.append(f"Consider broadening search terms for '{query}'")
            return recs

        # Recommend files with most findings
        file_counts = {}
        for f in findings:
            if f.source:
                file_counts[f.source] = file_counts.get(f.source, 0) + 1

        if file_counts:
            top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            for file, count in top_files:
                recs.append(f"Review {file} ({count} matches)")

        return recs

    def _compute_checksum(self, result: ResearchResult) -> str:
        """Compute deterministic checksum of result."""
        result_str = json.dumps(result.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(result_str.encode()).hexdigest()[:16]


__all__ = ['ResearchAgent', 'ResearchResult', 'ResearchFinding', 'ResearchType']
