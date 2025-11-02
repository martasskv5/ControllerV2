from typing import Any, Awaitable, Callable, Dict
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
from pycaw.pycaw import AudioUtilities, AudioSession
import re

class MediaControllerPlugin:
    """Plugin wrapper exposing MediaController actions as named handlers.

    Each plugin exposes an `actions` dict mapping action name -> async handler(msg) -> dict response.
    """

    def __init__(self):
        self.name = "mediacontroller"
        self.prefix = "mc_"
        self.mc = MediaController()
        # map action name to handler coroutine
        self.actions: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
            "mc_list": self.list_handler,
            "mc_set_volume": self.set_volume_handler,
            "mc_play": self.play_handler,
            "mc_pause": self.pause_handler,
            "mc_next": self.next_handler,
            "mc_previous": self.previous_handler,
        }

    async def list_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        ml = await self.mc.get_media_list()
        safe = []
        for i in ml:
            s = {k: v for k, v in i.items() if k != "session"}
            safe.append(s)
        return {"ok": True, "sessions": safe}

    async def set_volume_handler(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        level = msg.get("level")
        sid = msg.get("id", None)
        s = await self._resolve_session_for_command(sid)
        if s is None:
            return {"ok": False, "error": "session_not_found"}
        success = self.mc.try_set_volume(s, level)
        return {"ok": bool(success)}

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
            return {"ok": False, "error": "session_not_found"}
        # action_callable may be async
        await action_callable(s)
        return {"ok": True}

    async def _resolve_session_for_command(self, id_or_none):
        if id_or_none is None or id_or_none == "current":
            return await self.mc.resolve_session(None)
        if hasattr(id_or_none, "try_get_media_properties_async"):
            return id_or_none
        return await self.mc.resolve_session(id_or_none)

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
            out.append({
                "id": str(hash(s)),  # stable per-process run similar to GetHashCode()
                "title": title,
                "artist": artist,
                "album": album,
                "is_playing": is_playing,
                "status": str(status),
                "source": source,
                "volume": vol,
                "session": s,  # keep session if you want to control it directly
            })
        return out

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
