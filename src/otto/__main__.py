"""
Entry point for running Orchestra as a module.

Usage:
    cd C:\\Users\\User\\Orchestra
    python -m src.orchestra --task "Your task"
    python -m src.orchestra --info
    python -m src.orchestra --health
"""

import asyncio
from .framework_orchestrator import main

if __name__ == "__main__":
    asyncio.run(main())
