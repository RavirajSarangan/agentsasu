"""Importing this package registers every tool."""

# Importing each module registers its tools.
from . import (  # noqa: F401
    apps,
    clipboard,
    contacts,
    files,
    keyboard,
    media,
    messages,
    productivity,
    screen,
    shell,
    system,
    web,
    windows,
)
from .registry import GUEST_TOOLS, REGISTRY, Tool, ToolContext, ToolResult, schemas

__all__ = ["GUEST_TOOLS", "REGISTRY", "Tool", "ToolContext", "ToolResult", "schemas"]
