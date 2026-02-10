"""
Approval Gate System
====================

Per spec: Three approval categories control agent autonomy.
- CONSTITUTIONAL: Always require explicit approval (delete, send, pay)
- TRUST: Can earn auto-approval over time (read, search, summarize)
- SAFE: Auto-approved (log, format, parse)

Determinism:
- Deterministic policy evaluation
- Fixed trust threshold (0.8)
- No timing-based decisions
- Sorted iteration for reproducibility

Reference: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

import asyncio
import functools
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional, Set, TypeVar, Awaitable

logger = logging.getLogger(__name__)


# === Constants (Fixed) ===

APPROVAL_SEED: Final[int] = 0xADD70BAD
APPROVAL_VERSION: Final[str] = "1.0.0"
TRUST_THRESHOLD: Final[float] = 0.8  # Trust score needed for auto-approval
TRUST_DECAY_DAYS: Final[int] = 30  # Trust decays after this many days
MIN_APPROVALS_FOR_TRUST: Final[int] = 5  # Minimum approvals before trust can be earned
DEFAULT_TIMEOUT_SECONDS: Final[float] = 60.0
COGNITIVE_TILE_SIZE: Final[int] = 32


class ApprovalCategory(str, Enum):
    """
    Approval categories per spec.

    CONSTITUTIONAL: ALWAYS requires explicit user approval.
    TRUST: Can earn auto-approval through consistent safe usage.
    SAFE: Auto-approved (no user interaction needed).
    """

    CONSTITUTIONAL = "constitutional"
    TRUST = "trust"
    SAFE = "safe"

    @property
    def requires_approval(self) -> bool:
        """Check if category requires approval."""
        return self != ApprovalCategory.SAFE


class ApprovalDecision(str, Enum):
    """Possible approval outcomes."""

    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    AUTO_APPROVED = "auto_approved"
    AUTO_DENIED = "auto_denied"

    @property
    def is_approved(self) -> bool:
        """Check if decision permits the action."""
        return self in (ApprovalDecision.APPROVED, ApprovalDecision.AUTO_APPROVED)


class ApprovalError(Exception):
    """Base exception for approval operations."""
    pass


class ApprovalDeniedError(ApprovalError):
    """Raised when approval is denied."""
    pass


class ApprovalTimeoutError(ApprovalError):
    """Raised when approval times out."""
    pass


@dataclass
class ApprovalPolicy:
    """
    Policy for a specific action type.

    Policies define:
    - Category (CONSTITUTIONAL, TRUST, SAFE)
    - Trust requirements
    - Auto-approval conditions
    """

    action: str
    """Action identifier (e.g., 'email.send', 'calendar.read')."""

    category: ApprovalCategory
    """Approval category."""

    description: str
    """Human-readable description of what this action does."""

    # Trust configuration
    trust_eligible: bool = False
    """Whether this action can earn trust (TRUST category only)."""

    trust_threshold: float = TRUST_THRESHOLD
    """Trust score needed for auto-approval."""

    # Metadata
    service: Optional[str] = None
    """Service this policy belongs to."""

    risk_level: str = "medium"
    """Risk level: low, medium, high, critical."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action": self.action,
            "category": self.category.value,
            "description": self.description,
            "trust_eligible": self.trust_eligible,
            "trust_threshold": self.trust_threshold,
            "service": self.service,
            "risk_level": self.risk_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalPolicy":
        """Deserialize from dictionary."""
        return cls(
            action=data["action"],
            category=ApprovalCategory(data["category"]),
            description=data["description"],
            trust_eligible=data.get("trust_eligible", False),
            trust_threshold=data.get("trust_threshold", TRUST_THRESHOLD),
            service=data.get("service"),
            risk_level=data.get("risk_level", "medium"),
        )


