# Changelog

All notable changes to Otto will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [5.0.0] - 2026-01-26

### Added

- **5-Phase NEXUS Pipeline**: Complete cognitive ottotion engine
  - Phase 1: DETECT - PRISM signal extraction (emotional > mode > domain > task)
  - Phase 2: CASCADE - Safety gates + 7-expert MoE routing
  - Phase 3: LOCK - MAX3 bounded reflection + deterministic checksums
  - Phase 4: EXECUTE - Parameter-locked generation
  - Phase 5: UPDATE - RC^+xi convergence tracking

- **Cognitive Safety MoE**: 7 intervention experts with fixed priority
  - Validator, Scaffolder, Restorer, Refocuser, Celebrator, Socratic, Direct
  - First-match-wins semantics for deterministic routing

- **ThinkingMachines [He2025] Compliance**
  - Batch-invariant kernels (same inputs → same outputs)
  - Fixed reduction order across all operations
  - No dynamic switching strategies
  - Reproducible checksums

- **Production Resilience Patterns**
  - Circuit breaker (CLOSED → OPEN → HALF_OPEN)
  - Bulkhead pattern for resource isolation
  - Fallback registry with 3-tier cascade (cache → strategy → synthetic)
  - Retry with exponential backoff and jitter
  - Atomic file operations

- **Observability Layer**
  - OpenTelemetry adapter with graceful fallback
  - Distributed tracing with W3C context propagation
  - Prometheus-compatible metrics
  - Health check endpoints

- **CLI Tools**
  - `otto` - TUI dashboard
  - `otto status` - Cognitive state display
  - `otto install-hook` - Claude Code integration
  - `otto set` - State management

- **Test Suite**: 776 tests covering
  - Core ottotion
  - Safety gating (burnout/energy → depth caps)
  - Parameter locking determinism
  - Resilience patterns
  - Integration and chaos scenarios

### Changed

- Development status upgraded to Production/Stable
- State files moved to `~/.otto/state/` subdirectory
- Improved histogram bucket counting (Prometheus semantics)

### Fixed

- `otel_adapter.py` relative import bug
- `deque` slicing in Mycelium state export
- Handler name access for MagicMock compatibility
- Queue size semantics in bulkhead tests

## [4.0.0] - 2026-01-15

### Added

- USD composition semantics (LIVRPS) for cognitive state
- Cognitive state persistence
- WebSocket dashboard bridge

## [3.0.0] - 2026-01-01

### Added

- Initial Framework Ottotor
- 7 cognitive agents
- Basic resilience patterns

---

## References

- [ThinkingMachines [He2025]](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/) - Batch-invariance principles
- [USD](https://graphics.pixar.com/usd/) - Composition semantics inspiration
