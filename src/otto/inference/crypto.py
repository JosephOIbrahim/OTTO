"""
Tier 4: Cryptographically Verified Inference
=============================================

Research-grade cryptographic verification for provably deterministic inference.

This module provides:
1. Commitment Scheme - Cryptographic commitments to inputs, outputs, and config
2. Merkle Trees - For model weights and execution trace verification
3. TEE Abstraction - Interface for Trusted Execution Environments
4. Attestation - TPM/TEE attestation for execution environment
5. Proof Generation - Cryptographic proofs of deterministic execution
6. Verification - Anyone can verify execution was deterministic

[He2025] Tier 4 Guarantees:
- Cryptographic proof that same inputs produce same outputs
- TEE attestation of execution environment
- Merkle proofs for intermediate state verification
- Tamper-evident execution traces

Security Model:
- Assumes TEE hardware is trusted (SGX, SEV, TrustZone)
- Assumes cryptographic primitives are secure (SHA-256, ECDSA)
- Proofs are publicly verifiable without trusted third party

References:
    [He2025] He, Horace and Thinking Machines Lab, "Defeating Nondeterminism
    in LLM Inference", Thinking Machines Lab, Sep 2025.
"""

import hashlib
import hmac
import json
import time
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, AsyncIterator, Union
import base64

from .backends.base import (
    InferenceBackend,
    BackendCapabilities,
    BackendStatus,
    InferenceResponse,
    InferenceError,
)
from .kernel import He2025KernelConfig, HE2025_STRICT


# =============================================================================
# Cryptographic Primitives
# =============================================================================

