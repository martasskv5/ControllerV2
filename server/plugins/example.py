from typing import Any, Dict

class YourPlugin:
    def __init__(self):
        self.name = "yourplugin"
        self.actions = {
            "say_hello": self.say_hello,
        }

    async def say_hello(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        name = msg.get("name", "world")
        return {"ok": True, "greeting": f"hello, {name}"}