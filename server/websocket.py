
import asyncio
import json
import websockets
import pkgutil
import importlib
import inspect
from typing import Dict

# plugin wrappers
# from plugins.mediacontroller_plugin import MediaControllerPlugin

def load_plugins(package_name: str = "plugins"):
    plugins = []
    try:
        package = importlib.import_module(package_name)
    except Exception as e:
        print(f"plugin discovery: failed to import package '{package_name}': {e}")
        return plugins

    try:
        pkg_path = package.__path__
    except AttributeError:
        print(f"plugin discovery: package '{package_name}' has no __path__")
        return plugins

    for finder, name, ispkg in pkgutil.iter_modules(pkg_path):
        if name.startswith("_"):
            continue
        module_name = f"{package_name}.{name}"
        print(f"plugin discovery: trying to load {module_name}")
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            print(f"plugin discovery: failed to import {module_name}: {e}")
            continue

        # require a class named Wrapper in the module
        WrapperCls = getattr(module, "Wrapper", None)
        if isinstance(WrapperCls, type):
            try:
                inst = WrapperCls()
            except Exception as e:
                print(f"plugin instantiation failed for {module_name}.Wrapper: {e}")
                continue
            if hasattr(inst, "actions") and isinstance(inst.actions, dict):
                plugins.append(inst)

    return plugins


class WebSocketServer:
    """JSON command WebSocket server that delegates to a list of plugins.
    Each plugin must expose an `actions` dict mapping action names to
    async handlers accepting a message dict and returning a response dict.
    """

    def __init__(self, host: str = "localhost", port: int = 21234):
        self.host = host
        self.port = port
        self.connected_clients = set()
        # register plugins here; to add a new plugin, append an instance
        self.plugins = load_plugins()

    async def handler(self, websocket):
        # Register client
        self.connected_clients.add(websocket)
        try:
            async for raw in websocket:
                try:
                    msg = json.loads(raw)
                except Exception:
                    await websocket.send(json.dumps({"ok": False, "error": "invalid_json"}))
                    continue
                # dispatch to plugins
                resp = await self.handle_command(msg)
                try:
                    await websocket.send(json.dumps(resp))
                except Exception:
                    # ignore send errors for now
                    pass
        finally:
            # Unregister client
            self.connected_clients.remove(websocket)

    async def handle_command(self, msg: Dict):
        action = msg.get("action")
        if not action:
            return {"ok": False, "error": "missing_action"}

        # find first plugin that knows this action
        for p in self.plugins:
            handler = p.actions.get(action)
            if handler:
                try:
                    return await handler(msg)
                except Exception as e:
                    return {"ok": False, "error": str(e)}

        return {"ok": False, "error": "unknown_action"}

    def start(self):
        # Prefer using asyncio.run(self.run()) to start the async server.
        return asyncio.run(self.run())

    async def run(self):
        # run the websockets server inside an async context manager
        async with websockets.serve(self.handler, self.host, self.port):
            print(f"WebSocket command server started at ws://{self.host}:{self.port}")
            # keep running until cancelled
            await asyncio.Future()


if __name__ == "__main__":
    srv = WebSocketServer()
    srv.start()
