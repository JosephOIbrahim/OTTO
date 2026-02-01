"""
Substrate Integrity Verification
================================

Advanced integrity checking for cognitive substrate configuration.

Features:
- Merkle tree for efficient partial verification
- Schema validation for configuration files
- Tamper detection with detailed reporting
- Root hash for quick full-substrate verification

ThinkingMachines [He2025] Compliance:
- FIXED hash algorithm: SHA-256
- DETERMINISTIC tree construction (sorted paths)
- BOUNDED operations

Usage:
    from otto.substrate.integrity import SubstrateIntegrity

    integrity = SubstrateIntegrity(otto_dir)

    # Get root hash (for quick comparison)
    root_hash = integrity.compute_root_hash()

    # Verify specific configuration
    if integrity.verify_config("routing/expert_weights.json"):
        print("Config is valid")

    # Full integrity report
    report = integrity.full_verification()
    if not report.is_valid:
        print(f"Issues: {report.issues}")
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Configuration schemas for validation
CONFIG_SCHEMAS = {
    "routing/expert_weights.json": {
        "type": "object",
        "required_keys": ["validator", "scaffolder", "restorer", "refocuser",
                         "celebrator", "socratic", "direct"],
        "value_range": (0.0, 1.0),
    },
    "routing/expert_priorities.json": {
        "type": "object",
        "required_keys": ["validator", "scaffolder", "restorer", "refocuser",
                         "celebrator", "socratic", "direct"],
        "value_type": "int",
        "value_range": (1, 7),
    },
    "config/safety_floors.json": {
        "type": "object",
        "required_keys": ["validator", "restorer"],
        "value_range": (0.05, 0.5),  # Safety floors must be meaningful
    },
    "config/burnout_thresholds.json": {
        "type": "object",
        "required_keys": ["green", "yellow", "orange", "red"],
    },
}

# Safety constraints that must NEVER be violated
SAFETY_CONSTRAINTS = {
    "config/safety_floors.json": {
        "validator": {"min": 0.10},   # Validator must always be available
        "restorer": {"min": 0.08},    # Restorer must always be available
    },
    "routing/expert_priorities.json": {
        "validator": {"value": 1},     # Validator MUST be priority 1
    },
}


# =============================================================================
# Exceptions
# =============================================================================

class IntegrityVerificationError(Exception):
    """Base exception for integrity verification."""
    pass


class SchemaValidationError(IntegrityVerificationError):
    """Raised when configuration doesn't match schema."""
    pass


