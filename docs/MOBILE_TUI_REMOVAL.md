# OTTO OS Mobile Migration: TUI Dependency Analysis

## Summary

**Total TUI-dependent code**: ~2,250 lines
**TUI test code**: ~1,609 lines
**Estimated mobile-compatible code**: ~85% of codebase

---

## Files to REMOVE (No Mobile Equivalent)

| File | Lines | Reason |
|------|-------|--------|
| `src/otto/cli/tui.py` | 368 | Pure Rich terminal dashboard |
| `src/otto/cli/tui_enhanced.py` | 688 | Enhanced terminal dashboard with agent monitoring |
| `src/otto/tui/app.py` | ~150 | Rich-based TUI application |
| `src/otto/tui/widgets/*.py` | ~400 | Rich widget implementations |
| `tests/test_tui.py` | 811 | Tests for removed tui.py |
| `tests/test_tui_enhanced.py` | 423 | Tests for removed tui_enhanced.py |

---

## Files to ABSTRACT (Keep Logic, Remove Terminal-Specific)

### `src/otto/cli/status.py` (271 lines)
**Remove**: ANSI color codes (lines 41-56), Windows ANSI setup (lines 24-35)
**Keep**: `read_state()`, format logic without colors, `format_json()`

### `src/otto/cli/interactive.py` (421 lines)
**Remove**: Terminal `input()` calls, ASCII art
**Keep**: Session initialization, ProfileLoader, state management
**Abstract**: Create InputProvider interface

### `src/otto/dashboard.py` (503 lines)
**Remove**: ANSI color constants (lines 44-75)
**Keep**: Dashboard data structures, state queries
**Abstract**: Create DisplayFormatter interface

### `src/otto/intake/game.py`
**Remove**: Rich imports (Console, Panel, Prompt, Progress)
**Keep**: Intake questions data, response validation
**Abstract**: Create platform-agnostic intake interface

---

## Files to KEEP (Already Platform-Agnostic)

| File | Reason |
|------|--------|
| `src/otto/cli/tui_bridge.py` | Pure state management, JSON I/O |
| `src/otto/tui/websocket_client.py` | Backend WebSocket, no Rich |
| `src/otto/render/human_render.py` | Pure text generation |
| `tests/test_tui_bridge.py` | Tests state management (evaluate) |

---

## Terminal-Specific Dependencies to Remove

### Python Libraries
- `rich` - Terminal styling and layout
- `prompt_toolkit` - If used

### System Modules (Remove or Conditionalize)
- `termios` - Unix terminal control
- `tty` - Unix terminal control
- `select` - Unix I/O multiplexing
- `msvcrt` - Windows keyboard
- `ctypes.windll.kernel32` - Windows ANSI setup

---

## Required Abstractions

### 1. Output Abstraction
```python
# otto/output/formatter.py
class OutputFormatter(ABC):
    @abstractmethod
    def format_state(self, state: dict) -> str: ...

    @abstractmethod
    def format_status(self, burnout: str, momentum: str) -> str: ...

# Implementations:
# - ANSIFormatter (terminal with colors)
# - PlainFormatter (no colors)
# - JSONFormatter (structured data for mobile)
```

### 2. Input Abstraction
```python
# otto/input/provider.py
class InputProvider(ABC):
    @abstractmethod
    async def get_input(self, prompt: str) -> str: ...

    @abstractmethod
    async def get_choice(self, options: list[str]) -> int: ...

# Implementations:
# - TerminalInputProvider (stdin/keyboard)
# - APIInputProvider (REST/WebSocket)
```

---

## Mobile Architecture Target

```
otto/
├── core/                     # Platform-agnostic (KEEP)
│   ├── cognitive_orchestrator.py
│   ├── expert_router.py
│   ├── state/
│   └── security/
├── storage/                  # Abstracted storage (DONE)
│   ├── provider.py
│   ├── config.py
│   └── local.py
├── api/                      # New API layer
│   ├── state_api.py
│   ├── dashboard_api.py
│   └── intake_api.py
├── output/                   # New output abstraction
│   ├── formatter.py
│   └── json_formatter.py
└── input/                    # New input abstraction
    ├── provider.py
    └── api_provider.py
```

---

## Migration Steps

