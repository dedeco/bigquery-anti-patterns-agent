"""FastMCP server implementation"""
from typing import Any, Dict, List, Optional
from .types import MCPServer

class FastMCP(MCPServer):
    def __init__(self, name: str):
        self.name = name
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func
        return decorator 