from typing import Any, Dict, Optional, Callable

class Wrapper:
    """Base plugin class. Plugins should subclass this and fill `actions`."""
    def __init__(self):
        # server is optional; useful for broadcasting or accessing state
        self.name = "PluginBase"
        self.prefix = "base_"
        self.actions: Dict[str, Callable[..., Any]] = {}