@dataclass
class ApprovalRequest:
    """
    Request for approval.

    Contains all information needed for user to make informed decision.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    """Unique request ID."""

    action: str = ""
    """Action being requested."""

    actor: str = ""
    """Who is requesting (agent ID, service)."""

    service: Optional[str] = None
    """Service involved."""

    resource: Optional[str] = None
    """Resource being accessed/modified."""

    details: Dict[str, Any] = field(default_factory=dict)
    """Additional context for user."""

    policy: Optional[ApprovalPolicy] = None
    """Policy for this action."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When request was created."""

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    """How long to wait for response."""

    # Outcome (filled after decision)
    decision: Optional[ApprovalDecision] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    reason: Optional[str] = None

    def __post_init__(self):
        """Generate checksum for integrity."""
        self._checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        """Compute deterministic checksum."""
        data = f"{self.id}|{self.action}|{self.actor}|{self.service}|{self.resource}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def is_expired(self) -> bool:
        """Check if request has timed out."""
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        return elapsed > self.timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "actor": self.actor,
            "service": self.service,
            "resource": self.resource,
            "details": self.details,
            "policy": self.policy.to_dict() if self.policy else None,
            "timestamp": self.timestamp.isoformat(),
            "timeout_seconds": self.timeout_seconds,
            "decision": self.decision.value if self.decision else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "reason": self.reason,
        }


@dataclass
class TrustRecord:
    """
    Trust record for an action/actor combination.

    Trust is earned through consistent safe usage.
    """

    action: str
    actor: str
    approval_count: int = 0
    denial_count: int = 0
    last_approval: Optional[datetime] = None
    last_denial: Optional[datetime] = None
    trust_score: float = 0.0

    def update_trust(self) -> None:
        """
        Recalculate trust score.

        Formula: trust = approvals / (approvals + denials) * time_factor
        Deterministic calculation, no randomness.
        """
        total = self.approval_count + self.denial_count
        if total < MIN_APPROVALS_FOR_TRUST:
            self.trust_score = 0.0
            return

        # Base trust from approval rate
        base_trust = self.approval_count / total

        # Time decay - trust decays if not used
        time_factor = 1.0
        if self.last_approval:
            days_since = (datetime.now() - self.last_approval).days
            if days_since > TRUST_DECAY_DAYS:
                decay = 0.5 ** ((days_since - TRUST_DECAY_DAYS) / TRUST_DECAY_DAYS)
                time_factor = max(0.1, decay)

        self.trust_score = base_trust * time_factor

    def record_approval(self) -> None:
        """Record an approval."""
        self.approval_count += 1
        self.last_approval = datetime.now()
        self.update_trust()

    def record_denial(self) -> None:
        """Record a denial."""
        self.denial_count += 1
        self.last_denial = datetime.now()
        self.update_trust()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action": self.action,
            "actor": self.actor,
            "approval_count": self.approval_count,
            "denial_count": self.denial_count,
            "last_approval": self.last_approval.isoformat() if self.last_approval else None,
            "last_denial": self.last_denial.isoformat() if self.last_denial else None,
            "trust_score": self.trust_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrustRecord":
        """Deserialize from dictionary."""
        record = cls(
            action=data["action"],
            actor=data["actor"],
            approval_count=data.get("approval_count", 0),
            denial_count=data.get("denial_count", 0),
            last_approval=datetime.fromisoformat(data["last_approval"]) if data.get("last_approval") else None,
            last_denial=datetime.fromisoformat(data["last_denial"]) if data.get("last_denial") else None,
            trust_score=data.get("trust_score", 0.0),
        )
        return record


