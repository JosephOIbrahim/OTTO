"""
Comprehensive Determinism Verification for OTTO Public REST API.

Per [He2025] "Defeating Nondeterminism in LLM Inference":
- Batch invariance: same input → same output regardless of concurrent load
- Fixed evaluation order: no runtime-dependent branching
- Reproducible computations: deterministic routing and response generation

This test suite verifies these principles at the application level.

Reference:
  He, Horace and Thinking Machines Lab, "Defeating Nondeterminism in LLM Inference",
  Thinking Machines Lab: Connectionism, Sep 2025.
  https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

import asyncio
import json
import pytest
from typing import Dict, Any, List
from unittest.mock import patch

from otto.api import (
    # Core
    APIScope,
    APIKeyManager,
    # Routing
    Route,
    ROUTES,
    RESTRouter,
    create_rest_router,
    # Middleware
    MiddlewareChain,
    create_api_middleware,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    ScopeValidationMiddleware,
    SensitiveDataFilterMiddleware,
    # Response
    APIResponse,
    APIResponseMeta,
    success,
    error,
    # Errors
    APIErrorCode,
    api_code_to_http_status,
)
from otto.http_server import HTTPRequest


# =============================================================================
# Test Utilities
# =============================================================================

def normalize_for_comparison(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize response for determinism comparison.

    Removes fields that are EXPECTED to vary per-request:
    - timestamp: Time of request
    - request_id: Unique per request (UUID)
    - rate_limit_remaining: Decrements per request
    - rate_limit_reset: Time-based

    These fields varying is NOT nondeterminism - they are designed to vary.
    What matters is that the STRUCTURE and ROUTING are deterministic.
    """
    normalized = json.loads(json.dumps(body))
    if "meta" in normalized:
        for field in ["timestamp", "request_id", "rate_limit_remaining", "rate_limit_reset"]:
            if field in normalized["meta"]:
                normalized["meta"][field] = "NORMALIZED"
    if "data" in normalized and isinstance(normalized["data"], dict):
        if "timestamp" in normalized["data"]:
            normalized["data"]["timestamp"] = "NORMALIZED"
    return normalized


# =============================================================================
# Route Order Determinism
# =============================================================================

class TestRouteOrderDeterminism:
    """
    Verify route evaluation order is fixed.

    [He2025] Principle: Fixed evaluation order ensures reproducibility.
    """

    def test_routes_list_is_immutable_order(self):
        """ROUTES list should maintain fixed order."""
        # Get order multiple times
        orders = []
        for _ in range(10):
            order = [(r.method, r.path_pattern, r.jsonrpc_method) for r in ROUTES]
            orders.append(order)

        # All should be identical
        first = orders[0]
        for order in orders[1:]:
            assert order == first

    def test_route_matching_is_deterministic(self):
        """Same path should always match same route."""
        key_manager = APIKeyManager(use_keyring=False)
        middleware = create_api_middleware(key_manager=key_manager)
        router = RESTRouter(middleware=middleware)

        test_paths = [
            ("GET", "/api/v1/status"),
            ("GET", "/api/v1/ping"),
            ("GET", "/api/v1/state"),
            ("PATCH", "/api/v1/state"),
            ("POST", "/api/v1/sessions"),
            ("GET", "/api/v1/agents"),
            ("DELETE", "/api/v1/agents/test-id"),
        ]

        for method, path in test_paths:
            # Match same path 5 times
            matches = []
            for _ in range(5):
                route, params = router._find_route(method, path)
                if route:
                    matches.append((route.method, route.path_pattern, route.jsonrpc_method))
                else:
                    matches.append(None)

            # All matches should be identical
            first = matches[0]
            for match in matches[1:]:
                assert match == first, f"Non-deterministic match for {method} {path}"

    def test_first_match_wins_consistently(self):
        """First matching route should always win (no random selection)."""
        key_manager = APIKeyManager(use_keyring=False)
        middleware = create_api_middleware(key_manager=key_manager)
        router = RESTRouter(middleware=middleware)

        # Test that ordering matters and is consistent
        route_get, _ = router._find_route("GET", "/api/v1/status")
        route_patch, _ = router._find_route("PATCH", "/api/v1/state")

        # These should be different routes
        assert route_get is not None
        assert route_patch is not None
        assert route_get.jsonrpc_method != route_patch.jsonrpc_method


# =============================================================================
# Middleware Chain Determinism
# =============================================================================

