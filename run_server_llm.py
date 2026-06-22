#!/usr/bin/env python
"""MCP server with LLM-enhanced tools entry point."""
import sys
from src.server.server_llm import mcp

if __name__ == "__main__":
    # If called by mcp dev, export the official Server object

    if "mcp" in sys.modules and hasattr(mcp, "_server"):
        # fastmcp has an official Server object embedded, expose it
        mcp._server.run()
    else:
        # If called by manual python server.py, use fastmcp's own startup
        mcp.run()