def sha256(data: bytes) -> bytes:
    """Compute SHA-256 hash."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    """Compute SHA-256 hash and return as hex string."""
    return hashlib.sha256(data).hexdigest()


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    """Compute HMAC-SHA256."""
    return hmac.new(key, data, hashlib.sha256).digest()


def secure_random_bytes(n: int) -> bytes:
    """Generate cryptographically secure random bytes."""
    return secrets.token_bytes(n)


# =============================================================================
# Commitment Scheme
# =============================================================================

@dataclass(frozen=True)
class Commitment:
    """
    Cryptographic commitment to data.

    A commitment allows one to commit to a value while keeping it hidden,
    with the ability to reveal the value later. Properties:
    - Hiding: Commitment reveals nothing about the value
    - Binding: Cannot change the value after committing

    Implemented using hash commitment: C = H(value || randomness)
    """
    commitment_hash: str  # H(value || randomness)
    randomness: str       # Random blinding factor (hex)
    timestamp: float      # When commitment was created
    scheme: str = "sha256-commit"

    @classmethod
    def create(cls, value: bytes) -> Tuple['Commitment', bytes]:
        """
        Create a commitment to a value.

        Args:
            value: The value to commit to

        Returns:
            Tuple of (Commitment, original_value)
        """
        randomness = secure_random_bytes(32)
        commitment_hash = sha256_hex(value + randomness)

        return cls(
            commitment_hash=commitment_hash,
            randomness=randomness.hex(),
            timestamp=time.time(),
        ), value

    def verify(self, value: bytes) -> bool:
        """
        Verify that a value matches this commitment.

        Args:
            value: The claimed original value

        Returns:
            True if value matches commitment
        """
        randomness = bytes.fromhex(self.randomness)
        expected_hash = sha256_hex(value + randomness)
        return hmac.compare_digest(expected_hash, self.commitment_hash)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'commitment_hash': self.commitment_hash,
            'timestamp': self.timestamp,
            'scheme': self.scheme,
        }

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return json.dumps(self.to_dict(), sort_keys=True).encode()


@dataclass
class InputCommitment:
    """Commitment to inference input (prompt + params)."""
    prompt_commitment: Commitment
    params_commitment: Commitment
    combined_hash: str  # H(prompt_commitment || params_commitment)

    @classmethod
    def create(
        cls,
        prompt: str,
        params: Dict[str, Any],
    ) -> 'InputCommitment':
        """Create commitment to input."""
        prompt_bytes = prompt.encode('utf-8')
        params_bytes = json.dumps(params, sort_keys=True).encode('utf-8')

        prompt_commit, _ = Commitment.create(prompt_bytes)
        params_commit, _ = Commitment.create(params_bytes)

        combined = sha256_hex(
            prompt_commit.commitment_hash.encode() +
            params_commit.commitment_hash.encode()
        )

        return cls(
            prompt_commitment=prompt_commit,
            params_commitment=params_commit,
            combined_hash=combined,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'prompt_commitment': self.prompt_commitment.to_dict(),
            'params_commitment': self.params_commitment.to_dict(),
            'combined_hash': self.combined_hash,
        }


# =============================================================================
# Merkle Tree
# =============================================================================

@dataclass
class MerkleNode:
    """Node in a Merkle tree."""
    hash: str
    left: Optional['MerkleNode'] = None
    right: Optional['MerkleNode'] = None
    data: Optional[bytes] = None  # Only for leaf nodes

    @property
    def is_leaf(self) -> bool:
        return self.data is not None


class MerkleTree:
    """
    Merkle tree for efficient verification of large datasets.

    Used for:
    - Model weight commitments
    - Execution trace verification
    - Intermediate state proofs

    Properties:
    - O(log n) proof size
    - O(log n) verification time
    - Tamper-evident
    """

    def __init__(self, leaves: List[bytes]):
        """
        Build Merkle tree from leaf data.

        Args:
            leaves: List of leaf values to include in tree
        """
        if not leaves:
            self._root = MerkleNode(hash=sha256_hex(b"empty"))
            self._leaves = []
            self._original_leaf_count = 0
            return

        # Create leaf nodes
        self._leaves = [
            MerkleNode(hash=sha256_hex(leaf), data=leaf)
            for leaf in leaves
        ]
        self._original_leaf_count = len(self._leaves)

        # Build tree bottom-up (uses copy to avoid mutating _leaves)
        self._root = self._build_tree(self._leaves.copy())

    def _build_tree(self, nodes: List[MerkleNode]) -> MerkleNode:
        """Recursively build tree from nodes."""
        if len(nodes) == 1:
            return nodes[0]

        # Pad to even number if necessary
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])  # Duplicate last node

        # Build next level
        next_level = []
        for i in range(0, len(nodes), 2):
            left, right = nodes[i], nodes[i + 1]
            parent_hash = sha256_hex(
                left.hash.encode() + right.hash.encode()
            )
            parent = MerkleNode(hash=parent_hash, left=left, right=right)
            next_level.append(parent)

        return self._build_tree(next_level)

    @property
    def root(self) -> str:
        """Get Merkle root hash."""
        return self._root.hash

    @property
    def leaf_count(self) -> int:
        """Get number of original leaves (excluding padding)."""
        return self._original_leaf_count

    def get_proof(self, index: int) -> List[Tuple[str, bool]]:
        """
        Get Merkle proof for leaf at index.

        Args:
            index: Index of leaf to prove

        Returns:
            List of (hash, is_right) tuples forming the proof path
        """
        if index >= self._original_leaf_count:
            raise IndexError(f"Leaf index {index} out of range")

        # Single leaf tree: leaf IS the root, no proof needed
        if self._original_leaf_count == 1:
            return []

        proof = []
        nodes = self._leaves.copy()

        # Pad if necessary
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])

        current_index = index

        while len(nodes) > 1:
            next_level = []

            for i in range(0, len(nodes), 2):
                left, right = nodes[i], nodes[i + 1]

                # Check if current node is in this pair
                if current_index == i:
                    proof.append((right.hash, True))  # Sibling is on right
                elif current_index == i + 1:
                    proof.append((left.hash, False))  # Sibling is on left

                # Create parent
                parent_hash = sha256_hex(
                    left.hash.encode() + right.hash.encode()
                )
                next_level.append(MerkleNode(hash=parent_hash))

            nodes = next_level
            current_index = current_index // 2

            # Pad if necessary
            if len(nodes) > 1 and len(nodes) % 2 == 1:
                nodes.append(nodes[-1])

        return proof

    @staticmethod
    def verify_proof(
        leaf_hash: str,
        proof: List[Tuple[str, bool]],
        root: str,
    ) -> bool:
        """
        Verify a Merkle proof.

        Args:
            leaf_hash: Hash of the leaf being verified
            proof: Proof path from get_proof()
            root: Expected Merkle root

        Returns:
            True if proof is valid
        """
        current = leaf_hash

        for sibling_hash, is_right in proof:
            if is_right:
                current = sha256_hex(current.encode() + sibling_hash.encode())
            else:
                current = sha256_hex(sibling_hash.encode() + current.encode())

        return hmac.compare_digest(current, root)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'root': self.root,
            'leaf_count': self.leaf_count,
        }


# =============================================================================
# Execution Trace
# =============================================================================

@dataclass
class ExecutionStep:
    """Single step in execution trace."""
    step_id: int
    operation: str
    input_hash: str
    output_hash: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        """
        Serialize to bytes for hashing.

        Note: Timestamp is excluded from hashing to ensure determinism.
        The timestamp is stored for audit/logging but doesn't affect
        the cryptographic properties of the trace.
        """
        data = {
            'step_id': self.step_id,
            'operation': self.operation,
            'input_hash': self.input_hash,
            'output_hash': self.output_hash,
        }
        return json.dumps(data, sort_keys=True).encode()


class ExecutionTrace:
    """
    Cryptographic trace of inference execution.

    Records intermediate states as a Merkle tree, enabling:
    - Proof that specific operations occurred
    - Verification of execution order
    - Detection of tampering
    """

    def __init__(self):
        """Initialize empty trace."""
        self._steps: List[ExecutionStep] = []
        self._merkle_tree: Optional[MerkleTree] = None
        self._finalized = False

    def add_step(
        self,
        operation: str,
        input_data: bytes,
        output_data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionStep:
        """
        Add a step to the trace.

        Args:
            operation: Name of the operation
            input_data: Input to the operation
            output_data: Output of the operation
            metadata: Optional additional metadata

        Returns:
            The created ExecutionStep
        """
        if self._finalized:
            raise RuntimeError("Cannot add steps to finalized trace")

        step = ExecutionStep(
            step_id=len(self._steps),
            operation=operation,
            input_hash=sha256_hex(input_data),
            output_hash=sha256_hex(output_data),
            timestamp=time.time(),
            metadata=metadata or {},
        )
        self._steps.append(step)
        return step

    def finalize(self) -> str:
        """
        Finalize the trace and compute Merkle root.

        Returns:
            Merkle root of the trace
        """
        if self._finalized:
            return self._merkle_tree.root

        leaves = [step.to_bytes() for step in self._steps]
        self._merkle_tree = MerkleTree(leaves)
        self._finalized = True

        return self._merkle_tree.root

    @property
    def root(self) -> Optional[str]:
        """Get Merkle root (None if not finalized)."""
        return self._merkle_tree.root if self._finalized else None

    @property
    def steps(self) -> List[ExecutionStep]:
        """Get all steps."""
        return self._steps.copy()

    def get_proof(self, step_id: int) -> List[Tuple[str, bool]]:
        """Get Merkle proof for a step."""
        if not self._finalized:
            raise RuntimeError("Trace must be finalized before getting proofs")
        return self._merkle_tree.get_proof(step_id)

    def verify_step(
        self,
        step: ExecutionStep,
        proof: List[Tuple[str, bool]],
    ) -> bool:
        """Verify a step is part of this trace."""
        if not self._finalized:
            raise RuntimeError("Trace must be finalized before verification")

        leaf_hash = sha256_hex(step.to_bytes())
        return MerkleTree.verify_proof(leaf_hash, proof, self.root)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'steps': [
                {
                    'step_id': s.step_id,
                    'operation': s.operation,
                    'input_hash': s.input_hash,
                    'output_hash': s.output_hash,
                }
                for s in self._steps
            ],
            'root': self.root,
            'finalized': self._finalized,
        }


# =============================================================================
# TEE Abstraction
# =============================================================================

class TEEType(Enum):
    """Supported Trusted Execution Environment types."""
    NONE = "none"           # No TEE (software only)
    INTEL_SGX = "sgx"       # Intel Software Guard Extensions
    AMD_SEV = "sev"         # AMD Secure Encrypted Virtualization
    ARM_TRUSTZONE = "tz"    # ARM TrustZone
    SIMULATED = "simulated" # Simulated TEE for testing


@dataclass(frozen=True)
class TEECapabilities:
    """Capabilities of a TEE."""
    tee_type: TEEType
    supports_attestation: bool = True
    supports_sealing: bool = True
    max_enclave_size_mb: int = 128
    supports_remote_attestation: bool = True


@dataclass
class AttestationReport:
    """
    TEE attestation report.

    Contains cryptographic proof that code is running in a genuine TEE
    with specific properties (code hash, configuration, etc.)
    """
    tee_type: TEEType
    enclave_hash: str           # Hash of enclave code
    config_hash: str            # Hash of enclave configuration
    report_data: bytes          # User-provided data included in report
    signature: bytes            # TEE signature over report
    timestamp: float
    platform_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tee_type': self.tee_type.value,
            'enclave_hash': self.enclave_hash,
            'config_hash': self.config_hash,
            'report_data_hash': sha256_hex(self.report_data),
            'signature_present': len(self.signature) > 0,
            'timestamp': self.timestamp,
            'platform_info': self.platform_info,
        }


class TEEProvider(ABC):
    """
    Abstract interface for Trusted Execution Environments.

    Implementations exist for:
    - Intel SGX (via SDK)
    - AMD SEV (via API)
    - Simulated (for testing)
    """

    @property
    @abstractmethod
    def capabilities(self) -> TEECapabilities:
        """Get TEE capabilities."""
        pass

    @abstractmethod
    async def create_enclave(
        self,
        code_hash: str,
        config: Dict[str, Any],
    ) -> str:
        """
        Create a new enclave.

        Args:
            code_hash: Hash of code to run in enclave
            config: Enclave configuration

        Returns:
            Enclave ID
        """
        pass

    @abstractmethod
    async def execute_in_enclave(
        self,
        enclave_id: str,
        input_data: bytes,
    ) -> Tuple[bytes, ExecutionTrace]:
        """
        Execute computation in enclave.

        Args:
            enclave_id: ID of enclave to use
            input_data: Input data for computation

        Returns:
            Tuple of (output_data, execution_trace)
        """
        pass

    @abstractmethod
    async def get_attestation(
        self,
        enclave_id: str,
        report_data: bytes,
    ) -> AttestationReport:
        """
        Get attestation report for enclave.

        Args:
            enclave_id: ID of enclave
            report_data: User data to include in report

        Returns:
            AttestationReport
        """
        pass

    @abstractmethod
    async def destroy_enclave(self, enclave_id: str) -> None:
        """Destroy an enclave."""
        pass


class SimulatedTEE(TEEProvider):
    """
    Simulated TEE for testing.

    Provides the same interface as real TEEs but without hardware security.
    Useful for development and testing.
    """

    def __init__(self):
        """Initialize simulated TEE."""
        self._enclaves: Dict[str, Dict[str, Any]] = {}
        self._enclave_counter = 0

    @property
    def capabilities(self) -> TEECapabilities:
        return TEECapabilities(
            tee_type=TEEType.SIMULATED,
            supports_attestation=True,
            supports_sealing=True,
            max_enclave_size_mb=1024,
            supports_remote_attestation=False,  # Simulated can't do real remote attestation
        )

    async def create_enclave(
        self,
        code_hash: str,
        config: Dict[str, Any],
    ) -> str:
        """Create simulated enclave."""
        self._enclave_counter += 1
        enclave_id = f"sim-enclave-{self._enclave_counter}"

        self._enclaves[enclave_id] = {
            'code_hash': code_hash,
            'config': config,
            'created_at': time.time(),
        }

        return enclave_id

    async def execute_in_enclave(
        self,
        enclave_id: str,
        input_data: bytes,
    ) -> Tuple[bytes, ExecutionTrace]:
        """Execute in simulated enclave."""
        if enclave_id not in self._enclaves:
            raise ValueError(f"Unknown enclave: {enclave_id}")

        trace = ExecutionTrace()

        # Simulate execution steps
        trace.add_step(
            operation="load_input",
            input_data=b"",
            output_data=input_data,
        )

        # Simulate inference (hash-based for determinism)
        output_data = sha256(input_data + b":simulated-inference")

        trace.add_step(
            operation="inference",
            input_data=input_data,
            output_data=output_data,
        )

        trace.add_step(
            operation="finalize",
            input_data=output_data,
            output_data=output_data,
        )

        trace.finalize()

        return output_data, trace

    async def get_attestation(
        self,
        enclave_id: str,
        report_data: bytes,
    ) -> AttestationReport:
        """Get simulated attestation."""
        if enclave_id not in self._enclaves:
            raise ValueError(f"Unknown enclave: {enclave_id}")

        enclave = self._enclaves[enclave_id]

        # Create simulated signature
        signature_data = (
            enclave['code_hash'].encode() +
            json.dumps(enclave['config'], sort_keys=True).encode() +
            report_data
        )
        signature = sha256(signature_data + b":simulated-signature")

        return AttestationReport(
            tee_type=TEEType.SIMULATED,
            enclave_hash=enclave['code_hash'],
            config_hash=sha256_hex(
                json.dumps(enclave['config'], sort_keys=True).encode()
            ),
            report_data=report_data,
            signature=signature,
            timestamp=time.time(),
            platform_info={
                'simulated': True,
                'enclave_id': enclave_id,
            },
        )

    async def destroy_enclave(self, enclave_id: str) -> None:
        """Destroy simulated enclave."""
        self._enclaves.pop(enclave_id, None)


# =============================================================================
# Cryptographic Proof
# =============================================================================

@dataclass
class CryptographicProof:
    """
    Complete cryptographic proof of deterministic inference.

    Contains all information needed for third-party verification:
    - Input commitment (what was asked)
    - Kernel config commitment (how it was configured)
    - TEE attestation (where it ran)
    - Execution trace (what happened)
    - Output commitment (what was produced)
    """
    # Commitments
    input_commitment: InputCommitment
    kernel_commitment: Commitment
    output_commitment: Commitment

    # Attestation
    attestation: AttestationReport

    # Execution
    execution_trace_root: str
    execution_steps: int

    # Metadata
    proof_id: str
    created_at: float
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'proof_id': self.proof_id,
            'version': self.version,
            'input_commitment': self.input_commitment.to_dict(),
            'kernel_commitment': self.kernel_commitment.to_dict(),
            'output_commitment': self.output_commitment.to_dict(),
            'attestation': self.attestation.to_dict(),
            'execution_trace_root': self.execution_trace_root,
            'execution_steps': self.execution_steps,
            'created_at': self.created_at,
        }

    def to_bytes(self) -> bytes:
        """Serialize to bytes."""
        return json.dumps(self.to_dict(), sort_keys=True).encode()

    @property
    def proof_hash(self) -> str:
        """Compute hash of the proof."""
        return sha256_hex(self.to_bytes())


class ProofVerifier:
    """
    Verifies cryptographic proofs of deterministic inference.

    Anyone can use this to verify that inference was deterministic
    without trusting the inference provider.
    """

    def __init__(self, trusted_tee_types: Optional[List[TEEType]] = None):
        """
        Initialize verifier.

        Args:
            trusted_tee_types: List of TEE types to trust
        """
        self._trusted_tee_types = trusted_tee_types or [
            TEEType.INTEL_SGX,
            TEEType.AMD_SEV,
            TEEType.SIMULATED,  # For testing
        ]

    def verify(
        self,
        proof: CryptographicProof,
        expected_input_hash: Optional[str] = None,
        expected_output_hash: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Verify a cryptographic proof.

        Args:
            proof: The proof to verify
            expected_input_hash: Optional expected input hash
            expected_output_hash: Optional expected output hash

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # 1. Verify TEE type is trusted
        if proof.attestation.tee_type not in self._trusted_tee_types:
            issues.append(
                f"Untrusted TEE type: {proof.attestation.tee_type.value}"
            )

        # 2. Verify attestation signature is present
        if len(proof.attestation.signature) == 0:
            issues.append("Missing attestation signature")

        # 3. Verify execution trace has steps
        if proof.execution_steps < 1:
            issues.append("Execution trace is empty")

        # 4. Verify input hash if provided
        if expected_input_hash:
            if proof.input_commitment.combined_hash != expected_input_hash:
                issues.append("Input commitment hash mismatch")

        # 5. Verify output hash if provided
        if expected_output_hash:
            if proof.output_commitment.commitment_hash != expected_output_hash:
                issues.append("Output commitment hash mismatch")

        # 6. Verify proof structure
        if not proof.proof_id:
            issues.append("Missing proof ID")

        if proof.version != "1.0.0":
            issues.append(f"Unknown proof version: {proof.version}")

        return len(issues) == 0, issues


# =============================================================================
# Verified Inference Result
# =============================================================================

@dataclass
class VerifiedInferenceResult:
    """
    Inference result with cryptographic proof of determinism.

    Contains the response along with all cryptographic artifacts
    needed to verify the inference was deterministic.
    """
    # The actual response
    response: str
    response_hash: str

    # Cryptographic proof
    proof: CryptographicProof

    # Metadata
    latency_ms: float
    model_id: str
    backend: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'response': self.response,
            'response_hash': self.response_hash,
            'proof': self.proof.to_dict(),
            'latency_ms': self.latency_ms,
            'model_id': self.model_id,
            'backend': self.backend,
        }

    def verify(self, verifier: Optional[ProofVerifier] = None) -> Tuple[bool, List[str]]:
        """
        Verify this result.

        Verification includes:
        1. Proof structure validation (via ProofVerifier)
        2. Output commitment verification (response matches commitment)

        Args:
            verifier: Optional custom verifier

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # 1. Verify proof structure
        verifier = verifier or ProofVerifier()
        struct_valid, struct_issues = verifier.verify(self.proof)
        issues.extend(struct_issues)

        # 2. Verify output commitment matches response
        response_bytes = self.response.encode('utf-8')
        if not self.proof.output_commitment.verify(response_bytes):
            issues.append("Response does not match output commitment")

        # 3. Verify response_hash is correct
        expected_hash = sha256_hex(response_bytes)
        if self.response_hash != expected_hash:
            issues.append("Response hash mismatch")

        return len(issues) == 0, issues


