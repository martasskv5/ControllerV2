
import asyncio
import json
import websockets
import pkgutil
import importlib
import inspect
import threading
import time
import sys
try:
    import msvcrt
except Exception:
    msvcrt = None
from typing import Dict

# plugin wrappers
# from plugins.mediacontroller_plugin import MediaControllerPlugin

def load_plugins(package_name: str = "plugins", server=None):
    """Discover and instantiate plugins from the given package name.

    Each plugin module should define a class named `Wrapper`. The constructor
    may accept an optional server parameter. Returned plugins are instances
    that expose an `actions` dict.
    """
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
                # try server-aware constructor first
                try:
                    inst = WrapperCls(server)
                except TypeError:
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
            # store running loop so background threads can schedule work
            self.loop = asyncio.get_running_loop()
            # create a future we can complete to stop the server
            self._stop_future = self.loop.create_future()

            # start keyboard watcher thread (Ctrl+R to reload plugins)
            self._stop_event = threading.Event()
            self._kbd_thread = threading.Thread(target=self._keyboard_watcher, daemon=True)
            self._kbd_thread.start()

            try:
                await self._stop_future
            finally:
                # signal keyboard thread to stop and wait briefly
                self._stop_event.set()
                if self._kbd_thread.is_alive():
                    self._kbd_thread.join(timeout=0.2)

    def stop(self):
        self.connected_clients.clear()
        # stop the async run loop if running
        try:
            if hasattr(self, "loop") and hasattr(self, "_stop_future") and not self._stop_future.done():
                self.loop.call_soon_threadsafe(self._stop_future.set_result, None)
        except Exception:
            pass
        
    def reload_plugins(self):
        # synchronous reload (safe if called from main thread)
        print("Reloading plugins...")
        self.plugins = load_plugins(server=self)
        print(f"Reloaded {len(self.plugins)} plugins")

    def _do_reload(self):
        # helper to be scheduled on the event loop
        try:
            self.reload_plugins()
        except Exception as e:
            print(f"plugin reload failed: {e}")

    def _keyboard_watcher(self):
        """Background thread that watches console keys and triggers reload on Ctrl+R.

        Uses msvcrt on Windows; if unavailable, does nothing.
        """
        if msvcrt is None:
            return
        print("Keyboard watcher started (press Ctrl+R to reload plugins)")
        while not getattr(self, "_stop_event", threading.Event()).is_set():
            try:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    # Ctrl+R -> ASCII 18
                    if ch and ord(ch) == 18:
                        print("Ctrl+R detected -> scheduling plugin reload")
                        try:
                            # schedule reload on the asyncio loop
                            if hasattr(self, "loop"):
                                self.loop.call_soon_threadsafe(self._do_reload)
                        except Exception as e:
                            print(f"Failed to schedule reload: {e}")
                else:
                    time.sleep(0.05)
            except Exception:
                # swallow keyboard read errors and keep looping
                time.sleep(0.1)


if __name__ == "__main__":
    try:
        srv = WebSocketServer()
        srv.start()
    except Exception as e:
        print(f"Error starting WebSocket server: {e}")
    except KeyboardInterrupt:
        print("WebSocket server stopped by user")
        srv.stop()
    