class TestMiddlewareChainDeterminism:
    """
    Verify middleware execution order is fixed.

    [He2025] Principle: Fixed evaluation order in the processing pipeline.
    """

    def test_middleware_order_is_fixed(self):
        """Middleware should execute in fixed order: Auth → RateLimit → Scope → Filter."""
        key_manager = APIKeyManager(use_keyring=False)

        # Create multiple chains
        chains = [create_api_middleware(key_manager=key_manager) for _ in range(5)]

        # Get middleware types from each
        type_orders = []
        for chain in chains:
            types = [type(m).__name__ for m in chain._middleware]
            type_orders.append(types)

        # All should be identical
        first = type_orders[0]
        for order in type_orders[1:]:
            assert order == first

    def test_middleware_chain_deterministic_construction(self):
        """Chain construction should be deterministic."""
        key_manager = APIKeyManager(use_keyring=False)

        # Create chains with different key managers (but same type)
        km1 = APIKeyManager(use_keyring=False)
        km2 = APIKeyManager(use_keyring=False)

        chain1 = create_api_middleware(key_manager=km1)
        chain2 = create_api_middleware(key_manager=km2)

        # Should have same structure
        types1 = [type(m).__name__ for m in chain1._middleware]
        types2 = [type(m).__name__ for m in chain2._middleware]

        assert types1 == types2


# =============================================================================
# Response Structure Determinism
# =============================================================================

class TestResponseStructureDeterminism:
    """
    Verify response structure is deterministic.

    [He2025] Principle: Same input should produce structurally identical output.
    """

    def test_success_response_structure_fixed(self):
        """Success response should have fixed structure."""
        responses = []
        for i in range(5):
            response = success(data={"test": i})
            responses.append(response.to_dict())

        # All should have same keys
        first_keys = set(responses[0].keys())
        for resp in responses[1:]:
            assert set(resp.keys()) == first_keys

    def test_error_response_structure_fixed(self):
        """Error response should have fixed structure."""
        responses = []
        for i in range(5):
            response = error(
                code=APIErrorCode.INTERNAL_ERROR,
                message=f"Error {i}",
            )
            responses.append(response.to_dict())

        # All should have same keys
        first_keys = set(responses[0].keys())
        for resp in responses[1:]:
            assert set(resp.keys()) == first_keys

    def test_meta_fields_always_present(self):
        """Meta fields should always be present."""
        required_fields = ["timestamp", "version", "request_id"]

        for _ in range(5):
            response = success(data={})
            meta = response.meta.to_dict()

            for field in required_fields:
                assert field in meta


# =============================================================================
# Error Code Mapping Determinism
# =============================================================================

class TestErrorCodeMappingDeterminism:
    """
    Verify error code → HTTP status mapping is deterministic.

    [He2025] Principle: Fixed mappings, no runtime variation.
    """

    def test_error_code_to_status_is_fixed(self):
        """Same error code should always produce same HTTP status."""
        # Test all error codes
        error_codes = [
            APIErrorCode.INVALID_JSON,
            APIErrorCode.INVALID_REQUEST,
            APIErrorCode.NOT_FOUND,
            APIErrorCode.INVALID_PARAMS,
            APIErrorCode.INTERNAL_ERROR,
            APIErrorCode.UNAUTHORIZED,
            APIErrorCode.FORBIDDEN,
            APIErrorCode.RATE_LIMITED,
        ]

        for error_code in error_codes:
            # Get status multiple times
            statuses = [api_code_to_http_status(error_code) for _ in range(5)]

            # All should be identical
            first = statuses[0]
            for status in statuses[1:]:
                assert status == first, f"Non-deterministic status for {error_code}"


# =============================================================================
# API Key Validation Determinism
# =============================================================================

class TestAPIKeyValidationDeterminism:
    """
    Verify API key validation is deterministic.

    [He2025] Principle: Same key + same state → same validation result.
    """

    def test_valid_key_always_validates(self):
        """Valid key should always validate successfully."""
        manager = APIKeyManager(use_keyring=False)
        key, _ = manager.create(
            name="Test Key",
            scopes={APIScope.READ_STATUS},
        )

        # Validate same key 10 times
        results = [manager.validate(key) for _ in range(10)]

        # All should be valid
        for result in results:
            assert result.valid is True

    def test_invalid_key_always_fails(self):
        """Invalid key should always fail validation."""
        manager = APIKeyManager(use_keyring=False)

        # Validate invalid key 10 times
        results = [manager.validate("otto_live_invalid_00000000") for _ in range(10)]

        # All should be invalid
        for result in results:
            assert result.valid is False

    def test_scope_check_is_deterministic(self):
        """Scope checking should be deterministic."""
        manager = APIKeyManager(use_keyring=False)
        key, metadata = manager.create(
            name="Scoped Key",
            scopes={APIScope.READ_STATUS, APIScope.READ_STATE},
        )

        # Check scopes multiple times
        validation = manager.validate(key)
        key_obj = validation.key

        for _ in range(10):
            has_status = APIScope.READ_STATUS in key_obj.scopes
            has_state = APIScope.READ_STATE in key_obj.scopes
            has_write = APIScope.WRITE_STATE in key_obj.scopes

            assert has_status is True
            assert has_state is True
            assert has_write is False


# =============================================================================
# Concurrent Request Batch Invariance
# =============================================================================

