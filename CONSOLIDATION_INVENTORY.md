# Otto Consolidation Inventory

**Date:** 2026-01-23
**Methodology:** ThinkingMachines [He2025] batch-invariance compliant

---

## Source Locations (Now Deprecated)

| Location | Size | Purpose |
|----------|------|---------|
| `C:\Users\User\.claude\Framework_Ottotor\` | ~52MB | Source code, React dashboard, git repo |
| `C:\Users\User\.framework-ottotor\` | ~206KB | Runtime config, state, domains |

---

## Target Location

```
C:\Users\User\Otto\
```

---

## Consolidated Assets

### Python Backend (src/otto/)

| Module | Lines | Purpose |
|--------|-------|---------|
| `framework_ottotor.py` | 2100+ | Main 7-agent ottotor |
| `config.py` | 400+ | Configuration with env var support |
| `resilience.py` | 500+ | Circuit breaker, retry logic |
| `checkpoint.py` | 500+ | Crash recovery checkpoints |
| `bulkhead.py` | 400+ | Concurrency isolation |
| `metrics.py` | 450+ | Prometheus metrics |
| `tracing.py` | 500+ | OpenTelemetry tracing |
| `health.py` | 270+ | Health check endpoints |
| `lifecycle.py` | 300+ | Graceful shutdown |
| `http_server.py` | 300+ | HTTP API server |
| `fallback.py` | 450+ | Fallback strategies |
| `rate_limit.py` | 360+ | Rate limiting |
| `idempotency.py` | 340+ | Request deduplication |
| `validation.py` | 230+ | Input validation |
| `file_ops.py` | 180+ | Safe file operations |
| `logging_setup.py` | 270+ | Structured logging |
| `schemas.py` | 320+ | JSON schemas |
| `cogroute_bench.py` | 700+ | Benchmark suite |
| `otel_adapter.py` | 280+ | OpenTelemetry adapter |
| `__init__.py` | 220+ | Package exports |
| `__main__.py` | 15 | CLI entry point |

**Total: 22 Python modules**

### React Dashboard (src/dashboard/)

#### Components (22 files)
- `SimplifiedDashboard.jsx` - Maeda-inspired minimal UI
- `CognitiveAppShell.jsx` - Main cognitive dashboard shell
- `CognitiveStatePanel.jsx` - Burnout/momentum display
- `ConvergenceMonitor.jsx` - RC^+xi convergence tracking
- `RoutingDisplay.jsx` - Expert routing visualization
- `LayerStackViewer.jsx` - USD layer stack
- `AgentOtto.jsx` - Agent status visualization
- `ADHDSupportPanel.jsx` - Executive function support
- `TaskInterface.jsx` - Task input/output
- `Header.jsx`, `Icons.jsx`, `AppShell.jsx`
- `ActivityPanel.jsx`, `MetricsPanel.jsx`
- `AgentCard.jsx`, `AgentsList.jsx`, `StatusCard.jsx`
- `LatencyChart.jsx`, `TaskInput.jsx`
- `Modal.jsx`, `Toast.jsx`

#### Styles (5 files)
- `maeda.css` - John Maeda's Laws of Simplicity
- `cognitive.css` - Cognitive state styling
- `components.css` - Component styles
- `variables.css` - CSS variables
- `layout.css` - Layout system

#### Support Files
- `server.py` - Flask API server
- `package.json` - npm dependencies
- `vite.config.js` - Vite build config
- `index.html` - Entry HTML
- `dist/` - Production build

### Configuration (config/)

#### Domain Configs (4 files)
| Domain | Specialists | Keywords |
|--------|-------------|----------|
| `webdev.json` | 6 | React, Next.js, CSS, API |
| `ai_research.json` | 7 | ML, agents, prompts |
| `ai_conductor.json` | 10 | Ottotion, cognitive |
| `general.json` | 5 | Default domain |

#### Framework Modules (5 directories)
- `adhd_moe/` - ADHD intervention experts
- `cortex_world/` - World modeling
- `echo_memory/` - Context memory
- `max_reflection/` - Bounded reflection
- `nova_oracle/` - Self-play generation

#### Principles
- `principles.json` - 7 constitutional rules

### Tests (tests/)

**25 test files** covering:
- Ottotor core
- All resilience modules
- Configuration
- Integration tests
- Performance benchmarks
- Chaos testing

### Documentation (docs/)

- Architecture diagrams
- API documentation
- History/changelog
- Images/assets

### Examples (examples/)

- Sample domain configurations
- Usage examples

---

## Path Mappings

| Old Path | New Path |
|----------|----------|
| `~/.framework-ottotor/` | `~/Otto/` |
| `~/.framework-ottotor/domains/` | `~/Otto/config/domains/` |
| `~/.framework-ottotor/frameworks/` | `~/Otto/config/frameworks/` |
| `~/.framework-ottotor/principles.json` | `~/Otto/config/principles.json` |
| `~/.framework-ottotor/results/` | `~/Otto/state/results/` |
| `~/.framework-ottotor/checkpoints/` | `~/Otto/state/checkpoints/` |
| `~/.framework-ottotor/.ottotor-state.json` | `~/Otto/state/.ottotor-state.json` |

---

## Code Changes Made

1. **config.py** (lines 108-165)
   - Default workspace: `~/Otto`
   - Added `config_dir` and `state_dir` properties
   - Updated all path properties to use new structure

2. **framework_ottotor.py**
   - Line 16: Updated docstring path
   - Line 166: `PRINCIPLES_PATH` → `~/Otto/config/principles.json`
   - Line 449: `DEFAULT_DOMAINS_PATH` → `~/Otto/config/domains`
   - Line 2089: Updated help text

3. **server.py** (dashboard)
   - Removed legacy vanilla JS fallback
   - `REACT_DIST_DIR` now same directory as server.py
   - Simplified to React-only

---

## Files NOT Consolidated (Intentionally Excluded)

| File | Reason |
|------|--------|
| `create_icon.py` | Utility script, not core functionality |
| `setup.py` | Can be regenerated from pyproject.toml |
| `test_local_ottotion.py` | Local test file |
| `node_modules/` | Reinstall with npm |
| `.git/` | Fresh git history for Otto |
| `dashboard/templates/` | Legacy vanilla JS (replaced by React) |
| `dashboard/static/` | Legacy vanilla JS assets |
| Various `.bat`, `.ps1` scripts | Windows shortcuts, can regenerate |

---

## Verification Results

```
✓ Ottotor loads: 7 agents, 5 domains, 7 principles
✓ Checkpoint path: ~/Otto/state/checkpoints
✓ Domains path: ~/Otto/config/domains
✓ Dashboard server module loads
✓ React build exists in dist/
✓ All 25 test files present
```

---

## Usage

```bash
# Run ottotor
cd C:\Users\User\Otto
python -m src.otto --task "your task"
python -m src.otto --info

# Run dashboard
cd src/dashboard
npm install  # first time only
npm run build
python server.py
# Visit http://localhost:5050
```
