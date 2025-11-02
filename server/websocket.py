
import asyncio
import json
import websockets
from typing import Dict

# plugin wrappers
from plugins.mediacontroller_plugin import MediaControllerPlugin


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
        self.plugins = [MediaControllerPlugin()]

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
