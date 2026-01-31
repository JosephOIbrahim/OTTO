# Otto Advancement Roadmap

**Status:** v5.0.1 Shipped | Public Repository | CI Green | 798 Tests Passing

---

## Current State (2026-01-26)

### Shipped
- ✅ Otto v5.0.1 production-stable
- ✅ 798 tests passing (including 22 property-based + 7 fuzz tests)
- ✅ CI/CD with matrix testing (Ubuntu/Windows × Python 3.10-3.12)
- ✅ Code coverage in CI (50% threshold, Codecov integration)
- ✅ Branch protection on main
- ✅ ThinkingMachines [He2025] compliant
- ✅ Public on GitHub

### Tier 1 Features (Completed)
- ✅ Property-based testing with Hypothesis
- ✅ MCP server package (otto-mcp)
- ✅ Context engineering alignment documentation

### Tier 2 Features (Completed)
- ✅ Fuzz testing with Hypothesis (7 tests, Atheris on Linux CI)
- ✅ Semgrep determinism rules (9 rules in `.semgrep/otto-determinism.yaml`)
- ✅ Code coverage in CI (50% threshold with Codecov upload)
- ✅ json.dumps determinism fixes (sort_keys=True in all persistence files)

### Tier 3 Features (Completed)
- ✅ PyPI publish workflows (otto-os + otto-mcp)
- ✅ PR automation workflow (differential review with Semgrep checks)
- ✅ Security audit (pip-audit - see findings below)

---

## Security Audit Results

pip-audit found 8 vulnerabilities in 7 packages (system-wide, not Otto-specific):

| Package | CVE | Fix Version | Otto Impact |
|---------|-----|-------------|------------------|
| filelock | CVE-2025-68146, CVE-2026-22701 | 3.20.3 | Low (dev dependency) |
| urllib3 | CVE-2026-21441 | 2.6.3 | Low (requests dep) |
| setuptools | PYSEC-2025-49 | 78.1.1 | Low (build only) |
| pyasn1 | CVE-2026-23490 | 0.6.2 | None (not used) |
| rpyc | PYSEC-2024-44 | 6.0.0 | None (not used) |
| protobuf | CVE-2026-0994 | No fix yet | Low (optional dep) |

**Recommendation:** Update `filelock>=3.20.3` and `urllib3>=2.6.3` when stable.

---

## MCP Server Deployment

### Status: Ready for PyPI

The `otto-mcp` package is ready:

```bash
# Build verified
otto_mcp-1.0.0.tar.gz
otto_mcp-1.0.0-py3-none-any.whl

# Twine check: PASSED
```

### Publishing

1. **Manual (TestPyPI first):**
   ```bash
   cd packages/otto-mcp
   python -m twine upload --repository testpypi dist/*
   ```

2. **Via GitHub Actions:**
   - Go to Actions → "Publish otto-mcp to PyPI"
   - Run workflow → Select "testpypi" or "pypi"

3. **On Release:**
   - Create a GitHub Release → Auto-publishes to PyPI

### Installation (After PyPI Publication)
```bash
pip install otto-mcp
```

---

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `tests.yml` | Push/PR to master | Matrix tests + coverage |
| `fuzz.yml` | Push/PR + weekly | Fuzz testing (Linux only) |
| `pr-review.yml` | PR events | Automated review + Semgrep |
| `publish.yml` | Release/manual | Publish otto-os |
| `publish-mcp.yml` | Release/manual | Publish otto-mcp |
| `ci.yml` | Push/PR | Legacy CI (linting, type check) |

---

## Semgrep Determinism Rules

9 rules enforcing ThinkingMachines [He2025] compliance:

| Rule | Severity | Purpose |
|------|----------|---------|
| `otto-unseeded-random` | ERROR | Detect unseeded random |
| `otto-dict-iteration-unsorted` | WARNING | Catch unordered dict iteration |
| `otto-json-dumps-no-sort-keys` | WARNING | Enforce deterministic JSON |
| `otto-time-in-routing` | ERROR | Prevent time-based routing |
| `otto-state-mutation-without-batch` | ERROR | Enforce atomic state changes |
| `otto-set-iteration` | WARNING | Flag unordered set iteration |
| `otto-async-gather-unordered` | INFO | Warn about gather ordering |
| `otto-thinking-depth-bypass` | WARNING | Catch unconditional deep thinking |
| `otto-burnout-override` | WARNING | Prevent direct burnout manipulation |

**Current findings:** 73 (all WARNING/INFO level, display-only outputs)

---

## Metrics

| Metric | Previous | Current | Target |
|--------|----------|---------|--------|
| Test count | 792 | 798 | 850+ |
| Property tests | 15 | 22 | 25+ |
| Fuzz tests | 0 | 7 | 10+ |
| Code coverage | Unknown | 50%+ | 90%+ |
| Determinism score | 100% | 100% | 100% |
| Semgrep errors | N/A | 0 | 0 |

---

## Next Steps

### Immediate
1. **Publish to TestPyPI** - Verify installation works
2. **Publish to PyPI** - Make packages available
3. **Test Claude Desktop integration** - Verify MCP server works

### Future
1. **Academic paper** - Convert substrate spec to LaTeX/arXiv
2. **Multi-model support** - Not just Claude
3. **Community adoption** - MCP ecosystem integration

---

## Academic Publication Pipeline

Three repos form a coherent publication suite:

| Repo | Content | Status |
|------|---------|--------|
| **persistent-state-hypothesis** | Theory paper | Public |
| **usd-cognitive-substrate** | Specification | Public |
| **Otto** | Implementation | Public, v5.0.1 |

---

*Updated: 2026-01-26 (Tier 2/3 complete)*
