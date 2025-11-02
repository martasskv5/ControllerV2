# ControllerV2 - Server

A small Windows media controller service exposing a JSON WebSocket API to list media sessions, control playback, and set per-session volume.

This project uses Windows Global System Media Transport Controls (via `winrt`) to enumerate and control media sessions and `pycaw` to set per-process audio volume where possible.

---

## Features

- List active media sessions (title, artist, source, playback status, volume estimate)
- Control playback: play, pause, next, previous
- Best-effort per-session volume control using pycaw
- Plugin-based WebSocket command dispatch: add new commands by writing a plugin under `server/plugins`


## Requirements

- Windows 10/11
- Python 3.10+ (code has been tested with modern 3.14 install)
- The following Python packages (install via pip):
  - websockets
  - winrt
  - pycaw
  - comtypes

Note: `pycaw` may require `comtypes` and proper audio drivers. Running the script with elevated permissions can help in some environments.

Install the main dependencies with:

```powershell
python -m pip install --upgrade pip
pip install websockets winrt pycaw comtypes
```


## Files of interest

- `server/MediaController.py` - core logic that talks to Windows (GSMA) and pycaw. Contains helpers to list sessions and set volume.
- `server/websocket.py` - WebSocket JSON command server. Delegates commands to plugin(s).
- `server/plugins/mediacontroller_plugin.py` - plugin wrapper exposing MediaController actions as command handlers.
- `server/main.py` - simple demo/test harness for MediaController.


## Running the server

Start the WebSocket server (default: ws://localhost:21234):

```powershell
python .\server\websocket.py
```

You should see a message like:

```
WebSocket command server started at ws://localhost:21234
```


## WebSocket JSON protocol

Send JSON messages (one object per message). Server replies with a JSON response.

Supported commands (via the `mediacontroller` plugin):

- List sessions
  - Request: `{ "action": "list" }`
  - Response: `{ "ok": true, "sessions": [ { "id": "...", "title": "...", "artist": "...", "volume": 0.5, ... }, ... ] }`

- Set volume
  - Request: `{ "action": "set_volume", "id": "<session id>|current|null", "level": 0.5 }`
    - `level` accepts `0.0-1.0` or `0-100` (percentage) and is normalized to `0.0-1.0`.
  - Response: `{ "ok": true }` or `{ "ok": false, "error": "..." }`

- Playback control
  - Play: `{ "action": "play", "id": "<session id>|current" }`
  - Pause: `{ "action": "pause", "id": "<session id>|current" }`
  - Next: `{ "action": "next", "id": "<session id>|current" }` (id optional)
  - Previous: `{ "action": "previous", "id": "<session id>|current" }`
  - Response: `{ "ok": true }` or `{ "ok": false, "error": "..." }`

Notes:
- You can use `"id": "current"` or omit `id` to target the current session returned by the system.
- The `list` response includes a `session`-like object filtered to JSON-serializable fields. Use the `id` value for subsequent commands.


## Client examples

Python async example (requires `websockets`):

```python
import asyncio, json, websockets

async def run():
    uri = "ws://localhost:21345"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"action":"list"}))
        resp = json.loads(await ws.recv())
        print("list:", resp)

        sessions = resp.get("sessions", [])
        if sessions:
            sid = sessions[0]["id"]
            await ws.send(json.dumps({"action":"set_volume", "id": sid, "level": 30}))
            print("set_volume:", await ws.recv())

asyncio.run(run())
```

Browser example (JavaScript):

```javascript
const ws = new WebSocket("ws://localhost:21345");
ws.onopen = () => ws.send(JSON.stringify({ action: "list" }));
ws.onmessage = ev => {
  const msg = JSON.parse(ev.data);
  console.log('server:', msg);
  if (msg.sessions && msg.sessions.length) {
    const id = msg.sessions[0].id;
    ws.send(JSON.stringify({ action: 'set_volume', id, level: 50 }));
  }
};
```


## Plugin system (extending commands)

- Plugins live in `server/plugins/`.
- Each plugin should expose an `actions` mapping: `{ "action_name": async_handler }`.
  - `async_handler(msg: dict) -> dict` where the dict is JSON-serializable and contains `ok` and optional `error`.
- The server iterates plugins in `WebSocketServer.plugins` and dispatches the command to the first plugin that implements the requested `action` name.

Example plugin template (see `server/plugins/mediacontroller_plugin.py`):

```python
class MyPlugin:
    def __init__(self):
        self.actions = {
            "say_hello": self.say_hello,
        }

    async def say_hello(self, msg):
        name = msg.get("name", "world")
        return {"ok": True, "greeting": f"hello, {name}"}
```

To register a plugin, add an instance to `WebSocketServer.plugins` in `server/websocket.py`, or (future enhancement) implement auto-discovery under `server/plugins/`.


## Troubleshooting

- RuntimeError: `no running event loop` or related event loop errors
  - Make sure you run the server with `python .\server\websocket.py` (the server uses `asyncio.run` internally).

- Volume not changing for a session
  - `find_volume_for_session` uses heuristics to match the GSMA session to a pycaw audio session. This may fail for some apps or when process/display names don't match.
  - Run `{ "action":"list" }` and inspect returned `source` and `title` fields. Share them and I can help tune matching heuristics.
  - `pycaw` may require specific permissions. Try running the script with elevated privileges.

- Missing dependencies / import errors
  - Install dependencies shown above. If `winrt` import fails, ensure you're on a supported Windows and Python version.


## Next steps / suggestions

- Add plugin auto-discovery (load all plugins under `server/plugins` automatically)
- Add a small `requirements.txt` and optionally a venv activation script
- Add logging and optional broadcast helper so plugins can push events to all connected clients
- Improve/diagnose `pycaw` session matching heuristics if some apps don't respond to volume changes


## License

This project is provided as-is for experimentation and personal use.