class SafetyConstraintViolation(IntegrityVerificationError):
    """Raised when safety constraints are violated."""
    pass


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class MerkleNode:
    """Node in the Merkle tree."""
    hash: str
    path: Optional[str] = None  # File path (only for leaf nodes)
    left: Optional["MerkleNode"] = None
    right: Optional["MerkleNode"] = None

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node."""
        return self.left is None and self.right is None


@dataclass
class VerificationIssue:
    """A verification issue found during integrity check."""
    severity: str  # "critical", "warning", "info"
    category: str  # "schema", "safety", "hash", "missing"
    path: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "severity": self.severity,
            "category": self.category,
            "path": self.path,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class IntegrityReport:
    """Full integrity verification report."""
    is_valid: bool
    root_hash: str
    verified_files: int
    issues: List[VerificationIssue] = field(default_factory=list)
    critical_count: int = 0
    warning_count: int = 0
    timestamp: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "root_hash": self.root_hash,
            "verified_files": self.verified_files,
            "issues": [i.to_dict() for i in self.issues],
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Substrate Integrity
# =============================================================================

class SubstrateIntegrity:
    """
    Verifies integrity of cognitive substrate configuration.

    Provides:
    - Merkle tree construction for efficient verification
    - Schema validation for configuration files
    - Safety constraint checking
    - Tamper detection
    """

    def __init__(self, otto_dir: Path = None):
        """
        Initialize integrity verifier.

        Args:
            otto_dir: Base OTTO directory (default: ~/.otto)
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"
        self.substrate_dir = self.otto_dir / "substrate"

        # Cache for computed hashes
        self._hash_cache: Dict[str, str] = {}
        self._merkle_root: Optional[MerkleNode] = None

    # =========================================================================
    # Hash Operations
    # =========================================================================

    def compute_file_hash(self, file_path: Path) -> str:
        """
        Compute SHA-256 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            Hex-encoded hash string
        """
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def compute_content_hash(self, content: bytes) -> str:
        """
        Compute SHA-256 hash of content.

        Args:
            content: Bytes to hash

        Returns:
            Hex-encoded hash string
        """
        return hashlib.sha256(content).hexdigest()

    def compute_node_hash(self, left_hash: str, right_hash: str) -> str:
        """
        Compute hash of two child hashes for Merkle tree.

        Args:
            left_hash: Left child hash
            right_hash: Right child hash

        Returns:
            Combined hash
        """
        combined = (left_hash + right_hash).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    # =========================================================================
    # Merkle Tree
    # =========================================================================

    def build_merkle_tree(self, refresh: bool = False) -> MerkleNode:
        """
        Build Merkle tree from substrate files.

        Args:
            refresh: Force rebuild even if cached

        Returns:
            Root node of Merkle tree
        """
        if self._merkle_root is not None and not refresh:
            return self._merkle_root

        # Collect all substrate files (sorted for determinism)
        files = sorted(self._collect_substrate_files())

        if not files:
            # Empty tree
            self._merkle_root = MerkleNode(
                hash=hashlib.sha256(b"empty").hexdigest()
            )
            return self._merkle_root

        # Create leaf nodes
        leaves = []
        for file_path in files:
            try:
                file_hash = self.compute_file_hash(file_path)
                rel_path = str(file_path.relative_to(self.substrate_dir))
                self._hash_cache[rel_path] = file_hash
                leaves.append(MerkleNode(hash=file_hash, path=rel_path))
            except Exception as e:
                logger.warning(f"Failed to hash {file_path}: {e}")

        # Build tree bottom-up
        self._merkle_root = self._build_tree_level(leaves)
        return self._merkle_root

    def _build_tree_level(self, nodes: List[MerkleNode]) -> MerkleNode:
        """Build one level of the Merkle tree."""
        if len(nodes) == 0:
            return MerkleNode(hash=hashlib.sha256(b"empty").hexdigest())

        if len(nodes) == 1:
            return nodes[0]

        # Pair nodes and create parent level
        parents = []
        for i in range(0, len(nodes), 2):
            left = nodes[i]
            right = nodes[i + 1] if i + 1 < len(nodes) else left  # Duplicate if odd

            parent_hash = self.compute_node_hash(left.hash, right.hash)
            parents.append(MerkleNode(hash=parent_hash, left=left, right=right))

        return self._build_tree_level(parents)

    def _collect_substrate_files(self) -> List[Path]:
        """Collect all files in substrate directory."""
        files = []
        if self.substrate_dir.exists():
            for path in self.substrate_dir.rglob("*"):
                if path.is_file():
                    # Skip signature files
                    if not path.suffix == ".sig":
                        files.append(path)
        return files

    def compute_root_hash(self, refresh: bool = False) -> str:
        """
        Compute root hash of substrate Merkle tree.

        This provides a single hash that represents the entire substrate
        configuration. If any file changes, the root hash changes.

        Args:
            refresh: Force recomputation

        Returns:
            Root hash string
        """
        root = self.build_merkle_tree(refresh)
        return root.hash

    def get_proof(self, file_path: str) -> List[Tuple[str, str]]:
        """
        Get Merkle proof for a specific file.

        Args:
            file_path: Relative path within substrate directory

        Returns:
            List of (sibling_hash, direction) tuples
        """
        root = self.build_merkle_tree()
        proof = []

        def find_path(node: MerkleNode, target: str) -> bool:
            if node.is_leaf:
                return node.path == target

            if node.left and find_path(node.left, target):
                if node.right:
                    proof.append((node.right.hash, "right"))
                return True

            if node.right and find_path(node.right, target):
                if node.left:
                    proof.append((node.left.hash, "left"))
                return True

            return False

        find_path(root, file_path)
        return proof

    # =========================================================================
    # Schema Validation
    # =========================================================================

    def validate_schema(self, config_path: str, content: Dict[str, Any]) -> List[VerificationIssue]:
        """
        Validate configuration against schema.

        Args:
            config_path: Relative config path
            content: Parsed JSON content

        Returns:
            List of validation issues
        """
        issues = []

        if config_path not in CONFIG_SCHEMAS:
            return issues  # No schema defined

        schema = CONFIG_SCHEMAS[config_path]

        # Check type
        if schema.get("type") == "object" and not isinstance(content, dict):
            issues.append(VerificationIssue(
                severity="critical",
                category="schema",
                path=config_path,
                message=f"Expected object, got {type(content).__name__}",
            ))
            return issues

        # Check required keys
        if "required_keys" in schema:
            for key in schema["required_keys"]:
                if key not in content:
                    issues.append(VerificationIssue(
                        severity="critical",
                        category="schema",
                        path=config_path,
                        message=f"Missing required key: {key}",
                    ))

        # Check value range
        if "value_range" in schema:
            min_val, max_val = schema["value_range"]
            for key, value in content.items():
                if isinstance(value, (int, float)):
                    if value < min_val or value > max_val:
                        issues.append(VerificationIssue(
                            severity="warning",
                            category="schema",
                            path=config_path,
                            message=f"Value out of range for {key}: {value} (expected {min_val}-{max_val})",
                            details={"key": key, "value": value, "range": [min_val, max_val]},
                        ))

        return issues

    # =========================================================================
    # Safety Constraint Checking
    # =========================================================================

    def check_safety_constraints(self, config_path: str, content: Dict[str, Any]) -> List[VerificationIssue]:
        """
        Check that safety constraints are not violated.

        Args:
            config_path: Relative config path
            content: Parsed JSON content

        Returns:
            List of safety violations (always critical)
        """
        issues = []

        if config_path not in SAFETY_CONSTRAINTS:
            return issues

        constraints = SAFETY_CONSTRAINTS[config_path]

        for key, rules in constraints.items():
            if key not in content:
                continue

            value = content[key]

            # Check minimum
            if "min" in rules:
                if value < rules["min"]:
                    issues.append(VerificationIssue(
                        severity="critical",
                        category="safety",
                        path=config_path,
                        message=f"SAFETY VIOLATION: {key} below minimum ({value} < {rules['min']})",
                        details={"key": key, "value": value, "min": rules["min"]},
                    ))

            # Check maximum
            if "max" in rules:
                if value > rules["max"]:
                    issues.append(VerificationIssue(
                        severity="critical",
                        category="safety",
                        path=config_path,
                        message=f"SAFETY VIOLATION: {key} above maximum ({value} > {rules['max']})",
                        details={"key": key, "value": value, "max": rules["max"]},
                    ))

            # Check exact value
            if "value" in rules:
                if value != rules["value"]:
                    issues.append(VerificationIssue(
                        severity="critical",
                        category="safety",
                        path=config_path,
                        message=f"SAFETY VIOLATION: {key} must be {rules['value']}, got {value}",
                        details={"key": key, "value": value, "expected": rules["value"]},
                    ))

        return issues

    # =========================================================================
    # Full Verification
    # =========================================================================

    def verify_config(self, config_path: str) -> Tuple[bool, List[VerificationIssue]]:
        """
        Verify a specific configuration file.

        Args:
            config_path: Relative path within substrate directory

        Returns:
            Tuple of (is_valid, issues)
        """
        file_path = self.substrate_dir / config_path
        issues = []

        # Check existence
        if not file_path.exists():
            # Check for encrypted version
            encrypted_path = file_path.with_suffix(file_path.suffix + ".enc")
            if not encrypted_path.exists():
                issues.append(VerificationIssue(
                    severity="warning",
                    category="missing",
                    path=config_path,
                    message=f"Configuration file not found: {config_path}",
                ))
                return False, issues
            # Can't verify encrypted file content without key
            return True, issues

        # Parse and validate JSON configs
        if file_path.suffix == ".json":
            try:
                content = json.loads(file_path.read_text())

                # Schema validation
                issues.extend(self.validate_schema(config_path, content))

                # Safety constraint checking
                issues.extend(self.check_safety_constraints(config_path, content))

            except json.JSONDecodeError as e:
                issues.append(VerificationIssue(
                    severity="critical",
                    category="schema",
                    path=config_path,
                    message=f"Invalid JSON: {e}",
                ))

        # Check for critical issues
        has_critical = any(i.severity == "critical" for i in issues)
        return not has_critical, issues

    def full_verification(self) -> IntegrityReport:
        """
        Perform full integrity verification of substrate.

        Returns:
            Complete verification report
        """
        import time

        issues = []
        verified_count = 0

        # Build/refresh Merkle tree
        root = self.build_merkle_tree(refresh=True)

        # Verify all configuration files
        # [He2025] Use sorted() for deterministic iteration order
        for config_path in sorted(CONFIG_SCHEMAS.keys()):
            is_valid, config_issues = self.verify_config(config_path)
            issues.extend(config_issues)
            verified_count += 1

        # Check safety constraints
        # [He2025] Use sorted() for deterministic iteration order
        for config_path in sorted(SAFETY_CONSTRAINTS.keys()):
            file_path = self.substrate_dir / config_path
            if file_path.exists():
                try:
                    content = json.loads(file_path.read_text())
                    safety_issues = self.check_safety_constraints(config_path, content)
                    issues.extend(safety_issues)
                except Exception:
                    pass

        # Count severity levels
        critical_count = sum(1 for i in issues if i.severity == "critical")
        warning_count = sum(1 for i in issues if i.severity == "warning")

        return IntegrityReport(
            is_valid=critical_count == 0,
            root_hash=root.hash,
            verified_files=verified_count,
            issues=issues,
            critical_count=critical_count,
            warning_count=warning_count,
            timestamp=int(time.time()),
        )

    # =========================================================================
    # Tamper Detection
    # =========================================================================

    def detect_tampering(self, expected_root_hash: str) -> bool:
        """
        Quick tamper detection using root hash comparison.

        Args:
            expected_root_hash: Previously computed root hash

        Returns:
            True if tampering detected (hashes don't match)
        """
        current_hash = self.compute_root_hash(refresh=True)
        return current_hash != expected_root_hash

    def get_changed_files(self, previous_hashes: Dict[str, str]) -> Dict[str, str]:
        """
        Find files that have changed since last verification.

        Args:
            previous_hashes: Dict of path -> hash from previous verification

        Returns:
            Dict of changed files with change type (added, modified, removed)
        """
        self.build_merkle_tree(refresh=True)
        changes = {}

        current_paths = set(self._hash_cache.keys())
        previous_paths = set(previous_hashes.keys())

        # Added files
        for path in current_paths - previous_paths:
            changes[path] = "added"

        # Removed files
        for path in previous_paths - current_paths:
            changes[path] = "removed"

        # Modified files
        for path in current_paths & previous_paths:
            if self._hash_cache[path] != previous_hashes[path]:
                changes[path] = "modified"

        return changes


# =============================================================================
# Factory Function
# =============================================================================

def create_integrity_verifier(otto_dir: Path = None) -> SubstrateIntegrity:
    """Factory function to create SubstrateIntegrity."""
    return SubstrateIntegrity(otto_dir)


__all__ = [
    "SubstrateIntegrity",
    "IntegrityReport",
    "VerificationIssue",
    "MerkleNode",
    "IntegrityVerificationError",
    "SchemaValidationError",
    "SafetyConstraintViolation",
    "CONFIG_SCHEMAS",
    "SAFETY_CONSTRAINTS",
    "create_integrity_verifier",
]
