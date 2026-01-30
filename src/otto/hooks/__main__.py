"""
Orchestra Hooks Module Entry Point
==================================

Allows running as: python -m orchestra.hooks

Reads JSON from stdin, processes through NEXUS pipeline, outputs JSON to stdout.

Input format:
    {"user_prompt": "your message here"}

Output format:
    {
        "systemMessage": "[EXEC:checksum|expert|paradigm|altitude|depth]\\n\\nGuidance...",
        "hookSpecificOutput": {...}
    }
"""

from .cognitive_hook import main

if __name__ == "__main__":
    main()