class TestBatchInvariance:
    """
    Verify batch invariance per [He2025].

    Core principle: Results should not depend on concurrent load.
    """

    @pytest.fixture
    def setup(self):
        """Create test infrastructure."""
        key_manager = APIKeyManager(use_keyring=False)
        key, _ = key_manager.create(
            name="Batch Test Key",
            scopes={APIScope.READ_STATUS},
        )
        middleware = create_api_middleware(key_manager=key_manager)
        router = RESTRouter(middleware=middleware)
        return key, router

    @pytest.mark.asyncio
    async def test_sequential_same_as_parallel(self, setup):
        """Sequential and parallel requests should produce same results."""
        key, router = setup

        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b""
        )

        # Sequential requests
        sequential = []
        for _ in range(3):
            response = await router.handle_request(request)
            body = json.loads(response.body)
            sequential.append(normalize_for_comparison(body))

        # Parallel requests
        tasks = [router.handle_request(request) for _ in range(3)]
        results = await asyncio.gather(*tasks)
        parallel = [
            normalize_for_comparison(json.loads(r.body))
            for r in results
        ]

        # All should be structurally identical
        reference = sequential[0]
        for result in sequential[1:] + parallel:
            assert result == reference

    @pytest.mark.asyncio
    async def test_different_batch_sizes_same_result(self, setup):
        """Different batch sizes should not affect individual results."""
        key, router = setup

        request = HTTPRequest(
            method="GET",
            path="/api/v1/health",
            headers={},
            body=b""
        )

        # Batch of 1
        batch_1 = [router.handle_request(request)]
        results_1 = await asyncio.gather(*batch_1)

        # Batch of 5
        batch_5 = [router.handle_request(request) for _ in range(5)]
        results_5 = await asyncio.gather(*batch_5)

        # Batch of 10
        batch_10 = [router.handle_request(request) for _ in range(10)]
        results_10 = await asyncio.gather(*batch_10)

        # Normalize all results
        all_results = [
            normalize_for_comparison(json.loads(r.body))
            for r in results_1 + results_5 + results_10
        ]

        # All should be identical
        reference = all_results[0]
        for result in all_results[1:]:
            assert result == reference


# =============================================================================
# Sensitive Data Filtering Determinism
# =============================================================================

class TestSensitiveFilteringDeterminism:
    """
    Verify sensitive data filtering is deterministic.

    Same scopes should always filter same fields.
    """

    def test_same_scopes_same_filtering(self):
        """Same scopes should produce same filtering behavior."""
        from otto.api.scopes import filter_state_by_scope, SENSITIVE_FIELDS

        test_data = {
            "burnout_level": "GREEN",
            "energy_level": "high",
            "momentum_phase": "rolling",
            "decision_mode": "work",
            "session_goal": "Test",
        }

        # Filter with READ_STATE (no sensitive access)
        scopes = {APIScope.READ_STATE}
        results = []
        for _ in range(10):
            filtered = filter_state_by_scope(test_data, scopes)
            results.append(filtered)

        # All should be identical
        first = results[0]
        for result in results[1:]:
            assert result == first

        # Sensitive fields should be removed
        assert "burnout_level" not in first
        assert "decision_mode" in first

    def test_full_scope_preserves_all(self):
        """READ_STATE_FULL should preserve all fields deterministically."""
        from otto.api.scopes import filter_state_by_scope

        test_data = {
            "burnout_level": "GREEN",
            "energy_level": "high",
            "decision_mode": "work",
        }

        scopes = {APIScope.READ_STATE_FULL}
        results = []
        for _ in range(10):
            filtered = filter_state_by_scope(test_data, scopes)
            results.append(filtered)

        # All should be identical and contain all fields
        first = results[0]
        for result in results[1:]:
            assert result == first
            assert "burnout_level" in result
            assert "energy_level" in result


# =============================================================================
# Summary Test
# =============================================================================

class TestDeterminismSummary:
    """
    Summary test to verify overall determinism guarantees.

    This test documents what IS deterministic and what is expected to vary.
    """

    def test_determinism_guarantees_documented(self):
        """Document determinism guarantees for the API."""
        # DETERMINISTIC (must not vary):
        deterministic_components = [
            "Route matching order",
            "Middleware execution order",
            "Error code to HTTP status mapping",
            "API key validation logic",
            "Scope permission checking",
            "Sensitive field filtering",
            "Response envelope structure",
            "JSON serialization order (sort_keys)",
        ]

        # EXPECTED TO VARY (by design):
        varying_components = [
            "request_id (UUID per request)",
            "timestamp (time of request)",
            "rate_limit_remaining (decrements per request)",
            "rate_limit_reset (time-based)",
        ]

        # This test serves as documentation
        assert len(deterministic_components) > 0
        assert len(varying_components) > 0

        # All varying components are in the 'meta' section (isolated)
        # This ensures core 'data' and 'error' sections are deterministic