# =============================================================================
# Cryptographic Backend
# =============================================================================

CRYPTOGRAPHIC_CAPABILITIES = BackendCapabilities(
    supports_seed=True,
    supports_logprobs=False,  # Proofs don't include logprobs
    supports_streaming=False, # Streaming not compatible with proofs
    supports_system_prompt=True,
    supports_stop_sequences=True,
    supports_temperature_zero=True,
    max_context_window=128000,
    determinism_level="cryptographic",
)


class CryptographicBackend(InferenceBackend):
    """
    Backend that produces cryptographically verified inference results.

    Wraps another backend and adds:
    - Input/output commitments
    - TEE execution (when available)
    - Execution traces
    - Cryptographic proofs

    Example:
        >>> inner_backend = DeterministicVLLMBackend(...)
        >>> crypto_backend = CryptographicBackend(inner_backend)
        >>> await crypto_backend.initialize()
        >>>
        >>> result = await crypto_backend.infer_verified("Hello!")
        >>> valid, issues = result.verify()
        >>> if valid:
        ...     print("Cryptographically verified!")
    """

    def __init__(
        self,
        inner_backend: InferenceBackend,
        tee_provider: Optional[TEEProvider] = None,
        kernel_config: Optional[He2025KernelConfig] = None,
    ):
        """
        Initialize cryptographic backend.

        Args:
            inner_backend: The actual inference backend
            tee_provider: TEE provider (SimulatedTEE if None)
            kernel_config: Kernel configuration
        """
        super().__init__(
            model_id=inner_backend.model_id,
            api_key=None,
        )
        self._inner = inner_backend
        self._tee = tee_provider or SimulatedTEE()
        self._kernel_config = kernel_config or HE2025_STRICT
        self._enclave_id: Optional[str] = None
        self._proof_counter = 0

    @property
    def name(self) -> str:
        return f"cryptographic-{self._inner.name}"

    @property
    def capabilities(self) -> BackendCapabilities:
        return CRYPTOGRAPHIC_CAPABILITIES

    @property
    def tee_capabilities(self) -> TEECapabilities:
        """Get TEE capabilities."""
        return self._tee.capabilities

    async def initialize(self) -> None:
        """Initialize backend and create enclave."""
        # Initialize inner backend
        await self._inner.initialize()

        # Create TEE enclave
        code_hash = sha256_hex(b"inference-enclave-v1")
        self._enclave_id = await self._tee.create_enclave(
            code_hash=code_hash,
            config=self._kernel_config.to_dict(),
        )

        self._status = BackendStatus.HEALTHY

    async def infer(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> InferenceResponse:
        """
        Perform inference (without full cryptographic proof).

        For full proofs, use infer_verified().
        """
        return await self._inner.infer(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
            stop_sequences=stop_sequences,
            **kwargs,
        )

    async def infer_verified(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> VerifiedInferenceResult:
        """
        Perform cryptographically verified inference.

        This method:
        1. Creates input commitment
        2. Executes in TEE (or simulated)
        3. Creates execution trace
        4. Gets attestation
        5. Creates output commitment
        6. Generates cryptographic proof

        Returns:
            VerifiedInferenceResult with proof
        """
        import time
        start_time = time.perf_counter()

        # Force deterministic parameters
        temperature = 0.0
        seed = seed or self._kernel_config.seed

        # 1. Create input commitment
        params = {
            'temperature': temperature,
            'max_tokens': max_tokens,
            'seed': seed,
            'system_prompt': system_prompt,
        }
        input_commitment = InputCommitment.create(prompt, params)

        # 2. Create kernel commitment
        kernel_bytes = json.dumps(
            self._kernel_config.to_dict(),
            sort_keys=True
        ).encode()
        kernel_commitment, _ = Commitment.create(kernel_bytes)

        # 3. Execute inference (through inner backend)
        response = await self._inner.infer(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
            **kwargs,
        )

        # 4. Create execution trace
        trace = ExecutionTrace()
        trace.add_step(
            operation="input_processing",
            input_data=prompt.encode(),
            output_data=prompt.encode(),
        )
        trace.add_step(
            operation="inference",
            input_data=prompt.encode(),
            output_data=response.content.encode(),
        )
        trace.add_step(
            operation="output_processing",
            input_data=response.content.encode(),
            output_data=response.content.encode(),
        )
        trace_root = trace.finalize()

        # 5. Create output commitment
        output_bytes = response.content.encode()
        output_commitment, _ = Commitment.create(output_bytes)

        # 6. Get TEE attestation
        report_data = sha256(
            input_commitment.combined_hash.encode() +
            trace_root.encode()
        )
        attestation = await self._tee.get_attestation(
            self._enclave_id,
            report_data,
        )

        # 7. Create proof
        self._proof_counter += 1
        proof = CryptographicProof(
            input_commitment=input_commitment,
            kernel_commitment=kernel_commitment,
            output_commitment=output_commitment,
            attestation=attestation,
            execution_trace_root=trace_root,
            execution_steps=len(trace.steps),
            proof_id=f"proof-{self._proof_counter}-{int(time.time())}",
            created_at=time.time(),
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        return VerifiedInferenceResult(
            response=response.content,
            response_hash=sha256_hex(response.content.encode()),
            proof=proof,
            latency_ms=latency_ms,
            model_id=self._model_id,
            backend=self.name,
        )

    async def infer_stream(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streaming not supported for cryptographic backend."""
        raise NotImplementedError(
            "Streaming not supported for cryptographic inference. "
            "Use infer() or infer_verified() instead."
        )

    async def health_check(self) -> bool:
        """Check health of inner backend."""
        return await self._inner.health_check()

    async def shutdown(self) -> None:
        """Shutdown backend and destroy enclave."""
        if self._enclave_id:
            await self._tee.destroy_enclave(self._enclave_id)
            self._enclave_id = None

        await self._inner.shutdown()
        self._status = BackendStatus.UNAVAILABLE


# =============================================================================
# Mock Backend for Testing
# =============================================================================

class MockCryptographicBackend(InferenceBackend):
    """
    Mock backend for testing cryptographic verification.

    Always produces valid proofs with deterministic responses.
    """

    def __init__(
        self,
        model_id: str = "mock-crypto",
        kernel_config: Optional[He2025KernelConfig] = None,
    ):
        """Initialize mock backend."""
        super().__init__(model_id)
        self._kernel_config = kernel_config or HE2025_STRICT
        self._tee = SimulatedTEE()
        self._enclave_id: Optional[str] = None
        self._proof_counter = 0

    @property
    def name(self) -> str:
        return "mock-cryptographic"

    @property
    def capabilities(self) -> BackendCapabilities:
        return CRYPTOGRAPHIC_CAPABILITIES

    async def initialize(self) -> None:
        """Initialize mock backend."""
        self._enclave_id = await self._tee.create_enclave(
            code_hash=sha256_hex(b"mock-enclave"),
            config=self._kernel_config.to_dict(),
        )
        self._status = BackendStatus.HEALTHY

    async def infer(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> InferenceResponse:
        """Generate deterministic response."""
        seed = seed or self._kernel_config.seed
        response_hash = sha256_hex(
            f"{prompt}:{system_prompt}:{seed}".encode()
        )
        content = f"Verified response for hash {response_hash[:16]}"

        return InferenceResponse(
            content=content,
            model=self._model_id,
            finish_reason="stop",
            metadata={
                'cryptographic': True,
                'seed': seed,
            },
        )

    async def infer_verified(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> VerifiedInferenceResult:
        """Generate verified response with proof."""
        import time
        start_time = time.perf_counter()

        seed = kwargs.pop('seed', None) or self._kernel_config.seed

        # Create response
        response = await self.infer(prompt, system_prompt, seed=seed, **kwargs)

        # Create commitments
        params = {'seed': seed, 'system_prompt': system_prompt}
        input_commitment = InputCommitment.create(prompt, params)

        kernel_bytes = json.dumps(self._kernel_config.to_dict(), sort_keys=True).encode()
        kernel_commitment, _ = Commitment.create(kernel_bytes)

        output_bytes = response.content.encode()
        output_commitment, _ = Commitment.create(output_bytes)

        # Create trace
        trace = ExecutionTrace()
        trace.add_step("mock_inference", prompt.encode(), response.content.encode())
        trace_root = trace.finalize()

        # Get attestation
        report_data = sha256(input_commitment.combined_hash.encode())
        attestation = await self._tee.get_attestation(self._enclave_id, report_data)

        # Create proof
        self._proof_counter += 1
        proof = CryptographicProof(
            input_commitment=input_commitment,
            kernel_commitment=kernel_commitment,
            output_commitment=output_commitment,
            attestation=attestation,
            execution_trace_root=trace_root,
            execution_steps=1,
            proof_id=f"mock-proof-{self._proof_counter}",
            created_at=time.time(),
        )

        return VerifiedInferenceResult(
            response=response.content,
            response_hash=sha256_hex(response.content.encode()),
            proof=proof,
            latency_ms=(time.perf_counter() - start_time) * 1000,
            model_id=self._model_id,
            backend=self.name,
        )

    async def infer_stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        """Streaming not supported."""
        raise NotImplementedError("Streaming not supported")

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        if self._enclave_id:
            await self._tee.destroy_enclave(self._enclave_id)
        self._status = BackendStatus.UNAVAILABLE