1. **[DONE]** Create storage abstraction layer (37 tests)
2. **[DONE]** Create keyring provider abstraction (44 tests)
3. **[DONE]** Document TUI dependencies
4. **[DONE]** Create output formatter abstraction (41 tests)
5. **[DONE]** Create input provider abstraction (59 tests)
6. **[DONE]** Extract status.py logic without ANSI (36 tests)
7. **[DONE]** Extract dashboard.py logic without ANSI (43 tests)
8. **[DONE]** Create mobile build configuration (32 tests)
9. **[DONE]** Define TUI exclusion list in mobile config
10. **[DONE]** Add mobile-specific tests (32 tests)

---

## Completed Abstraction Layers

### Storage Abstraction (`otto/storage/`)
- **Provider**: `StorageProvider` ABC with read/write methods
- **Config**: `StorageConfig` with environment variable support
- **Local**: `LocalStorageProvider` for filesystem
- **Manager**: Global singleton with `get_storage()`
- **Tests**: 37 passing

Environment variables:
- `OTTO_DATA_DIR` - Override otto root
- `ORCHESTRA_DATA_DIR` - Override orchestra root
- `CLAUDE_DATA_DIR` - Override claude root
- `OTTO_CACHE_DIR` - Override cache root

### Keyring Abstraction (`otto/security/keyring_provider.py`)
- **Provider**: `KeyringProvider` ABC
- **System**: `SystemKeyringProvider` (Windows/macOS/Linux)
- **Memory**: `MemoryKeyringProvider` (testing)
- **NoOp**: `NoOpKeyringProvider` (disabled)
- **Manager**: `KeyringManager` with auto-selection
- **Tests**: 44 passing

Environment variables:
- `OTTO_KEYRING_DISABLED=true` - Disable keyring
- `OTTO_KEYRING_BACKEND=memory|system|none` - Force backend

### Output Formatter (`otto/output/`)
- **Formatter**: `OutputFormatter` ABC
- **Plain**: `PlainFormatter` (no colors)
- **JSON**: `JSONFormatter` (structured data)
- **Data classes**: `StatusData`, `AlertData`
- **Tests**: 41 passing

Environment variables:
- `OTTO_OUTPUT_FORMAT=plain|json|ansi` - Set output format

### Input Provider (`otto/input/`)
- **Provider**: `InputProvider` ABC
- **Sync**: `SyncInputProvider` (terminal stdin)
- **Async**: `AsyncInputProvider` (callbacks/queue)
- **Memory**: `MemoryInputProvider` (testing)
- **Data classes**: `InputChoice`, `InputResult`
- **Tests**: 59 passing

Environment variables:
- `OTTO_INPUT_PROVIDER=sync|async|memory` - Set input provider

---

## Total Test Coverage

| Module | Tests |
|--------|-------|
| Storage | 37 |
| Keyring | 44 |
| Output | 41 |
| Input | 59 |
| Status Renderer | 36 |
| Dashboard Renderer | 43 |
| Mobile Build | 32 |
| **Total** | **292** |

---

## New Mobile Abstraction Modules

### Status Renderer (`otto/cli/status_renderer.py`)
- **Renderer**: `StatusRenderer` class with formatter integration
- **Config**: `StatusRenderConfig` for customization
- **Formats**: JSON, plain text, prompt-friendly
- **Global**: `get_status_renderer()`, `set_status_renderer()`
- **Tests**: 36 passing

### Dashboard Renderer (`otto/dashboard_renderer.py`)
- **Renderer**: `DashboardRenderer` class with formatter integration
- **Data**: `CognitiveStateData`, `DashboardSection` dataclasses
- **Formats**: Full dashboard, JSON, status line
- **Global**: `get_dashboard_renderer()`, `set_dashboard_renderer()`
- **Tests**: 43 passing

### Mobile Build Configuration (`otto/mobile/`)
- **Detection**: `is_mobile_build()`, `is_desktop_build()`
- **Capabilities**: `PlatformCapabilities` dataclass
- **Exclusions**: `MOBILE_EXCLUDED_MODULES`, `MOBILE_EXCLUDED_DEPENDENCIES`
- **Config**: `configure_mobile_environment()`
- **Manifest**: `BuildManifest`, `get_build_manifest()`
- **Tests**: 32 passing

Environment variables:
- `OTTO_MOBILE_BUILD=true|false` - Explicit mobile mode
- `OTTO_BUILD_TYPE=mobile|ios|android|desktop` - Build type
