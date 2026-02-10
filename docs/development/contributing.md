# Contributing to OTTO OS

Thank you for your interest in contributing to OTTO OS! This guide will help you get started.

## Getting Started

### 1. Fork and Clone

```bash
# Fork on GitHub, then clone
git clone https://github.com/YOUR_USERNAME/OTTO_OS.git
cd OTTO_OS
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### 3. Verify Setup

```bash
# Run tests
pytest

# Run linting
ruff check .
mypy src/

# Run all checks
pre-commit run --all-files
```

---

## Development Workflow

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/description` | `feature/add-webauthn` |
| Bug Fix | `fix/description` | `fix/auth-token-expiry` |
| Docs | `docs/description` | `docs/api-reference` |
| Refactor | `refactor/description` | `refactor/crypto-engine` |

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation |
| `style` | Formatting |
| `refactor` | Code restructure |
| `test` | Tests |
| `chore` | Maintenance |

**Examples:**

```
feat(api): add WebSocket real-time updates

Implements WebSocket hub for real-time state synchronization.
- Add Channel enum for subscription management
- Add StateChangeMonitor for automatic alerts
- Add comprehensive test suite

Closes #123
```

---

## Code Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints for all public functions
- Maximum line length: 100 characters
- Use `ruff` for linting and formatting

### Documentation

- Docstrings for all public modules, classes, and functions
- Follow [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) docstrings

```python
def process_state(state: Dict[str, Any], *, strict: bool = False) -> StateResult:
    """Process cognitive state and return result.

    Args:
        state: The cognitive state dictionary.
        strict: If True, raise on invalid state.

    Returns:
        Processed state result with validation info.

    Raises:
        StateValidationError: If strict=True and state is invalid.
    """
```

### Testing

- Write tests for all new features
- Maintain >90% code coverage
- Use descriptive test names

```python
class TestWebSocketHub:
    """Tests for WebSocketHub."""

    def test_register_connection_adds_to_hub(self):
        """Test that registering a connection adds it to the hub."""
        hub = WebSocketHub()
        conn = hub.register("conn1", lambda m: None)
        assert hub.connection_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_subscribers_only(self):
        """Test that broadcast only sends to subscribed connections."""
        # ...
```

---

## Determinism

All contributions must maintain determinism:

### Required

1. **Fixed evaluation order** - No runtime variation in processing order
2. **Locked parameters** - Parameters locked before generation
3. **Reproducible outputs** - Same inputs produce same outputs

### Checklist

Before submitting, verify:

- [ ] No `random.choice()` without fixed seed
- [ ] No `dict.items()` iteration without sorting
- [ ] No floating-point comparison issues
- [ ] All algorithms selected at initialization
- [ ] Tests verify determinism

---

## Pull Request Process

### 1. Create PR

- Use the PR template
- Link related issues
- Add appropriate labels

### 2. PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation

## Determinism
- [ ] Fixed evaluation order maintained
- [ ] No new sources of non-determinism
- [ ] Determinism tests added/updated

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Coverage maintained

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings
```

### 3. Review Process

1. Automated checks must pass
2. At least one maintainer review
3. All comments addressed
4. Squash and merge

---

## Testing

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/otto --cov-report=html

# Specific module
pytest tests/test_websocket.py -v

# Determinism tests only
pytest -m determinism
```

### Test Categories

| Marker | Purpose |
|--------|---------|
| `@pytest.mark.asyncio` | Async tests |
| `@pytest.mark.slow` | Long-running tests |
| `@pytest.mark.determinism` | Determinism verification |
| `@pytest.mark.integration` | Integration tests |

---

## Documentation

### Build Docs

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve locally
mkdocs serve

# Build static site
mkdocs build
```

### Adding Pages

1. Create markdown file in `docs/`
2. Add to `nav` in `mkdocs.yml`
3. Link from related pages

---

## Getting Help

- **Questions**: Open a [Discussion](https://github.com/JosephOIbrahim/OTTO_OS/discussions)
- **Bugs**: Open an [Issue](https://github.com/JosephOIbrahim/OTTO_OS/issues)
- **Security**: Email security@otto-os.io

---

## Recognition

Contributors are recognized in:

- `CONTRIBUTORS.md`
- Release notes
- Documentation

Thank you for contributing!
