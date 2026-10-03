from typing import Any, Awaitable, Callable, Dict, Optional
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
from pycaw.pycaw import AudioUtilities, AudioSession, IAudioMeterInformation
from .base import Wrapper as PluginBase
import re
import json
import asyncio
import hashlib

class Wrapper(PluginBase):
    """Plugin wrapper exposing MediaController actions as named handlers.

    Each plugin exposes an `actions` dict mapping action name -> async handler(msg) -> dict response.
    """

    def __init__(self, server=None):
        # super().__init__(server)
        self.name = "mediacontroller"
        self.prefix = "mc_"
        self.mc = MediaController()
        self.server = server
        # map action name to handler coroutine
        self.actions: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
            "mc_list": self.list_handler,
            "mc_set_volume": self.set_volume_handler,
            "mc_play": self.play_handler,
            "mc_pause": self.pause_handler,
            "mc_next": self.next_handler,
            "mc_previous": self.previous_handler,
        }        
        # Server reference stored for later use
        self.server = server
        self._monitoring_started = False
        # Store event tokens to prevent garbage collection
        self._event_tokens = []
        # Last known state to prevent duplicate broadcasts
        self._last_state = None
        # Cache mapping stable id -> session object
        self._session_cache = {}
        
    def format_message(self, ok: bool, error: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if data is None:
            data = {}
        message = {
            "ok": ok,
            "type": self.name,
            **({"error": error} if error is not None else {}),
            **data
        }
        return message

    async def list_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        # Start monitoring if not already started and server is running
        if not self._monitoring_started and self.server and hasattr(self.server, 'loop'):
            self._monitoring_started = True
            await self._setup_session_monitoring()
        
        ml = await self.mc.get_media_list()
        safe = []
        # rebuild session cache for fresh session objects
        self._session_cache.clear()
        for i in ml:
            sess = i.get("session")
            source = (i.get("source") or "") or ""
            title = (i.get("title") or "") or ""
            artist = (i.get("artist") or "") or ""
            album = (i.get("album") or "") or ""
            key = f"{source}|{title}|{artist}|{album}"
            sid = hashlib.sha1(key.encode("utf-8")).hexdigest()
            # store mapping to the session object for later commands
            if sess:
                self._session_cache[sid] = sess

            s = {k: v for k, v in i.items() if k != "session"}
            s["id"] = sid
            safe.append(s)
        return self.format_message(True, data={"sessions": safe})

    async def set_volume_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        level = msg.get("level")
        sid = msg.get("id", None)
        s = await self._resolve_session_for_command(sid)
        if s is None:
            return self.format_message(False, error="session_not_found")
        success = self.mc.try_set_volume(s, level)
        return self.format_message(bool(success))

    async def play_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        return await self._call_simple_action(msg, self.mc.try_play)

    async def pause_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        return await self._call_simple_action(msg, self.mc.try_pause)

    async def next_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        return await self._call_simple_action(msg, self.mc.try_next)

    async def previous_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        return await self._call_simple_action(msg, self.mc.try_previous)

    async def _call_simple_action(self, msg, action_callable) -> Dict[str, Any]:
        sid = msg.get("id", None)
        s = await self._resolve_session_for_command(sid)
        if s is None:
            return self.format_message(False, error="session_not_found")
        # action_callable may be async
        await action_callable(s)
        return self.format_message(True)

    async def _resolve_session_for_command(self, id_or_none):
        if id_or_none is None or id_or_none == "current":
            return await self.mc.resolve_session(None)
        if hasattr(id_or_none, "try_get_media_properties_async"):
            return id_or_none
        # First try our cache (stable ids)
        if isinstance(id_or_none, str) and id_or_none in self._session_cache:
            return self._session_cache[id_or_none]

        # Fallback: try lookup by hashed id produced earlier (legacy behavior)
        mgr = await self.mc.get_manager()
        for s in mgr.get_sessions():
            try:
                if str(hash(s)) == str(id_or_none):
                    return s
            except Exception:
                continue

        # As a last resort, try to resolve by matching source or title tokens
        try:
            for s in mgr.get_sessions():
                try:
                    props = await s.try_get_media_properties_async()
                except Exception:
                    continue
                source = getattr(s, "source_app_user_model_id", "") or ""
                title = getattr(props, "title", "") or ""
                candidate_key = f"{source}|{title}|"
                if isinstance(id_or_none, str) and id_or_none in candidate_key:
                    return s
        except Exception:
            pass

        return None

    async def _setup_session_monitoring(self):
        """Set up event listeners for media session changes."""
        try:
            mgr = await self.mc.get_manager()
            
            # Subscribe to session changes
            token = mgr.add_current_session_changed(self._on_current_session_changed)
            self._event_tokens.append(token)
            token = mgr.add_sessions_changed(self._on_sessions_changed)
            self._event_tokens.append(token)
            
            # Monitor each existing session
            for session in mgr.get_sessions():
                await self._setup_session_listeners(session)
                
            print("Media session monitoring started")
            # Initial state broadcast
            await self._broadcast_media_list()
        except Exception as e:
            print(f"Failed to set up media session monitoring: {e}")
    
    async def _setup_session_listeners(self, session):
        """Set up event listeners for an individual session."""
        try:
            if not session:
                return
                
            # Get initial properties to ensure the session is valid
            try:
                await session.try_get_media_properties_async()
            except Exception:
                print("Skipping invalid session")
                return
                
            token = session.add_media_properties_changed(self._on_media_properties_changed)
            self._event_tokens.append(token)
            token = session.add_playback_info_changed(self._on_playback_info_changed)
            self._event_tokens.append(token)
            print(f"Set up listeners for session: {getattr(session, 'source_app_user_model_id', 'unknown')}")
        except Exception as e:
            print(f"Failed to set up session listeners: {e}")

    def _on_current_session_changed(self, mgr, args):
        """Handler for when the current media session changes."""
        if self.server and hasattr(self.server, "loop"):
            asyncio.run_coroutine_threadsafe(self._broadcast_media_list(), self.server.loop)

    def _on_sessions_changed(self, mgr, args):
        """Handler for when the available sessions list changes."""
        if self.server and hasattr(self.server, "loop"):
            async def handle_sessions_changed():
                # Set up listeners for any new sessions
                for session in mgr.get_sessions():
                    await self._setup_session_listeners(session)
                await self._broadcast_media_list()
            
            asyncio.run_coroutine_threadsafe(handle_sessions_changed(), self.server.loop)

    def _on_media_properties_changed(self, session, args):
        """Handler for when media properties (title, artist, etc.) change."""
        if self.server and hasattr(self.server, "loop"):
            asyncio.run_coroutine_threadsafe(self._broadcast_media_list(), self.server.loop)

    def _on_playback_info_changed(self, session, args):
        """Handler for when playback status changes."""
        if self.server and hasattr(self.server, "loop"):
            asyncio.run_coroutine_threadsafe(self._broadcast_media_list(), self.server.loop)

    async def _broadcast_media_list(self):
        """Send updated media list to all connected clients."""
        if not self.server:
            return
            
        try:
            # Get current media list
            result = await self.list_handler({})
            if result.get("ok"):
                # Check if state actually changed
                current_state = json.dumps(result, sort_keys=True)
                if current_state == self._last_state:
                    return
                self._last_state = current_state
                
                msg_str = json.dumps(result)
                for client in self.server.connected_clients:
                    try:
                        await client.send(msg_str)
                    except Exception:
                        # Ignore failed sends to individual clients
                        pass
                print("Broadcasted media update")
        except Exception as e:
            print(f"Failed to broadcast media list: {e}")

class MediaController:

    async def get_manager(self):
        return await GlobalSystemMediaTransportControlsSessionManager.request_async()

    async def get_media_list(self):
        mgr = await self.get_manager()
        sessions = mgr.get_sessions()
        out = []
        for s in sessions:
            props = await s.try_get_media_properties_async()
            info = s.get_playback_info()
            title = getattr(props, "title", None)
            artist = getattr(props, "artist", None)
            album = getattr(props, "album_title", None) or getattr(props, "albumTitle", None)
            status = getattr(info, "playback_status", None)
            is_playing = (status is not None and status.name == "PLAYING") or (str(status).lower() == "playing")
            source = getattr(s, "source_app_user_model_id", None)
            vol = self.find_volume_for_session(s)
            peak = self.find_meter_for_session(s)
            out.append({
                "id": str(hash(s)),  # stable per-process run similar to GetHashCode()
                "title": title,
                "artist": artist,
                "album": album,
                "is_playing": is_playing,
                "status": str(status),
                "source": source,
                "volume": vol,
                "audio_level": peak,
                "session": s,  # keep session if you want to control it directly
            })
        return out

    def find_meter_for_session(self, gsma_session):
        """Best-effort match using pycaw AudioMeterInformation peak values."""
        try:
            source = (gsma_session.source_app_user_model_id or "") or ""
            source = source.lower()

            def norm(name: str) -> str:
                if not name:
                    return ""
                n = name.lower()
                n = re.sub(r"\.exe$", "", n)
                n = re.sub(r"[^a-z0-9]+", " ", n)
                return n.strip()

            sessions: list[AudioSession] = AudioUtilities.GetAllSessions()
            for sess in sessions:
                try:
                    proc = sess.Process
                    proc_name = proc.name() if proc else ""
                except Exception:
                    proc_name = ""
                display = (sess.DisplayName or "") or ""
                proc_name_n = norm(proc_name)
                display_n = norm(display)

                matched = False
                if proc_name_n and (proc_name_n in source or proc_name_n in display_n or proc_name_n in source.replace('.', ' ')):
                    matched = True
                if not matched and display_n and (display_n in source or display_n in proc_name_n):
                    matched = True
                if not matched and not source and proc_name_n and proc_name_n == display_n:
                    matched = True

                if matched:
                    try:
                        meter = sess._ctl.QueryInterface(IAudioMeterInformation)
                        peak = meter.GetPeakValue()
                        return max(0.0, min(1.0, float(peak)))
                    except Exception:
                        pass
        except Exception:
            print("Error finding audio meter for session")
            pass
        return None

    def find_volume_for_session(self, gsma_session):
        """Best-effort match using pycaw AudioUtilities.GetAllSessions()."""
        try:
            source = (gsma_session.source_app_user_model_id or "") or ""
            source = source.lower()
            # helper to normalize process/display names (strip .exe etc)
            def norm(name: str) -> str:
                if not name:
                    return ""
                n = name.lower()
                # remove extension
                n = re.sub(r"\.exe$", "", n)
                # replace non-alphanumeric with spaces for safer substring checks
                n = re.sub(r"[^a-z0-9]+", " ", n)
                return n.strip()
            sessions = AudioUtilities.GetAllSessions()
            for sess in sessions:
                try:
                    proc = sess.Process
                    proc_name = proc.name() if proc else ""
                except Exception:
                    proc_name = ""
                display = (sess.DisplayName or "") or ""
                proc_name_n = norm(proc_name)
                display_n = norm(display)
                icon = ""  # pycaw doesn't expose icon path readily
                # heuristics similar to C# code
                # match heuristics: check token presence both ways and normalized names
                if proc_name_n and (proc_name_n in source or proc_name_n in display_n or proc_name_n in source.replace('.', ' ')):
                    try:
                        return sess.SimpleAudioVolume.GetMasterVolume()
                    except Exception:
                        pass
                if display_n and (display_n in source or display_n in proc_name_n):
                    try:
                        return sess.SimpleAudioVolume.GetMasterVolume()
                    except Exception:
                        pass
                if not source and proc_name_n and proc_name_n == display_n:
                    try:
                        return sess.SimpleAudioVolume.GetMasterVolume()
                    except Exception:
                        pass
        except Exception:
            print("Error finding volume for session")
            pass
        return None

    async def try_play(self, id_or_session=None):
        s = await self.resolve_session(id_or_session)
        if s:
            await s.try_play_async()

    async def try_pause(self, id_or_session=None):
        s = await self.resolve_session(id_or_session)
        if s:
            await s.try_pause_async()

    async def try_next(self, id_or_session=None):
        s = await self.resolve_session(id_or_session)
        if s:
            await s.try_skip_next_async()

    async def try_previous(self, id_or_session=None):
        s = await self.resolve_session(id_or_session)
        if s:
            await s.try_skip_previous_async()

    async def resolve_session(self, id_or_session):
        if id_or_session is None:
            mgr = await self.get_manager()
            return mgr.get_current_session()
        if hasattr(id_or_session, "try_get_media_properties_async"):
            return id_or_session
        # otherwise try lookup by hashed id
        mgr = await self.get_manager()
        for s in mgr.get_sessions():
            if str(hash(s)) == str(id_or_session):
                return s
        return None

    def try_set_volume(self, gsma_session, level):
        """level is 0.0-1.0. Returns True on success."""
        try:
            source = (gsma_session.source_app_user_model_id or "") or ""
            source = source.lower()
            # normalize numeric input: accept 0-1 or 0-100
            try:
                lvl = float(level)
            except Exception:
                return False
            if lvl > 1.0:
                # assume 0-100 percentage
                lvl = max(0.0, min(100.0, lvl)) / 100.0
            lvl = max(0.0, min(1.0, lvl))

            sessions: list[AudioSession] = AudioUtilities.GetAllSessions()
            def norm(name: str) -> str:
                if not name:
                    return ""
                n = name.lower()
                n = re.sub(r"\.exe$", "", n)
                n = re.sub(r"[^a-z0-9]+", " ", n)
                return n.strip()

            for sess in sessions:
                # debug print of available session info (uncomment if needed)
                # print('checking', sess.DisplayName, getattr(sess, 'Process', None))
                try:
                    proc = sess.Process
                    proc_name = proc.name() if proc else ""
                except Exception:
                    proc_name = ""
                display = (sess.DisplayName or "") or ""
                proc_name_n = norm(proc_name)
                display_n = norm(display)

                matched = False
                if proc_name_n and (proc_name_n in source or proc_name_n in display_n or proc_name_n in source.replace('.', ' ')):
                    matched = True
                if not matched and display_n and (display_n in source or display_n in proc_name_n):
                    matched = True
                if not matched and not source and proc_name_n and proc_name_n == display_n:
                    matched = True

                if matched:
                    try:
                        # preferred call
                        sess.SimpleAudioVolume.SetMasterVolume(lvl, None)
                        return True
                    except Exception:
                        try:
                            # fallback: methods may differ across pycaw versions
                            sess.SimpleAudioVolume.SetMasterVolumeLevelScalar(lvl, None)
                            return True
                        except Exception as e:
                            print('Failed to set volume on matched session:', e)
                            return False
        except Exception:
            pass
        return False
