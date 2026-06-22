#!/usr/bin/env python
"""QuantLib MCP client entry point.

Usage:
    python run_client.py --gui    # Web UI (default)
    python run_client.py --tui    # Terminal UI
    python run_client.py --test   # Quick test
"""
import sys
from src.client.client import app_gui, app_tui, test


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--gui"

    if mode == "--test":
        import asyncio
        asyncio.run(test())
    elif mode == "--tui":
        import asyncio
        asyncio.run(app_tui())
    else:
        app_gui()


if __name__ == "__main__":
    main()
