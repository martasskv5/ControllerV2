from .base import Wrapper as PluginBase
from typing import Any, Dict, cast, Optional
from pyKey import pressKey, releaseKey

class Wrapper(PluginBase):
    def __init__(self):
        self.name = "keyboard"
        self.prefix = "k_"
        self.kc = KeyboardController()
        self.actions = {
            "k_press": self.press_key,
            "k_hold": self.hold_key,
            "k_release": self.release_key
        }
        
    async def press_key(self, message: Dict[str, Any]) -> Dict[str, Any]:
        key = message.get("key")
        if key is None:
            return {"status": "error", "message": "missing 'key' in message"}
        if not isinstance(key, str):
            return {"status": "error", "message": "'key' must be a string"}
        key_str = cast(str, key)
        return self.kc.press_key(key, key_str)
    
    async def hold_key(self, message: Dict[str, Any]) -> Dict[str, Any]:
        key = message.get("key")
        if key is None:
            return {"status": "error", "message": "missing 'key' in message"}
        if not isinstance(key, str):
            return {"status": "error", "message": "'key' must be a string"}
        key_str = cast(str, key)
        return self.kc.hold_key(key, key_str)

    async def release_key(self, message: Dict[str, Any]) -> Dict[str, Any]:
        key = message.get("key")
        if key is None:
            return {"status": "error", "message": "missing 'key' in message"}
        if not isinstance(key, str):
            return {"status": "error", "message": "'key' must be a string"}
        key_str = cast(str, key)
        return self.kc.release_key(key, key_str)

class KeyboardController:

    def press_key(self, key_code: Any, key_name: Optional[str] = None) -> Dict[str, Any]:
        try:
            pressKey(key_code)
            releaseKey(key_code)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        return {"status": "success", "key_pressed": key_name or str(key_code)}

    def hold_key(self, key_code: Any, key_name: Optional[str] = None) -> Dict[str, Any]:
        try:
            pressKey(key_code)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        return {"status": "success", "key_held": key_name or str(key_code)}

    def release_key(self, key_code: Any, key_name: Optional[str] = None) -> Dict[str, Any]:
        try:
            releaseKey(key_code)
        except Exception as e:
            return {"status": "error", "message": str(e)}

        return {"status": "success", "key_released": key_name or str(key_code)}