class ApprovalGate:
    """
    Central approval gate manager.

    Responsibilities:
    - Policy management
    - Trust tracking
    - Approval request handling
    - Audit integration

    Determinism:
    - Deterministic policy evaluation
    - Fixed thresholds
    - Sorted iteration
    - No timing randomness
    """

    def __init__(
        self,
        otto_dir: Optional[Path] = None,
        approval_handler: Optional[Callable[[ApprovalRequest], Awaitable[bool]]] = None,
    ):
        """
        Initialize approval gate.

        Args:
            otto_dir: Base OTTO directory
            approval_handler: Async function to get user approval
        """
        self.otto_dir = otto_dir or Path.home() / ".otto"
        self._approval_dir = self.otto_dir / "approvals"
        self._approval_dir.mkdir(parents=True, exist_ok=True)

        # Approval handler (UI callback)
        self._approval_handler = approval_handler

        # Policy registry
        self._policies: Dict[str, ApprovalPolicy] = {}

        # Trust records (action:actor -> TrustRecord)
        self._trust: Dict[str, TrustRecord] = {}

        # Pending requests
        self._pending: Dict[str, ApprovalRequest] = {}

        # Request history
        self._history: List[ApprovalRequest] = []

        # Load state
        self._load()
        self._register_default_policies()

    def _register_default_policies(self) -> None:
        """Register default approval policies per spec."""
        # CONSTITUTIONAL - Always require approval
        constitutional_actions = [
            ("email.send", "Send email to external recipient"),
            ("calendar.delete", "Delete calendar event"),
            ("file.delete", "Delete file permanently"),
            ("payment.process", "Process payment"),
            ("credential.store", "Store new credential"),
            ("data.export", "Export personal data"),
            ("setting.change_critical", "Change critical system setting"),
        ]

        for action, desc in constitutional_actions:
            self.register_policy(ApprovalPolicy(
                action=action,
                category=ApprovalCategory.CONSTITUTIONAL,
                description=desc,
                trust_eligible=False,
                risk_level="critical",
            ))

        # TRUST - Can earn auto-approval
        trust_actions = [
            ("calendar.read", "Read calendar events"),
            ("email.read", "Read emails"),
            ("file.read", "Read file contents"),
            ("search.execute", "Execute search query"),
            ("task.read", "Read tasks"),
            ("notion.read", "Read Notion pages"),
            ("repo.read", "Read repository contents"),
        ]

        for action, desc in trust_actions:
            self.register_policy(ApprovalPolicy(
                action=action,
                category=ApprovalCategory.TRUST,
                description=desc,
                trust_eligible=True,
                risk_level="medium",
            ))

        # SAFE - Auto-approved
        safe_actions = [
            ("log.write", "Write to log"),
            ("format.text", "Format text"),
            ("parse.data", "Parse data structure"),
            ("cache.read", "Read from cache"),
            ("cache.write", "Write to cache"),
            ("metric.record", "Record metric"),
        ]

        for action, desc in safe_actions:
            self.register_policy(ApprovalPolicy(
                action=action,
                category=ApprovalCategory.SAFE,
                description=desc,
                trust_eligible=False,
                risk_level="low",
            ))

    def _load(self) -> None:
        """Load trust records and history."""
        # Load trust records
        trust_file = self._approval_dir / "trust.json"
        if trust_file.exists():
            try:
                with open(trust_file) as f:
                    data = json.load(f)
                for key in sorted(data.keys()):  # Sorted
                    self._trust[key] = TrustRecord.from_dict(data[key])
            except Exception as e:
                logger.error(f"Failed to load trust records: {e}")

    def _save_trust(self) -> None:
        """Save trust records."""
        trust_file = self._approval_dir / "trust.json"
        data = {k: v.to_dict() for k, v in sorted(self._trust.items())}
        with open(trust_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _get_trust_key(self, action: str, actor: str) -> str:
        """Get deterministic trust key."""
        return f"{action}:{actor}"

    def _record_approval_to_memory(self, action: str, actor: str, approved: bool) -> None:
        """
        Record approval/denial to memory system (pheromone trails).

        Deterministic trail deposits for trust tracking.
        Trail strength accumulates with approvals, decays with denials.

        Args:
            action: Action that was approved/denied
            actor: Who requested approval
            approved: Whether it was approved
        """
        try:
            from ..memory import Episode, Outcome, get_memory

            memory = get_memory()

            # Deposit trail for this action+actor combination
            outcome = Outcome.SUCCESS if approved else Outcome.REJECTED
            trail_action = f"{action}:{actor}"

            memory.deposit_trail(action=trail_action, outcome=outcome)

            # Also record as episode for history
            episode = Episode(
                type=f"approval.{'granted' if approved else 'denied'}",
                data={
                    "action": action,
                    "actor": actor,
                    "decision": "approved" if approved else "denied",
                },
                outcome=outcome,
                actor=actor,
                service="approval_gate",
            )
            memory.record_episode(episode)

            logger.debug(f"Approval recorded to memory: {trail_action} -> {outcome}")

        except Exception as e:
            logger.debug(f"Memory recording skipped: {e}")

    # =========================================================================
    # Policy Management
    # =========================================================================

    def register_policy(self, policy: ApprovalPolicy) -> None:
        """Register an approval policy."""
        self._policies[policy.action] = policy
        logger.debug(f"Registered policy: {policy.action} ({policy.category.value})")

    def get_policy(self, action: str) -> Optional[ApprovalPolicy]:
        """Get policy for an action."""
        return self._policies.get(action)

    def list_policies(self) -> List[ApprovalPolicy]:
        """List all policies (sorted by action)."""
        return [self._policies[k] for k in sorted(self._policies.keys())]

    # =========================================================================
    # Trust Management
    # =========================================================================

    def get_trust(self, action: str, actor: str) -> float:
        """
        Get trust score for action/actor combination.

        Deterministic - uses trail strength from memory.
        Falls back to local trust records if memory unavailable.
        """
        # Try memory-based trust (pheromone trail strength)
        try:
            from ..memory import get_memory
            memory = get_memory()
            trail_strength = memory.follow_trail(f"{action}:{actor}")
            if trail_strength.strength > 0:
                return trail_strength.strength
        except Exception:
            pass  # Fall back to local trust

        # Fall back to local trust records
        key = self._get_trust_key(action, actor)
        if key in self._trust:
            return self._trust[key].trust_score
        return 0.0

    def has_trust(self, action: str, actor: str) -> bool:
        """
        Check if action/actor has sufficient trust for auto-approval.

        Uses trail strength (>= 0.8) for auto-approval.
        """
        policy = self.get_policy(action)
        if not policy or not policy.trust_eligible:
            return False

        trust = self.get_trust(action, actor)
        return trust >= policy.trust_threshold

    # =========================================================================
    # Approval Flow
    # =========================================================================

    async def request_approval(
        self,
        action: str,
        actor: str,
        service: Optional[str] = None,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> ApprovalDecision:
        """
        Request approval for an action.

        Args:
            action: Action being requested
            actor: Who is requesting
            service: Service involved
            resource: Resource being accessed
            details: Additional context
            timeout: How long to wait

        Returns:
            ApprovalDecision indicating outcome

        Raises:
            ApprovalDeniedError: If denied
            ApprovalTimeoutError: If timeout
        """
        policy = self.get_policy(action)

        # Create request
        request = ApprovalRequest(
            action=action,
            actor=actor,
            service=service,
            resource=resource,
            details=details or {},
            policy=policy,
            timeout_seconds=timeout,
        )

        # Evaluate policy
        if policy is None:
            # Unknown action - default to TRUST category
            policy = ApprovalPolicy(
                action=action,
                category=ApprovalCategory.TRUST,
                description=f"Unknown action: {action}",
            )
            request.policy = policy

        # Check category
        if policy.category == ApprovalCategory.SAFE:
            # Auto-approve safe actions
            decision = ApprovalDecision.AUTO_APPROVED
            request.decision = decision
            request.decided_at = datetime.now()
            request.decided_by = "system"
            request.reason = "Safe action (auto-approved)"
            self._history.append(request)
            return decision

        if policy.category == ApprovalCategory.TRUST:
            # Check if trusted
            if self.has_trust(action, actor):
                decision = ApprovalDecision.AUTO_APPROVED
                request.decision = decision
                request.decided_at = datetime.now()
                request.decided_by = "system"
                request.reason = f"Trusted (score: {self.get_trust(action, actor):.2f})"
                self._history.append(request)

                # Record for trust tracking (memory + local)
                self._record_approval_to_memory(action, actor, approved=True)

                key = self._get_trust_key(action, actor)
                if key not in self._trust:
                    self._trust[key] = TrustRecord(action=action, actor=actor)
                self._trust[key].record_approval()
                self._save_trust()

                return decision

        # Need explicit approval
        self._pending[request.id] = request

        try:
            # Get user decision
            if self._approval_handler:
                approved = await asyncio.wait_for(
                    self._approval_handler(request),
                    timeout=timeout
                )
            else:
                # No handler - default deny for safety
                logger.warning(f"No approval handler - denying {action}")
                approved = False

            # Record decision
            if approved:
                decision = ApprovalDecision.APPROVED
                request.reason = "User approved"

                # Update trust for TRUST category (memory + local)
                if policy.category == ApprovalCategory.TRUST:
                    self._record_approval_to_memory(action, actor, approved=True)

                    key = self._get_trust_key(action, actor)
                    if key not in self._trust:
                        self._trust[key] = TrustRecord(action=action, actor=actor)
                    self._trust[key].record_approval()
                    self._save_trust()
            else:
                decision = ApprovalDecision.DENIED
                request.reason = "User denied"

                # Update trust (memory + local)
                if policy.category == ApprovalCategory.TRUST:
                    self._record_approval_to_memory(action, actor, approved=False)

                    key = self._get_trust_key(action, actor)
                    if key not in self._trust:
                        self._trust[key] = TrustRecord(action=action, actor=actor)
                    self._trust[key].record_denial()
                    self._save_trust()

        except asyncio.TimeoutError:
            decision = ApprovalDecision.TIMEOUT
            request.reason = f"Timeout after {timeout}s"

        # Finalize request
        request.decision = decision
        request.decided_at = datetime.now()
        request.decided_by = "user"

        # Move to history
        del self._pending[request.id]
        self._history.append(request)

        # Audit logging
        from .audit import get_audit_log, AuditAction

        audit = get_audit_log()
        audit.log(
            action=AuditAction.APPROVAL_GRANTED if decision.is_approved else AuditAction.APPROVAL_DENIED,
            actor=actor,
            service=service,
            resource=resource,
            details={"approval_id": request.id, "decision": decision.value},
            success=decision.is_approved,
            approval_id=request.id,
        )

        # Raise if not approved
        if decision == ApprovalDecision.DENIED:
            raise ApprovalDeniedError(f"Approval denied for {action}")
        if decision == ApprovalDecision.TIMEOUT:
            raise ApprovalTimeoutError(f"Approval timed out for {action}")

        return decision

    def get_pending(self) -> List[ApprovalRequest]:
        """Get pending approval requests."""
        # Sorted by timestamp
        return sorted(
            self._pending.values(),
            key=lambda r: r.timestamp
        )

    def get_history(
        self,
        limit: int = 100,
        action: Optional[str] = None,
        actor: Optional[str] = None,
    ) -> List[ApprovalRequest]:
        """Get approval history."""
        results = []
        for request in reversed(self._history):
            if action and request.action != action:
                continue
            if actor and request.actor != actor:
                continue
            results.append(request)
            if len(results) >= limit:
                break
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get approval statistics."""
        total = len(self._history)
        approved = sum(1 for r in self._history if r.decision and r.decision.is_approved)
        denied = sum(1 for r in self._history if r.decision == ApprovalDecision.DENIED)
        timeout = sum(1 for r in self._history if r.decision == ApprovalDecision.TIMEOUT)

        return {
            "total_requests": total,
            "approved": approved,
            "denied": denied,
            "timeout": timeout,
            "approval_rate": approved / total if total > 0 else 0,
            "pending_count": len(self._pending),
            "policy_count": len(self._policies),
            "trust_records": len(self._trust),
        }


# === Module-level Singleton ===

_gate: Optional[ApprovalGate] = None


def get_approval_gate(
    otto_dir: Optional[Path] = None,
    approval_handler: Optional[Callable[[ApprovalRequest], Awaitable[bool]]] = None,
) -> ApprovalGate:
    """Get or create the approval gate singleton."""
    global _gate
    if _gate is None:
        _gate = ApprovalGate(otto_dir=otto_dir, approval_handler=approval_handler)
    return _gate


# === Decorator for requiring approval ===

F = TypeVar("F", bound=Callable[..., Any])


def requires_approval(
    action: str,
    actor: str = "system",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Callable[[F], F]:
    """
    Decorator that requires approval before function execution.

    Usage:
        @requires_approval("email.send", actor="agent-123")
        async def send_email(to: str, subject: str, body: str):
            ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            gate = get_approval_gate()

            # Extract details for approval request
            details = {
                "function": func.__name__,
                "args_count": len(args),
                "kwargs_keys": list(kwargs.keys()),
            }

            # Request approval
            await gate.request_approval(
                action=action,
                actor=actor,
                details=details,
                timeout=timeout,
            )

            # Approved - execute function
            return await func(*args, **kwargs)

        return wrapper  # type: ignore
    return decorator


__all__ = [
    "ApprovalGate",
    "ApprovalRequest",
    "ApprovalDecision",
    "ApprovalCategory",
    "ApprovalPolicy",
    "ApprovalError",
    "ApprovalDeniedError",
    "ApprovalTimeoutError",
    "get_approval_gate",
    "requires_approval",
]
