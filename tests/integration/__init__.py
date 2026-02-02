"""
OTTO Integration Tests
======================

These tests validate the memory backbone is correctly wired.
They test real interactions between components, not mocks.

Test Categories:
- test_memory_interface.py: OTTOMemory unified interface
- test_trail_system.py: Pheromone trail architecture
- test_cross_surface.py: Cross-surface state visibility
- test_e2e_scenarios.py: End-to-end user scenarios
- test_livrps.py: LIVRPS layer composition

[He2025] Compliance:
- All tests use real memory instances (no mocking of determinism)
- Tests verify fixed evaluation order
- Tests verify deterministic outputs
"""
