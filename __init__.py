"""Brain Guard Plugin - OpenClaw Integration Entry Point.

This module exposes the OpenClaw plugin interface for Brain Guard.
Import this module to access the plugin hooks.
"""

# Import and re-export the OpenClaw interface
from .openclaw_plugin import (
    OpenClawBrainGuardPlugin,
    get_openclaw_plugin,
    initialize,
    shutdown,
    onMessage,
    onResponse,
    health,
)

# Also export the core BrainGuardPlugin for direct access
from .src.brain_guard_plugin import BrainGuardPlugin, get_plugin, initialize_plugin

__all__ = [
    # OpenClaw interface
    "OpenClawBrainGuardPlugin",
    "get_openclaw_plugin",
    "initialize",
    "shutdown",
    "onMessage",
    "onResponse",
    "health",
    # Core plugin
    "BrainGuardPlugin",
    "get_plugin",
    "initialize_plugin",
]
