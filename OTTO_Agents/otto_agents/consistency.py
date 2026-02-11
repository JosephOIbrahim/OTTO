"""He2025 Consistency Agent — Determinism auditor for OTTO.

Scans the OTTO codebase for violations of He2025 determinism principles:

1. Missing sort_keys=True in json.dumps() calls
2. Unsorted dict iteration (for/dict without sorted())
3. uuid.uuid4() in hot paths (should use hashlib-based IDs)
4. time.time() used in seeds or hashing
5. Missing Kahan summation in numerical aggregation
6. set() iteration without sorting (nondeterministic order)
7. random module usage without fixed seed
8. PYTHONHASHSEED-dependent hash() calls

Uses Claude Agent SDK with Read/Grep/Glob tools to analyze the codebase.
Reports violations with file, line, and remediation guidance.

Reference: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)


CONSISTENCY_SYSTEM_PROMPT = """\
You are OTTO's He2025 Consistency Agent. Your job is to audit the OTTO
codebase for determinism violations.

## Background

OTTO follows He2025 principles for application-level determinism:
"Same signals + same state = same routing." Every control flow path
must produce identical results given identical inputs.

Reference: ThinkingMachines blog, "Defeating Nondeterminism in LLM Inference"
(addresses GPU kernel nondeterminism; OTTO applies the principle at the
application layer).

## What to Check

Scan all Python files in the OTTO codebase for these violations:

### CRITICAL (breaks determinism)
1. **json.dumps() without sort_keys=True** -- dict serialization order is
   implementation-dependent. Every json.dumps() call MUST include sort_keys=True.
2. **Dict iteration without sorted()** -- `for k in dict` or `for k, v in dict.items()`
   without wrapping in `sorted()`. Dict iteration order is insertion-order in Python 3.7+
   but NOT deterministic across processes with different insertion patterns.
3. **set() iteration** -- Sets have no guaranteed order. Must convert to sorted list.
4. **hash() on strings** -- PYTHONHASHSEED-dependent. Use hashlib.sha256() instead.

### HIGH (likely breaks determinism)
5. **uuid.uuid4() in hot paths** -- Random UUIDs. Acceptable for database IDs
   (generated once), NOT acceptable in template selection, routing, or aggregation.
6. **time.time() in seeds/hashing** -- Time-dependent behavior breaks reproducibility.
7. **random module without seed** -- random.choice(), random.shuffle() etc.

### MEDIUM (potential issue)
8. **Floating-point aggregation without Kahan summation** -- sum() on float lists
   can produce different results based on accumulation order. Use Kahan summation
   for trail decay and batch invariance calculations.
9. **os.listdir() / glob without sorting** -- Filesystem ordering is OS-dependent.

## How to Audit

1. Use Grep to find all json.dumps() calls -> verify sort_keys=True
2. Use Grep to find dict iteration patterns -> verify sorted()
3. Use Grep to find hash(), uuid4(), time.time(), random.* usage
4. Use Grep to find sum() on float lists -> check for Kahan pattern
5. Use Read to examine suspicious files in detail

## Output Format

For each violation found, report:
- **File**: path relative to otto_v4/
- **Line**: line number
- **Severity**: CRITICAL / HIGH / MEDIUM
- **Pattern**: what you found
- **Fix**: specific remediation

At the end, provide a summary:
- Total violations by severity
- Files with most violations
- Overall determinism score (0-100%)

## Important Notes

- Focus on otto_v4/src/otto/ and otto_v4/otto_agent/ directories
- Skip test files (they can use non-deterministic patterns)
- Skip __pycache__ directories
- uuid.uuid4() for database primary keys is ACCEPTABLE (generated once at creation)
- The existing nudge.py already uses hashlib for template selection -- verify this is correct
"""


async def run_consistency(
    *,
    target_dir: str | None = None,
    verbose: bool = False,
) -> None:
    """Run the He2025 consistency audit on the OTTO codebase.

    Parameters
    ----------
    target_dir:
        Directory to audit. Defaults to otto_v4/.
    verbose:
        If True, print all messages including tool calls.
    """
    cwd = target_dir or str(
        Path(__file__).resolve().parent.parent.parent / "otto_v4"
    )

    options = ClaudeAgentOptions(
        system_prompt=CONSISTENCY_SYSTEM_PROMPT,
        allowed_tools=["Read", "Grep", "Glob"],
        permission_mode="bypassPermissions",
        max_turns=30,
        cwd=cwd,
    )

    prompt = (
        "Perform a full He2025 determinism audit on the OTTO codebase. "
        "Scan all Python files in src/otto/ and otto_agent/ for violations. "
        "Report each violation with file, line, severity, pattern, and fix. "
        "End with a summary and determinism score."
    )

    print("He2025 Consistency Audit")
    print(f"Target: {cwd}")
    print("-" * 60)

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text, end="")
            elif isinstance(message, ResultMessage):
                if message.is_error:
                    print(f"\n[Error: {message.result}]")
                elif message.total_cost_usd is not None:
                    print(f"\n\n[Audit cost: ${message.total_cost_usd:.4f}]")
        print()
